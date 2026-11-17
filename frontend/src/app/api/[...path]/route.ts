import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

const HOP_BY_HOP_REQUEST_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "accept-encoding",
]);

const HOP_BY_HOP_RESPONSE_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function getBackendBaseUrl(): string {
  const raw =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8000";
  return raw.replace(/\/+$/, "");
}

async function handleProxy(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const backendBase = getBackendBaseUrl();
  const encodedPath = path.map((segment) => encodeURIComponent(segment)).join("/");
  const search = request.nextUrl?.search ?? new URL(request.url).search;
  const targetUrl = `${backendBase}/api/${encodedPath}${search}`;

  const forwardHeaders = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_REQUEST_HEADERS.has(key.toLowerCase())) {
      forwardHeaders.set(key, value);
    }
  });
  forwardHeaders.set("accept-encoding", "identity");

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  let bodyPayload: ArrayBuffer | undefined;
  if (hasBody) {
    const buf = await request.arrayBuffer();
    if (buf.byteLength > 0) {
      bodyPayload = buf;
    }
  }

  let upstreamRes: Response;
  try {
    upstreamRes = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body: bodyPayload,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (err: any) {
    return Response.json(
      {
        error: true,
        code: "UPSTREAM_API_UNREACHABLE",
        message: "تعذر الاتصال بخدمة الخلفية.",
        detail: err?.message || "Network error",
      },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  const upstreamHadEncoding = upstreamRes.headers.has("content-encoding");
  upstreamRes.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_RESPONSE_HEADERS.has(lower)) {
      return;
    }
    if (upstreamHadEncoding && (lower === "content-encoding" || lower === "content-length")) {
      return;
    }
    responseHeaders.set(key, value);
  });

  const noBody =
    method === "HEAD" ||
    upstreamRes.status === 204 ||
    upstreamRes.status === 205 ||
    upstreamRes.status === 304;

  return new Response(noBody ? null : upstreamRes.body, {
    status: upstreamRes.status,
    statusText: upstreamRes.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}

export async function HEAD(request: NextRequest, context: RouteContext): Promise<Response> {
  return handleProxy(request, context);
}
