import base64
import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .pdf_service import normalize_indesign_arabic_ligatures

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://100.120.103.82:20128/v1").rstrip("/")
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY", "").strip()
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")

TEXT_MODELS = [
    "nv-nemotron-3-5-bolt-e4b",
    "nv-nemotron-3-5-super-vl-120b",
    "nv-nemotron-3-nano-omni-30b",
]
VISION_MODELS = [
    "nv-nemotron-3-5-super-vl-120b",
    "nv-nemotron-3-nano-omni-30b",
]
UPSTREAM_NVIDIA_MAP = {
    "nv-nemotron-3-5-bolt-e4b": "nvidia/nemotron-3.5-bolt-e4b",
    "nv-nemotron-3-5-super-vl-120b": "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "nv-nemotron-3-nano-omni-30b": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
}

_nvidia_key_counter = 0


def _get_nvidia_keys() -> List[str]:
    raw = os.getenv("NVIDIA_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def _next_nvidia_key(keys: List[str]) -> str:
    global _nvidia_key_counter
    if not keys:
        return ""
    key = keys[_nvidia_key_counter % len(keys)]
    _nvidia_key_counter += 1
    return key


def _is_omniroute_keyless_allowed() -> bool:
    raw = os.getenv("OMNIROUTE_ALLOW_KEYLESS", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def get_ai_status() -> Dict[str, Any]:
    omni_base = os.getenv("OMNIROUTE_BASE_URL", OMNIROUTE_BASE_URL).strip().rstrip("/")
    omni_key = os.getenv("OMNIROUTE_API_KEY", OMNIROUTE_API_KEY).strip()
    omni_ready = bool(omni_base and (omni_key or _is_omniroute_keyless_allowed()))
    ready = omni_ready or bool(_get_nvidia_keys())
    return {
        "available": ready,
        "configured": ready,
        "mode": "live" if ready else "fallback",
        "textGenerationReady": ready,
        "visionGenerationReady": ready,
        "fallbackAvailable": True,
    }


def _extract_json_from_text(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch not in ("{", "["):
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned, idx)
            if isinstance(obj, dict):
                return obj
            if isinstance(obj, list):
                return {"items": obj}
        except Exception:
            continue
    return None


def _post_chat_completion(
    base_url: str,
    api_key: str,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    image_png_bytes: Optional[bytes] = None,
    timeout_sec: float = 18.0,
    proxy_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if image_png_bytes:
        b64 = base64.b64encode(image_png_bytes).decode("ascii")
        user_content: Any = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
    else:
        user_content = user_prompt

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = httpx.Timeout(timeout_sec, connect=2.5)
    client_kwargs: Dict[str, Any] = {"timeout": timeout}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    with httpx.Client(**client_kwargs) as client:
        resp = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        return None
    msg = choices[0].get("message") or {}
    text = msg.get("content") or msg.get("reasoning_content") or ""
    return _extract_json_from_text(str(text))


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    image_png_bytes: Optional[bytes] = None,
    timeout_sec: float = 18.0,
) -> Tuple[Optional[Dict[str, Any]], str]:
    models = VISION_MODELS if image_png_bytes else TEXT_MODELS
    omni_base = os.getenv("OMNIROUTE_BASE_URL", OMNIROUTE_BASE_URL).strip().rstrip("/")
    omni_key = os.getenv("OMNIROUTE_API_KEY", OMNIROUTE_API_KEY).strip()
    ts_proxy = os.getenv("TAILSCALE_HTTP_PROXY", "").strip() or None

    if omni_base and (omni_key or _is_omniroute_keyless_allowed()):
        proxy_candidates = [ts_proxy, None] if ts_proxy else [None]
        for m in models:
            for p_url in proxy_candidates:
                try:
                    parsed = _post_chat_completion(
                        omni_base, omni_key, m, system_prompt, user_prompt, image_png_bytes, timeout_sec, proxy_url=p_url
                    )
                    if parsed is not None:
                        return parsed, m
                except Exception:
                    continue

    nv_keys = _get_nvidia_keys()
    if nv_keys:
        nv_base = os.getenv("NVIDIA_BASE_URL", NVIDIA_BASE_URL).rstrip("/")
        for m in models:
            upstream_id = UPSTREAM_NVIDIA_MAP.get(m, m)
            try:
                parsed = _post_chat_completion(
                    nv_base, _next_nvidia_key(nv_keys), upstream_id, system_prompt, user_prompt, image_png_bytes, timeout_sec
                )
                if parsed is not None:
                    return parsed, upstream_id
            except Exception:
                continue

    return None, "deterministic_fallback"


def generate_slides_with_ai(
    plan_dict: Dict[str, Any],
    context_snap: Dict[str, Any],
    source_excerpt: str = "",
    slides_count: int = 6,
    custom_instructions: str = "",
) -> Dict[str, Any]:
    slides_count = max(3, min(12, int(slides_count or 6)))
    lang = str(context_snap.get("language") or "ar")
    subject = context_snap.get("subject") or "المادة الدراسية"
    grade = context_snap.get("grade") or "الصف الدراسي"
    country = context_snap.get("country") or ""
    title = plan_dict.get("title") or "عرض الدرس"
    objectives = plan_dict.get("objectives") or []
    phases = plan_dict.get("phases") or []
    assessment = plan_dict.get("formativeAssessment") or ""

    system_prompt = (
        "أنت مصمم عروض تقديمية تربوية خبير. أعدّ شرائح صفية تفاعلية واضحة ومباشرة بصيغة JSON فقط "
        "بالمفتاح `slides` وهو مصفوفة عناصر كل منها `{order, title, content}`. "
        "لا تكتب أي نص خارج كائن JSON."
    )
    user_prompt = json.dumps(
        {
            "task": f"Generate exactly {slides_count} classroom presentation slides in language='{lang}'",
            "subject": subject,
            "grade": grade,
            "country": country,
            "lessonTitle": title,
            "objectives": objectives,
            "phases": [{"phaseName": p.get("phaseName"), "teacherActivity": p.get("teacherActivity"), "materials": p.get("materials")} for p in phases],
            "subjectItems": plan_dict.get("subjectItems") or [],
            "formativeAssessment": assessment,
            "sourceExcerpt": source_excerpt[:2500],
            "customInstructions": custom_instructions,
            "requiredSchema": {
                "slides": [
                    {"order": 1, "title": "عنوان الشريحة", "content": "السطر الأول الفكرة الرئيسة\nالسطر الثاني سؤال تفاعلي أو نشاط صفي"}
                ]
            },
        },
        ensure_ascii=False,
    )

    parsed, model_used = call_llm_json(system_prompt, user_prompt, timeout_sec=20.0)
    raw_slides = (parsed or {}).get("slides") if isinstance(parsed, dict) else None
    clean_slides: List[Dict[str, Any]] = []

    if isinstance(raw_slides, list) and len(raw_slides) >= 1:
        for idx, item in enumerate(raw_slides[:slides_count], start=1):
            if isinstance(item, dict):
                s_title = str(item.get("title") or f"شريحة {idx}").strip()
                s_content = str(item.get("content") or "").strip()
                if s_title or s_content:
                    clean_slides.append({"order": idx, "title": s_title, "content": s_content or s_title})

    if not clean_slides:
        model_used = "deterministic_fallback"
        clean_slides = _build_deterministic_slides(
            title=title,
            subject=subject,
            grade=grade,
            country=country,
            objectives=objectives,
            phases=phases,
            assessment=assessment,
            source_excerpt=source_excerpt,
            slides_count=slides_count,
            custom_instructions=custom_instructions,
        )

    return {
        "slides": clean_slides,
        "modelUsed": model_used,
        "slidesCount": len(clean_slides),
    }


def _build_deterministic_slides(
    title: str,
    subject: str,
    grade: str,
    country: str,
    objectives: List[str],
    phases: List[Dict[str, Any]],
    assessment: str,
    source_excerpt: str,
    slides_count: int,
    custom_instructions: str = "",
) -> List[Dict[str, Any]]:
    obj_text = "\n".join(f"• {o}" for o in objectives) if objectives else "• تحقيق نتاجات التعلّم الأساسية للدرس."
    excerpt_line = (source_excerpt.strip().splitlines()[0][:180] if source_excerpt.strip() else "مادة الدرس المعتمدة من خطة المعلم.")
    note_line = f"\nتوجيه المعلم: {custom_instructions}" if custom_instructions.strip() else ""

    base = [
        {"title": title, "content": f"{subject} · {grade} {('· ' + country) if country else ''}\nتمهيد تفاعلي لربط الدرس بخبرات المتعلمين{note_line}".strip()},
        {"title": "نتاجات التعلّم المستهدفة", "content": f"{obj_text}\nما الذي تتوقع أن تتعلمه بنهاية الحصة؟"},
        {"title": "التهيئة واستدعاء المعرفة السابقة", "content": f"{excerpt_line}\nسؤال استهلالي: كيف يرتبط موضوع اليوم بما سبقت دراسته؟"},
        {"title": "الشرح والتفسير والنمذجة", "content": f"{(phases[1].get('teacherActivity') if len(phases) > 1 else 'عرض المفاهيم الرئيسة خطوة بخطوة مع أمثلة موجهة.')}\nناقش خطوات الفهم مع زميلك."},
        {"title": "التدريب التعاوني والممارسة", "content": f"{(phases[2].get('studentActivity') if len(phases) > 2 else 'تطبيق عملي موجه على مفاهيم الدرس بالبطاقات والسبورة.')}\nاستراتيجية التفكير: لماذا اخترت هذه الطريقة؟"},
        {"title": "التقويم الختامي والتوسعة", "content": f"{assessment or 'مهمة تقويم ختامية لقياس تحقق أهداف الدرس.'}\nبطاقة خروج: لخّص الفكرة الأهم في جملة واحدة."},
    ]
    for idx in range(len(base), slides_count):
        base.append(
            {
                "title": f"إثراء وتطبيق إضافي ({idx + 1})",
                "content": f"نشاط توسعة مرتبط بدرس «{title}» لمادة {subject}.\nسؤال التحدي: طبّق المفهوم في موقف حياتي جديد.",
            }
        )
    return [{"order": i + 1, "title": item["title"], "content": item["content"]} for i, item in enumerate(base[:slides_count])]


def _sanitize_slides(raw_slides: Any, fallback_slides: List[Dict[str, Any]], max_count: int = 12) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    if isinstance(raw_slides, list):
        for idx, item in enumerate(raw_slides[:max_count], start=1):
            if isinstance(item, dict):
                s_title = str(item.get("title") or f"شريحة {idx}").strip()
                s_content = str(item.get("content") or "").strip() or s_title
                clean.append({"order": idx, "title": s_title, "content": s_content})
            elif isinstance(item, str) and item.strip():
                clean.append({"order": idx, "title": f"شريحة {idx}", "content": item.strip()})
    return clean if clean else fallback_slides


def _normalize_phases_minutes(phases: List[Any], total_minutes: int) -> List[Dict[str, Any]]:
    clean_phases: List[Dict[str, Any]] = []
    for item in phases or []:
        if not isinstance(item, dict):
            continue
        p = dict(item)
        try:
            mins = max(1, int(float(p.get("minutes") or 5)))
        except Exception:
            mins = 5
        p["minutes"] = mins
        p.setdefault("periodNumber", 1)
        p["isHomeEnrichment"] = bool(p.get("isHomeEnrichment", False))
        clean_phases.append(p)

    if not clean_phases:
        return []

    in_class = [p for p in clean_phases if not p["isHomeEnrichment"]]
    if in_class and total_minutes > 0:
        cur_sum = sum(p["minutes"] for p in in_class)
        if cur_sum != total_minutes:
            # Proportionally scale to fit total_minutes while keeping >=1 min per phase (if possible)
            min_per_phase = 1 if total_minutes >= len(in_class) else 0
            for p in in_class:
                scaled = round((p["minutes"] / max(1, cur_sum)) * total_minutes)
                p["minutes"] = max(min_per_phase, scaled)
            delta = total_minutes - sum(p["minutes"] for p in in_class)
            # Distribute any remaining +/- delta across phases safely
            ordered = sorted(in_class, key=lambda x: x["minutes"], reverse=(delta < 0))
            guard = 0
            while delta != 0 and guard < 200:
                changed = False
                for p in ordered:
                    if delta == 0:
                        break
                    if delta > 0:
                        p["minutes"] += 1
                        delta -= 1
                        changed = True
                    elif p["minutes"] > min_per_phase:
                        p["minutes"] -= 1
                        delta += 1
                        changed = True
                if not changed:
                    break
                guard += 1

    for i, p in enumerate(clean_phases, start=1):
        p["order"] = i
    return clean_phases


def generate_daily_plan_with_ai(
    plan_dict: Dict[str, Any],
    context_snap: Dict[str, Any],
    lesson_title: str = "",
    source_excerpt: str = "",
    custom_instructions: str = "",
) -> Dict[str, Any]:
    subject = context_snap.get("subject") or "المادة الدراسية"
    grade = context_snap.get("grade") or "الصف الدراسي"
    country = context_snap.get("country") or ""
    periods_count = int(plan_dict.get("periodsCount") or 1)
    period_minutes = int(plan_dict.get("periodMinutes") or 45)
    total_allocated = periods_count * period_minutes
    effective_title = lesson_title.strip() or plan_dict.get("title") or f"خطة درس — {subject}"

    system_prompt = (
        "أنت خبير مناهج وطرائق تدريس. أنشئ خطة درس يومية متكاملة وفق دورة التعلّم الخماسية "
        "(التهيئة، التدريس، التدريب، التقويم، التوسعة والإثراء) بصيغة JSON فقط."
    )
    user_prompt = json.dumps(
        {
            "task": "Draft a complete daily lesson plan in Arabic JSON matching the schema strictly.",
            "subject": subject,
            "grade": grade,
            "country": country,
            "lessonTitle": effective_title,
            "periodsCount": periods_count,
            "periodMinutes": period_minutes,
            "totalClassMinutesMustEqual": total_allocated,
            "sourceExcerpt": source_excerpt[:2500],
            "customInstructions": custom_instructions,
            "requiredSchema": {
                "objectives": ["هدف 1", "هدف 2", "هدف 3"],
                "priorKnowledge": "المتطلبات القبلية",
                "teacherRole": "دور المعلم",
                "studentRole": "دور المتعلم",
                "phases": [
                    {
                        "order": 1,
                        "periodNumber": 1,
                        "phaseName": "التهيئة",
                        "materials": "السبورة والكتاب",
                        "sourceRef": "المقرر",
                        "executorRole": "المعلم يهيئ المتعلم",
                        "teacherActivity": "...",
                        "studentActivity": "...",
                        "objective": "...",
                        "minutes": 5,
                        "isHomeEnrichment": False,
                    }
                ],
                "formativeAssessment": "أداة ومعيار التقويم التكويني",
                "differentiation": "التمايز والدعم",
                "homework": "الواجب المنزلي",
                "slides": [{"order": 1, "title": "...", "content": "..."}],
            },
        },
        ensure_ascii=False,
    )

    parsed, model_used = call_llm_json(system_prompt, user_prompt, timeout_sec=22.0)

    if isinstance(parsed, dict) and isinstance(parsed.get("phases"), list) and len(parsed["phases"]) >= 3:
        objectives = [str(o).strip() for o in (parsed.get("objectives") or []) if str(o).strip()]
        if not objectives:
            objectives = [f"أن يوضح الطالب المفاهيم الرئيسة لدرس {effective_title}."]
        phases = _normalize_phases_minutes(parsed["phases"], total_allocated)
        if not phases:
            phases = _normalize_phases_minutes([], total_allocated)
        else:
            fallback_slides = _build_deterministic_slides(
                effective_title, subject, grade, country, objectives, phases, str(parsed.get("formativeAssessment") or ""), source_excerpt, 5
            )
            slides = _sanitize_slides(parsed.get("slides"), fallback_slides, max_count=8)
            return {
                "title": effective_title,
                "objectives": objectives,
                "priorKnowledge": str(parsed.get("priorKnowledge") or f"استرجاع المفاهيم التمهيدية لدرس {effective_title}.").strip(),
                "teacherRole": str(parsed.get("teacherRole") or "التوجيه والنمذجة وإدارة الحوار الصفي والتقويم التكويني.").strip(),
                "studentRole": str(parsed.get("studentRole") or "الاستكشاف والممارسة الموجهة والمستقلة وتعليل الحلول.").strip(),
                "phases": phases,
                "formativeAssessment": str(parsed.get("formativeAssessment") or "بطاقة خروج وملاحظة أداء المتعلم وفق محك واضح.").strip(),
                "differentiation": str(parsed.get("differentiation") or "دعم إضافي للمتعثرين وتحدٍ إثرائي للمتمكنين.").strip(),
                "homework": str(parsed.get("homework") or "تطبيق منزلي مرتبط بأهداف الدرس.").strip(),
                "slides": slides,
                "modelUsed": model_used,
            }

    # Deterministic fallback when offline
    scale = periods_count
    fallback_phases = _normalize_phases_minutes(
        [
            {"order": 1, "periodNumber": 1, "phaseName": "التهيئة", "materials": "سبورة، بطاقات", "sourceRef": "المقرر", "executorRole": "المعلم يهيئ المتعلم", "teacherActivity": f"يطرح سؤالًا تمهيديًا حول «{effective_title}».", "studentActivity": "يستدعي خبراته السابقة.", "objective": "استدعاء المتطلبات السابقة", "minutes": 5 * scale, "isHomeEnrichment": False},
            {"order": 2, "periodNumber": 1, "phaseName": "التدريس (الشرح والتفسير)", "materials": "السبورة والكتاب", "sourceRef": "المقرر", "executorRole": "المعلم يشرح وينمذج", "teacherActivity": f"يشرح المفاهيم الأساسية في «{effective_title}» عبر أمثلة متدرجة.", "studentActivity": "يتابع النمذجة ويدون الملاحظات.", "objective": "بناء المفهوم الأساسي", "minutes": 15 * scale, "isHomeEnrichment": False},
            {"order": 3, "periodNumber": 2 if periods_count == 2 else 1, "phaseName": "التدريب", "materials": "أوراق عمل، بطاقات", "sourceRef": "المقرر", "executorRole": "المتعلم يتدرب", "teacherActivity": "يوجه التدريب التعاوني والفردي ويصحح المفاهيم.", "studentActivity": "ينفذ التطبيقات العملية ويناقش خطواته.", "objective": "تعزيز الطلاقة والفهم", "minutes": 12 * scale, "isHomeEnrichment": False},
            {"order": 4, "periodNumber": 2 if periods_count == 2 else 1, "phaseName": "التقويم", "materials": "أداة تقويم تكويني", "sourceRef": "الدليل", "executorRole": "المعلم يقوّم", "teacherActivity": "يطبق فقرة تقويمية مرتبطة بنتائج التعلم.", "studentActivity": "يقدم دليل الفهم كتابيًا أو شفهيًا.", "objective": "التحقق من تحقق الأهداف", "minutes": 8 * scale, "isHomeEnrichment": False},
            {"order": 5, "periodNumber": 2 if periods_count == 2 else 1, "phaseName": "التوسعة والإثراء", "materials": "بطاقات إثرائية", "sourceRef": "المعلم", "executorRole": "المتعلم يتوسع", "teacherActivity": "يطرح موقفًا تطبيقيًا جديدًا لنقل أثر التعلم.", "studentActivity": "يربط الدرس بمواقف حياتية.", "objective": "نقل أثر التعلم", "minutes": max(1, total_allocated - (40 * scale)), "isHomeEnrichment": False},
        ],
        total_allocated,
    )
    objectives = [
        f"أن يفسر الطالب المفاهيم الأساسية في درس {effective_title}.",
        f"أن يطبق الطالب خطوات الحل أو التحليل بدقة في أنشطة الصف.",
    ]
    assessment = "ملاحظة الأداء أثناء التدريب مع بطاقة خروج ختامية مرتبطة بأهداف الدرس."
    return {
        "title": effective_title,
        "objectives": objectives,
        "priorKnowledge": f"مراجعة المفاهيم التمهيدية المرتبطة بـ «{effective_title}» في مادة {subject}.",
        "teacherRole": "التهيئة والنمذجة وإدارة النقاش الصفي وتقديم التغذية الراجعة.",
        "studentRole": "المشاركة النشطة في الاستكشاف والتدريب وتبرير الاستنتاجات.",
        "phases": fallback_phases,
        "formativeAssessment": assessment,
        "differentiation": "أمثلة بصرية مبسطة للدعم، ومهمة تحدٍ للمتعلمين المتقدمين.",
        "homework": f"نشاط منزلي تطبيقي حول {effective_title} (15 دقيقة).",
        "slides": _build_deterministic_slides(effective_title, subject, grade, country, objectives, fallback_phases, assessment, source_excerpt, 5),
        "modelUsed": "deterministic_fallback",
    }


def ocr_pdf_page_with_ai(
    image_png_bytes: Optional[bytes],
    fallback_text: str,
    page_number: int,
    context_snap: Dict[str, Any],
) -> Dict[str, Any]:
    subject = context_snap.get("subject") or "المادة"
    grade = context_snap.get("grade") or ""
    system_prompt = (
        "أنت محرك OCR عربي وثنائي اللغة دقيق للكتب المدرسية. استخرج كامل النص الموجود في الصفحة بدقة مع الحفاظ على "
        "العناوين والأرقام والمعادلات والصفحة المطبوعة. أعد JSON فقط بالصيغة: "
        "{\"extractedText\": \"...\", \"printedPageNumber\": \"...\", \"notes\": \"...\"}."
    )
    user_prompt = (
        f"استخرج النص الكامل من صفحة كتاب مادة ({subject} - {grade}) رقم PDF ({page_number}). "
        f"النص الأولي المتاح: {fallback_text[:1000]}"
    )

    parsed, model_used = call_llm_json(
        system_prompt,
        user_prompt,
        image_png_bytes=image_png_bytes,
        timeout_sec=24.0,
    )
    if isinstance(parsed, dict) and str(parsed.get("extractedText") or "").strip():
        return {
            "extracted": True,
            "extractedText": str(parsed["extractedText"]).strip(),
            "printedPageNumber": str(parsed.get("printedPageNumber") or page_number).strip(),
            "notes": str(parsed.get("notes") or "").strip(),
            "modelUsed": model_used,
        }

    preserved = fallback_text.strip()
    return {
        "extracted": False,
        "extractedText": preserved,
        "printedPageNumber": str(page_number),
        "notes": "تم الإبقاء على النص المستخرج محليًا عبر PyMuPDF لعدم توفر نموذج الرؤية الحية." if preserved else "تعذر الوصول لنموذج الرؤية الذكية؛ الصفحة بحاجة لتفريغ يدوي.",
        "modelUsed": model_used,
    }


_TOC_KEYWORDS = ("المحتويات", "الـمحتويــات", "الفهرس", "فهرس", "Contents", "Content")
_AR_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_ORDINALS: Dict[str, int] = {
    "الاول": 1, "الأول": 1, "الاولى": 1, "الأولى": 1,
    "الثاني": 2, "الثانية": 2, "الثالث": 3, "الثالثة": 3,
    "الرابع": 4, "الرابعة": 4, "الخامس": 5, "الخامسة": 5,
    "السادس": 6, "السادسة": 6, "السابع": 7, "السابعة": 7,
    "الثامن": 8, "الثامنة": 8, "التاسع": 9, "التاسعة": 9,
    "العاشر": 10, "العاشرة": 10, "الحادي عشر": 11, "الحادية عشرة": 11,
    "الثاني عشر": 12, "الثانية عشرة": 12,
}


def _has_toc_keyword(txt: str) -> bool:
    if not txt:
        return False
    plain = txt.replace("\u0640", "")
    return any(k in plain for k in _TOC_KEYWORDS)


def _is_toc_page_text(txt: str) -> bool:
    if not txt:
        return False
    if _has_toc_keyword(txt):
        return True
    plain = txt.replace("\u0640", "")
    lesson_lines = sum(1 for ln in plain.splitlines() if "الدرس" in ln or re.search(r"\b\d{1,2}\s*-\s*\d{1,2}\b", ln))
    return lesson_lines >= 5 and ("الفصل" in plain or "الوحدة" in plain or "Chapter" in plain)


def _clean_structural_page_text(txt: str) -> str:
    if not txt:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in txt.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _select_structural_pages(pages_text: List[Dict[str, Any]], max_pages: int = 24) -> List[Dict[str, Any]]:
    """Prioritize Table of Contents (المحتويات/الفهرس anywhere in the book, including end-of-book Iraqi TOCs)
    and Chapter Opener pages (الفصل + multiple الدرس entries) before falling back to leading pages."""
    explicit_toc_pages: List[Dict[str, Any]] = []
    dense_toc_pages: List[Dict[str, Any]] = []
    opener_pages: List[Dict[str, Any]] = []
    seen_nums = set()
    for p in pages_text:
        txt = str(p.get("text") or "")
        pnum = p.get("pdfPageNumber")
        if _has_toc_keyword(txt):
            explicit_toc_pages.append(p)
            seen_nums.add(pnum)
        elif _is_toc_page_text(txt):
            dense_toc_pages.append(p)
            seen_nums.add(pnum)
        elif ("الفصل" in txt or "الوحدة" in txt or "Chapter" in txt) and (txt.count("الدرس") >= 2 or txt.count("Lesson") >= 2):
            opener_pages.append(p)
            seen_nums.add(pnum)

    structural = explicit_toc_pages + dense_toc_pages + opener_pages
    if len(structural) >= 3:
        return structural[:max_pages]
    for p in pages_text[:max_pages]:
        pnum = p.get("pdfPageNumber")
        if pnum not in seen_nums:
            structural.append(p)
            seen_nums.add(pnum)
        if len(structural) >= max_pages:
            break
    return structural


def _clean_toc_title(raw_title: str) -> str:
    s = raw_title.replace("\u0640", "")
    s = re.sub(r"[ \t]+", " ", s).strip()
    # Strip dot leaders & trailing page numbers if still attached
    s = re.sub(r"[\.·•…_]{2,}\s*\d*\s*$", "", s).strip()
    s = re.sub(r"^[\.\:\-\–\—\)]+", "", s).strip()
    s = re.sub(r"[\.\:\-\–\—\(]+$", "", s).strip()
    # Repair InDesign LTR trailing variable placement (". R ... في" -> "... في R")
    if s.startswith("R ") and s.endswith(" في"):
        s = s[2:].strip() + " R"
    elif s.startswith("R "):
        s = s[2:].strip()
    if s.count("(") > s.count(")"):
        s += ")"
    return s


def _parse_ordinal_or_int(token: str, default_val: int) -> int:
    clean_tok = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", token).translate(_AR_INDIC_DIGITS).strip()
    if clean_tok.isdigit():
        return int(clean_tok)
    return _ARABIC_ORDINALS.get(clean_tok, default_val)


def _match_chapter_heading(line_clean: str, fallback_num: int) -> Optional[Tuple[int, str, Optional[int]]]:
    # Iraqi InDesign reversed TOC/opener format: "[page?] : <title><num> الفصل"
    m_rev = re.match(
        r"^(?:(\d{1,4})\s+)?[:\-\.]*\s*(.+?)\s*(\d{1,2})\s*(الفصل|الوحدة|الباب)\s*$",
        line_clean,
    )
    if m_rev:
        pg = int(m_rev.group(1)) if m_rev.group(1) else None
        title = _clean_toc_title(m_rev.group(2))
        cnum = int(m_rev.group(3))
        if title:
            return cnum, f"{m_rev.group(4)} {cnum}: {title}", pg

    # Standard Arabic/English forward format: "[page?] الفصل <num/ordinal>: <title> [page?]"
    m_fwd = re.match(
        r"^(?:(\d{1,4})\s+)?(الفصل|الوحدة|الباب|Chapter)\s+([0-9]+|[\u0621-\u064A]+(?:\s+عشر[ة]?)?)\s*[:\-\–\—]\s*(.+?)(?:[\.·•…_\s]+(\d{1,4}))?\s*$",
        line_clean,
        re.IGNORECASE,
    )
    if m_fwd:
        pg_raw = m_fwd.group(1) or m_fwd.group(5)
        pg = int(pg_raw) if pg_raw else None
        raw_num = m_fwd.group(3).strip()
        cnum = _parse_ordinal_or_int(raw_num, fallback_num)
        title = _clean_toc_title(m_fwd.group(4))
        if title:
            return cnum, f"{m_fwd.group(2)} {raw_num}: {title}", pg

    return None


def _match_lesson_heading(line_clean: str) -> Optional[Tuple[str, Optional[int]]]:
    # Forward format with optional InDesign prefix noise (". R ", ".)", etc.):
    # "[page?] [. R )] الدرس <ord/num>: <title> [page?]"
    m_fwd = re.match(
        r"^(?:(\d{1,4})\s+)?(?:[\.\)\(]+|[A-Za-z\.\s]{1,5})*\s*(?:الدرس|Lesson)\s+([^\s:]+)\s*[:\-\–\—]\s*(.+?)(?:[\.·•…_\s]+(\d{1,4}))?\s*$",
        line_clean,
        re.IGNORECASE,
    )
    if m_fwd:
        pg_raw = m_fwd.group(1) or m_fwd.group(4)
        pg = int(pg_raw) if pg_raw else None
        title = _clean_toc_title(m_fwd.group(3))
        if m_fwd.group(3).strip().startswith("R ") or " R " in line_clean[:8]:
            if title.endswith(" في") and not title.endswith(" R"):
                title = f"{title} R"
        if title:
            return title, pg

    # Reverse TOC format (Chapter 7 on p.196): "[page?] <title> : الدرس <ord>"
    m_rev = re.match(
        r"^(?:(\d{1,4})\s+)?(.+?)\s*[:\-\–\—]\s*الدرس\s+(\S+)\s*$",
        line_clean,
    )
    if m_rev:
        pg = int(m_rev.group(1)) if m_rev.group(1) else None
        title = _clean_toc_title(m_rev.group(2))
        if title:
            return title, pg

    # Numbered lesson code format: "[1-1] <title> .... 6" or "1-1: <title> 6"
    m_code = re.match(
        r"^(?:\[?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*\]?)\s*[:\-\s]+(.+?)(?:[\.·•…_\s]+(\d{1,4}))?\s*$",
        line_clean,
    )
    if m_code:
        pg = int(m_code.group(4)) if m_code.group(4) else None
        title = _clean_toc_title(m_code.group(3))
        if title:
            return title, pg

    return None


def _build_lesson_entry(title: str, pdf_page: int, printed_page: str) -> Dict[str, Any]:
    return {
        "title": title[:160],
        "pdfPageNumber": pdf_page,
        "printedPageNumber": printed_page,
        "objectives": [f"فهم وتطبيق المفاهيم الأساسية في درس {title[:100]}."],
        "priorKnowledge": "استرجاع المتطلبات القبلية والمفاهيم التمهيدية المرتبطة بالدرس.",
        "evaluationCriteria": "التحقق من فهم المفاهيم الرئيسة وحل التطبيقات المرتبطة بالدرس.",
    }


def _fallback_extract_structure(pages_text: List[Dict[str, Any]], source_title: str) -> List[Dict[str, Any]]:
    normalized_pages: List[Dict[str, Any]] = []
    printed_to_pdf: Dict[str, int] = {}
    for p in pages_text:
        pno = int(p.get("pdfPageNumber") or 1)
        pr = str(p.get("printedPageNumber") or pno).translate(_AR_INDIC_DIGITS).strip()
        raw_txt = unicodedata.normalize("NFKC", str(p.get("text") or ""))
        norm_txt = normalize_indesign_arabic_ligatures(raw_txt)
        normalized_pages.append({"pdfPageNumber": pno, "printedPageNumber": pr, "text": norm_txt})
        if pr and pr not in printed_to_pdf:
            printed_to_pdf[pr] = pno

    def _resolve_page(printed_val: Optional[int]) -> Optional[int]:
        if printed_val is None:
            return None
        key = str(printed_val)
        if key in printed_to_pdf:
            return printed_to_pdf[key]
        if 1 <= printed_val <= len(normalized_pages):
            return printed_val
        return printed_val

    # 1. Try parsing dedicated Table of Contents pages first
    toc_pages = [p for p in normalized_pages if _has_toc_keyword(p["text"])]
    parsed_chapters: List[Dict[str, Any]] = []
    orphan_nums: List[int] = []
    cur_ch: Optional[Dict[str, Any]] = None

    for p in toc_pages:
        pno_str = str(p["pdfPageNumber"])
        pr_str = str(p["printedPageNumber"])
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in p["text"].splitlines() if ln.strip()]
        collecting_orphans = cur_ch is None
        for idx, ln in enumerate(lines):
            ln_clean = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", ln).translate(_AR_INDIC_DIGITS).strip()
            if idx <= 1 and ln_clean in (pno_str, pr_str):
                continue
            if any(k in ln_clean for k in _TOC_KEYWORDS) and len(ln_clean) < 40:
                continue
            if re.fullmatch(r"\d{1,4}", ln_clean):
                if collecting_orphans and cur_ch is None:
                    orphan_nums.append(int(ln_clean))
                continue
            collecting_orphans = False

            ch_match = _match_chapter_heading(ln_clean, len(parsed_chapters) + 1)
            if ch_match:
                cnum, ctitle, cpg = ch_match
                cur_ch = {
                    "_num": cnum,
                    "title": ctitle,
                    "_rawPage": cpg,
                    "lessons": [],
                }
                parsed_chapters.append(cur_ch)
                continue

            les_match = _match_lesson_heading(ln_clean)
            if les_match and cur_ch is not None:
                ltitle, lpg = les_match
                cur_ch["lessons"].append({"title": ltitle, "_rawPage": lpg})

    # Reattach detached InDesign numeric column (e.g. Ch. 4 on p.195) if unambiguous
    missing_chs = [c for c in parsed_chapters if c["_rawPage"] is None]
    if len(missing_chs) == 1 and orphan_nums and len(orphan_nums) == 1 + len(missing_chs[0]["lessons"]):
        missing_chs[0]["_rawPage"] = orphan_nums[0]
        for les, pval in zip(missing_chs[0]["lessons"], orphan_nums[1:]):
            if les["_rawPage"] is None:
                les["_rawPage"] = pval

    if parsed_chapters and sum(len(c["lessons"]) for c in parsed_chapters) > 0:
        parsed_chapters.sort(key=lambda c: (c["_num"], c["_rawPage"] or 99999))
        output_chapters: List[Dict[str, Any]] = []
        for ch in parsed_chapters:
            ch_pdf_pg = _resolve_page(ch["_rawPage"]) or 1
            ch_printed = str(ch["_rawPage"] or ch_pdf_pg)
            lessons_out: List[Dict[str, Any]] = []
            for l_idx, les in enumerate(ch["lessons"], start=1):
                l_raw = les["_rawPage"]
                if l_raw is None:
                    # Try locating lesson code [ch-les] in body pages
                    code_a = f"[{ch['_num']}-{l_idx}]"
                    code_b = f"]{ch['_num']}-{l_idx}["
                    for bp in normalized_pages:
                        if code_a in bp["text"] or code_b in bp["text"]:
                            l_raw = bp["pdfPageNumber"]
                            break
                l_pdf_pg = _resolve_page(l_raw) or ch_pdf_pg
                lessons_out.append(_build_lesson_entry(les["title"], l_pdf_pg, str(l_raw or l_pdf_pg)))
            if not lessons_out:
                lessons_out.append(_build_lesson_entry(ch["title"], ch_pdf_pg, ch_printed))
            output_chapters.append(
                {
                    "title": ch["title"],
                    "pdfStartPage": ch_pdf_pg,
                    "printedStartPage": ch_printed,
                    "lessons": lessons_out,
                }
            )
        return output_chapters

    # 2. Scan body pages directly for Chapter / Lesson headings when no TOC page exists
    body_chapters: List[Dict[str, Any]] = []
    cur_body_ch: Optional[Dict[str, Any]] = None
    for p in normalized_pages:
        pno = p["pdfPageNumber"]
        pr = p["printedPageNumber"] or str(pno)
        for ln in p["text"].splitlines():
            ln_clean = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", re.sub(r"[ \t]+", " ", ln)).translate(_AR_INDIC_DIGITS).strip()
            if not ln_clean:
                continue
            ch_match = _match_chapter_heading(ln_clean, len(body_chapters) + 1)
            if ch_match:
                cnum, ctitle, _ = ch_match
                if not any(c["title"] == ctitle for c in body_chapters):
                    cur_body_ch = {"_num": cnum, "title": ctitle, "pdfStartPage": pno, "printedStartPage": pr, "lessons": []}
                    body_chapters.append(cur_body_ch)
                continue
            les_match = _match_lesson_heading(ln_clean)
            if les_match:
                ltitle, _ = les_match
                if cur_body_ch is None:
                    cur_body_ch = {"_num": 1, "title": f"فهرس مستخرج — {source_title}", "pdfStartPage": pno, "printedStartPage": pr, "lessons": []}
                    body_chapters.append(cur_body_ch)
                if not any(l["title"] == ltitle for l in cur_body_ch["lessons"]):
                    cur_body_ch["lessons"].append(_build_lesson_entry(ltitle, pno, pr))

    if body_chapters:
        final_body: List[Dict[str, Any]] = []
        for ch in body_chapters:
            if not ch["lessons"]:
                ch["lessons"].append(_build_lesson_entry(ch["title"], ch["pdfStartPage"], ch["printedStartPage"]))
            final_body.append(
                {
                    "title": ch["title"],
                    "pdfStartPage": ch["pdfStartPage"],
                    "printedStartPage": ch["printedStartPage"],
                    "lessons": ch["lessons"],
                }
            )
        return final_body

    # 3. Last-resort fallback from meaningful non-empty page first lines
    fallback_lessons = []
    for p in normalized_pages[:10]:
        txt = p["text"].strip()
        if not txt:
            continue
        first_line = next(
            (ln.strip() for ln in txt.splitlines() if len(ln.strip()) >= 3 and not re.fullmatch(r"[\d\W]+", ln.strip())),
            "",
        )
        if first_line:
            fallback_lessons.append(
                _build_lesson_entry(first_line[:120], p["pdfPageNumber"], p["printedPageNumber"] or str(p["pdfPageNumber"]))
            )
    if not fallback_lessons:
        fallback_lessons = [_build_lesson_entry(f"محتوى مستخرج من {source_title}", 1, "1")]
    return [
        {
            "title": f"فهرس مستخرج — {source_title}",
            "pdfStartPage": normalized_pages[0]["pdfPageNumber"] if normalized_pages else 1,
            "printedStartPage": str(normalized_pages[0].get("printedPageNumber", "1")) if normalized_pages else "1",
            "lessons": fallback_lessons,
        }
    ]


def extract_chapters_and_lessons_with_ai(
    pages_text: List[Dict[str, Any]],
    context_snap: Dict[str, Any],
    source_title: str,
) -> Dict[str, Any]:
    subject = context_snap.get("subject") or "المادة"
    grade = context_snap.get("grade") or ""
    selected_pages = _select_structural_pages(pages_text, max_pages=24)

    formatted_sections: List[str] = []
    for p in selected_pages:
        raw_txt = str(p.get("text") or "")
        cleaned_txt = _clean_structural_page_text(raw_txt)
        budget = 6000 if _is_toc_page_text(raw_txt) else 2200
        formatted_sections.append(
            f"--- PDF Page {p.get('pdfPageNumber')} (Printed {p.get('printedPageNumber')}) ---\n{cleaned_txt[:budget]}"
        )
    combined_pages = "\n\n".join(formatted_sections)

    system_prompt = (
        "أنت محلل مناهج تعليمية. استخرج بنية جميع الفصول والدروس الموجودة فعليًا في صفحات الفهرس/المحتويات ومقدمات الفصول فقط دون اختلاق دروس غير موجودة. "
        "انتبه لأرقام الصفحات المذكورة أمام كل فصل ودرس في الفهرس. أعد JSON فقط بالصيغة: "
        "{\"chapters\": [{\"title\": \"...\", \"pdfStartPage\": 1, \"printedStartPage\": \"1\", "
        "\"lessons\": [{\"title\": \"...\", \"pdfPageNumber\": 1, \"printedPageNumber\": \"1\", "
        "\"objectives\": [\"...\"], \"priorKnowledge\": \"...\", \"evaluationCriteria\": \"...\"}]}]}."
    )
    user_prompt = f"الكتاب: {source_title} | المادة: {subject} | الصف: {grade}\n\nالنصوص المستخرجة:\n{combined_pages}"

    parsed, model_used = call_llm_json(system_prompt, user_prompt, timeout_sec=35.0)
    chapters = (parsed or {}).get("chapters") if isinstance(parsed, dict) else None
    if isinstance(chapters, list) and len(chapters) > 0:
        return {"chapters": chapters, "modelUsed": model_used}

    return {
        "chapters": _fallback_extract_structure(pages_text, source_title),
        "modelUsed": "deterministic_fallback",
    }
