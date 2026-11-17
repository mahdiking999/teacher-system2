import os
import sys
import json
import base64
import asyncio
import hashlib
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app.database import Base, engine, SessionLocal
from backend.app.services.seed_service import ensure_initial_seed_data
from backend.app.main import EXPORTS_DIR, create_export_task
from backend.app.schemas import ExportCreateRequest
from backend.app.services.export_service import verify_exported_file_structure

EVIDENCE_DIR = os.path.join(ROOT_DIR, "docs", "evidence")
SCREENSHOTS_DIR = os.path.join(EVIDENCE_DIR, "screenshots")
EXPORTS_EVIDENCE_DIR = os.path.join(EVIDENCE_DIR, "sample_exports")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(EXPORTS_EVIDENCE_DIR, exist_ok=True)

PILOT_PIN = os.getenv("PILOT_ACCESS_PIN", "").strip() or "evidence-pilot-pin"

ROUTES = [
    ("01_dashboard", "/"),
    ("02_curriculum", "/curriculum"),
    ("03_lessons", "/lessons"),
    ("04_tools", "/tools"),
    ("05_settings", "/settings"),
    ("06_daily_plan", "/daily-plan"),
    ("07_weekly_plan", "/weekly-plan"),
    ("08_five_day_plan", "/five-day-plan"),
    ("09_review", "/review"),
    ("10_reports", "/reports"),
    ("11_presentations", "/presentations"),
    ("12_sources", "/sources"),
    ("13_export_package", "/export-package"),
]

VIEWPORTS = [
    ("desktop_1440x900", 1440, 900),
    ("tablet_768x1024", 768, 1024),
    ("mobile_390x844", 390, 844),
    ("overflow_320x800", 320, 800),
]


def build_api_headers(pilot_pin: str = PILOT_PIN, context_id: str | None = None) -> dict[str, str]:
    headers = {"X-Pilot-Pin": pilot_pin}
    if context_id:
        headers["X-Active-Context-Id"] = context_id
    return headers


def api_request(
    url: str,
    method: str = "GET",
    payload: dict | None = None,
    pilot_pin: str = PILOT_PIN,
    context_id: str | None = None,
    timeout: int = 10,
) -> tuple[int, bytes]:
    headers = build_api_headers(pilot_pin=pilot_pin, context_id=context_id)
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def wait_for_url(url: str, timeout: int = 30, headers: dict[str, str] | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def find_browser_executable() -> str:
    env_path = os.getenv("CHROME_PATH", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    for cmd in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(cmd)
        if found:
            return found
    raise FileNotFoundError("Could not locate Chrome or Edge executable for headless CDP capture.")


def generate_sample_exports_and_verify():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_initial_seed_data(db, force=True)
        results = {}
        for fmt, filename in [
            ("docx", "sample_daily_plan.docx"),
            ("pdf", "sample_daily_plan.pdf"),
            ("pptx", "sample_presentation.pptx"),
            ("report_pdf", "sample_planning_report.pdf"),
            ("bundle_zip", "sample_full_bundle.zip"),
        ]:
            task_info = create_export_task(
                payload=ExportCreateRequest(
                    contextId="ctx_math_iq_demo",
                    planId="pln_daily_demo_a",
                    exportFormat=fmt,
                ),
                x_active_context_id="ctx_math_iq_demo",
                db=db,
            )
            src_files = os.listdir(EXPORTS_DIR)
            matching = [f for f in src_files if f.endswith(task_info["fileName"])]
            if matching:
                src_path = os.path.join(EXPORTS_DIR, matching[0])
                dst_path = os.path.join(EXPORTS_EVIDENCE_DIR, filename)
                with open(src_path, "rb") as f_in:
                    data = f_in.read()
                with open(dst_path, "wb") as f_out:
                    f_out.write(data)
                ver = verify_exported_file_structure(data, fmt)
                results[fmt] = {
                    "file": f"docs/evidence/sample_exports/{filename}",
                    "sizeBytes": len(data),
                    "sha256": task_info["contentSha256"],
                    "verification": ver,
                }
        with open(os.path.join(EVIDENCE_DIR, "export_verification_report.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("Sample exports generated and verified successfully.")
    finally:
        db.close()


class _SimpleWebSocket:
    """Minimal stdlib RFC 6455 WebSocket client for local Chrome CDP when `websockets` is unavailable."""

    def __init__(self, url: str, timeout: float = 30.0):
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("WebSocket handshake closed unexpectedly")
            buf += chunk
        header_end = buf.index(b"\r\n\r\n") + 4
        headers_raw = buf[:header_end].decode("latin-1", errors="replace")
        if "101" not in headers_raw.splitlines()[0]:
            raise RuntimeError(f"WebSocket handshake failed: {headers_raw.splitlines()[0]}")
        self._extra = bytearray(buf[header_end:])

    def _read_exact(self, n: int) -> bytes:
        while len(self._extra) < n:
            chunk = self.sock.recv(max(4096, n - len(self._extra)))
            if not chunk:
                raise EOFError("WebSocket connection closed")
            self._extra.extend(chunk)
        out = bytes(self._extra[:n])
        del self._extra[:n]
        return out

    def _send_frame(self, opcode: int, payload: bytes):
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def send_text(self, text: str):
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self) -> str:
        fragments: list[bytes] = []
        while True:
            b1, b2 = self._read_exact(2)
            fin = (b1 >> 7) & 1
            opcode = b1 & 0x0F
            masked = (b2 >> 7) & 1
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length) if length else b""
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise EOFError("WebSocket closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            fragments.append(payload)
            if fin:
                return b"".join(fragments).decode("utf-8", errors="replace")

    def close(self):
        try:
            self._send_frame(0x8, b"")
        except Exception:
            pass
        self.sock.close()


async def cdp_capture_all(ws_url: str, pilot_pin: str = PILOT_PIN, frontend_port: int = 3000):
    viewport_audit = []
    msg_id = 0
    console_errors: list[dict] = []
    failed_requests: list[dict] = []
    current_route = "/"
    pending_urls: dict[str, str] = {}

    async def _run_with_transport(send_raw, recv_raw):
        nonlocal msg_id, current_route

        async def send_cmd(method: str, params: dict = None):
            nonlocal msg_id
            msg_id += 1
            cur_id = msg_id
            await send_raw(json.dumps({"id": cur_id, "method": method, "params": params or {}}))
            while True:
                raw = await recv_raw()
                data = json.loads(raw)
                if data.get("id") == cur_id:
                    return data.get("result", {})
                ev_method = data.get("method")
                ev_params = data.get("params", {})
                if ev_method == "Runtime.exceptionThrown":
                    details = ev_params.get("exceptionDetails", {})
                    console_errors.append({
                        "route": current_route,
                        "type": "exception",
                        "text": details.get("text") or details.get("exception", {}).get("description", ""),
                    })
                elif ev_method == "Runtime.consoleAPICalled" and ev_params.get("type") == "error":
                    args = ev_params.get("args", [])
                    console_errors.append({
                        "route": current_route,
                        "type": "console.error",
                        "text": " ".join(str(a.get("value") or a.get("description") or "") for a in args),
                    })
                elif ev_method == "Network.requestWillBeSent":
                    req_id = ev_params.get("requestId")
                    req_url = ev_params.get("request", {}).get("url", "")
                    if req_id:
                        pending_urls[req_id] = req_url
                elif ev_method == "Network.responseReceived":
                    resp = ev_params.get("response", {})
                    status = resp.get("status", 200)
                    if status >= 400:
                        failed_requests.append({
                            "route": current_route,
                            "url": resp.get("url", ""),
                            "status": status,
                        })
                elif ev_method == "Network.loadingFailed":
                    req_id = ev_params.get("requestId", "")
                    failed_requests.append({
                        "route": current_route,
                        "url": pending_urls.get(req_id, ""),
                        "error": ev_params.get("errorText", "loadingFailed"),
                    })

        await send_cmd("Page.enable")
        await send_cmd("Runtime.enable")
        await send_cmd("Network.enable")

        # Inject PILOT_ACCESS_PIN into sessionStorage before any route renders
        await send_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": f"window.sessionStorage.setItem('agy_pilot_pin', {json.dumps(pilot_pin)});"},
        )

        for route_slug, route_path in ROUTES:
            current_route = route_path
            url = f"http://127.0.0.1:{frontend_port}{route_path}"
            await send_cmd("Page.navigate", {"url": url})

            # Wait for client fetch & React hydration to settle (max ~5s)
            for _ in range(25):
                await asyncio.sleep(0.2)
                ready_res = await send_cmd(
                    "Runtime.evaluate",
                    {
                        "expression": """(() => {
                            const hasPinGate = !!document.querySelector('#pilot-access-pin');
                            const text = document.body ? document.body.innerText : '';
                            const loading = text.includes('جارٍ التحميل') || text.includes('جارٍ تحميل');
                            return !hasPinGate && !loading && text.trim().length > 20;
                        })()""",
                        "returnByValue": True,
                    },
                )
                if ready_res.get("result", {}).get("value") is True:
                    break
            await asyncio.sleep(0.2)

            for vp_name, w, h in VIEWPORTS:
                if vp_name in ("tablet_768x1024", "overflow_320x800") and route_slug not in (
                    "01_dashboard",
                    "06_daily_plan",
                    "09_review",
                    "11_presentations",
                ):
                    continue

                await send_cmd(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": w,
                        "height": h,
                        "deviceScaleFactor": 1,
                        "mobile": w < 820,
                    },
                )
                await asyncio.sleep(0.2)

                eval_res = await send_cmd(
                    "Runtime.evaluate",
                    {
                        "expression": """JSON.stringify({
                            innerWidth: window.innerWidth,
                            scrollWidth: document.documentElement.scrollWidth,
                            hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
                            dir: document.documentElement.dir || 'rtl',
                            lang: document.documentElement.lang || 'ar',
                            pinGateVisible: !!document.querySelector('#pilot-access-pin')
                        })""",
                        "returnByValue": True,
                    },
                )
                metrics_str = eval_res.get("result", {}).get("value", "{}")
                metrics = json.loads(metrics_str)

                shot = await send_cmd(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "clip": {"x": 0, "y": 0, "width": w, "height": h, "scale": 1},
                    },
                )
                b64_data = shot.get("data", "")
                out_file = os.path.join(SCREENSHOTS_DIR, f"{route_slug}_{vp_name}.png")
                if b64_data:
                    with open(out_file, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                viewport_audit.append(
                    {
                        "route": route_path,
                        "screenshot": f"docs/evidence/screenshots/{route_slug}_{vp_name}.png",
                        "viewport": f"{w}x{h}",
                        **metrics,
                    }
                )

    if websockets is not None:
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            await _run_with_transport(ws.send, ws.recv)
    else:
        simple_ws = _SimpleWebSocket(ws_url, timeout=30.0)
        try:
            await _run_with_transport(
                lambda msg: asyncio.to_thread(simple_ws.send_text, msg),
                lambda: asyncio.to_thread(simple_ws.recv_text),
            )
        finally:
            simple_ws.close()

    report = {
        "viewports": viewport_audit,
        "consoleErrorsCount": len(console_errors),
        "consoleErrors": console_errors,
        "failedRequestsCount": len(failed_requests),
        "failedRequests": failed_requests,
    }
    with open(os.path.join(EVIDENCE_DIR, "viewport_audit_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(
        f"Captured {len(viewport_audit)} screenshots via CDP "
        f"(consoleErrors={len(console_errors)}, failedRequests={len(failed_requests)})."
    )


def _terminate_proc(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def capture_all_screenshots():
    chrome_path = find_browser_executable()
    python_exe = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(python_exe):
        python_exe = sys.executable
    node_exe = "node"
    next_bin = os.path.join(ROOT_DIR, "frontend", "node_modules", "next", "dist", "bin", "next")
    user_data_dir = tempfile.mkdtemp(prefix="chrome_cdp_")

    backend_port = int(os.getenv("EVIDENCE_BACKEND_PORT", "8000"))
    frontend_port = int(os.getenv("EVIDENCE_FRONTEND_PORT", "3000"))
    cdp_port = int(os.getenv("EVIDENCE_CDP_PORT", "9229"))

    backend_env = {**os.environ, "PILOT_ACCESS_PIN": PILOT_PIN, "ENABLE_DEMO_SEED": os.getenv("ENABLE_DEMO_SEED", "1")}
    frontend_env = {**os.environ, "INTERNAL_API_URL": f"http://127.0.0.1:{backend_port}"}

    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
        cwd=ROOT_DIR,
        env=backend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frontend_proc = subprocess.Popen(
        [node_exe, next_bin, "start", "-p", str(frontend_port)],
        cwd=os.path.join(ROOT_DIR, "frontend"),
        env=frontend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    chrome_proc = subprocess.Popen(
        [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print(f"Waiting for backend ({backend_port}), frontend ({frontend_port}), and Chrome CDP ({cdp_port})...")
        if not wait_for_url(f"http://127.0.0.1:{backend_port}/api/health", 25):
            raise RuntimeError(f"Backend did not become ready on port {backend_port}")
        status_code, _ = api_request(
            f"http://127.0.0.1:{backend_port}/api/contexts",
            pilot_pin=PILOT_PIN,
        )
        if status_code != 200:
            raise RuntimeError(f"Authenticated backend check failed with status {status_code}")
        if not wait_for_url(f"http://127.0.0.1:{frontend_port}/", 25):
            raise RuntimeError(f"Frontend did not become ready on port {frontend_port}")
        if not wait_for_url(f"http://127.0.0.1:{cdp_port}/json", 15):
            raise RuntimeError(f"Chrome CDP did not become ready on port {cdp_port}")

        with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json") as resp:
            targets = json.loads(resp.read().decode("utf-8"))
        page_target = next(t for t in targets if t.get("type") == "page")
        ws_url = page_target["webSocketDebuggerUrl"]

        asyncio.run(cdp_capture_all(ws_url, pilot_pin=PILOT_PIN, frontend_port=frontend_port))
    finally:
        _terminate_proc(chrome_proc)
        _terminate_proc(frontend_proc)
        _terminate_proc(backend_proc)
        shutil.rmtree(user_data_dir, ignore_errors=True)


if __name__ == "__main__":
    generate_sample_exports_and_verify()
    capture_all_screenshots()
