import base64
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://100.120.103.82:20128/v1").rstrip("/")
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY", "sk-da9c432387749a32-7f7b6c-b16fecef").strip()
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


def get_ai_status() -> Dict[str, Any]:
    return {
        "omnirouteBaseUrl": os.getenv("OMNIROUTE_BASE_URL", OMNIROUTE_BASE_URL).rstrip("/"),
        "tailscaleAuthKeyConfigured": bool(os.getenv("TAILSCALE_AUTHKEY", "").strip()),
        "tailscaleProxy": os.getenv("TAILSCALE_HTTP_PROXY", "").strip() or None,
        "directNvidiaConfigured": len(_get_nvidia_keys()) > 0,
        "textModels": TEXT_MODELS,
        "visionModels": VISION_MODELS,
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
        "max_tokens": 2200,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
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
    omni_base = os.getenv("OMNIROUTE_BASE_URL", OMNIROUTE_BASE_URL).rstrip("/")
    omni_key = os.getenv("OMNIROUTE_API_KEY", OMNIROUTE_API_KEY).strip()
    ts_proxy = os.getenv("TAILSCALE_HTTP_PROXY", "").strip() or None

    if omni_base:
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
            "extractedText": str(parsed["extractedText"]).strip(),
            "printedPageNumber": str(parsed.get("printedPageNumber") or page_number).strip(),
            "notes": str(parsed.get("notes") or "").strip(),
            "modelUsed": model_used,
        }

    return {
        "extractedText": fallback_text.strip() or f"[صفحة {page_number}: لم يتسنّ الاستخراج التلقائي — يرجى المراجعة اليدوية]",
        "printedPageNumber": str(page_number),
        "notes": "تم اعتماد النص المستخرج محليًا عبر PyMuPDF." if fallback_text.strip() else "تعذر الوصول لنموذج الرؤية الذكية؛ الصفحة بحاجة لتفريغ يدوي.",
        "modelUsed": model_used,
    }


def extract_chapters_and_lessons_with_ai(
    pages_text: List[Dict[str, Any]],
    context_snap: Dict[str, Any],
    source_title: str,
) -> Dict[str, Any]:
    subject = context_snap.get("subject") or "المادة"
    grade = context_snap.get("grade") or ""
    combined_pages = "\n\n".join(
        f"--- PDF Page {p.get('pdfPageNumber')} (Printed {p.get('printedPageNumber')}) ---\n{str(p.get('text') or '')[:900]}"
        for p in pages_text[:20]
    )

    system_prompt = (
        "أنت محلل مناهج تعليمية. استخرج بنية الفصول والدروس الموجودة فعليًا في صفحات الكتاب فقط دون اختلاق دروس غير موجودة. "
        "أعد JSON فقط بالصيغة: "
        "{\"chapters\": [{\"title\": \"...\", \"pdfStartPage\": 1, \"printedStartPage\": \"1\", "
        "\"lessons\": [{\"title\": \"...\", \"pdfPageNumber\": 1, \"printedPageNumber\": \"1\", "
        "\"objectives\": [\"...\"], \"priorKnowledge\": \"...\", \"evaluationCriteria\": \"...\"}]}]}."
    )
    user_prompt = f"الكتاب: {source_title} | المادة: {subject} | الصف: {grade}\n\nالنصوص المستخرجة:\n{combined_pages}"

    parsed, model_used = call_llm_json(system_prompt, user_prompt, timeout_sec=24.0)
    chapters = (parsed or {}).get("chapters") if isinstance(parsed, dict) else None
    if isinstance(chapters, list) and len(chapters) > 0:
        return {"chapters": chapters, "modelUsed": model_used}

    # Deterministic fallback from extracted page headings
    fallback_lessons = []
    for p in pages_text[:10]:
        txt = str(p.get("text") or "").strip()
        if not txt:
            continue
        first_line = next((ln.strip() for ln in txt.splitlines() if len(ln.strip()) >= 3), "")
        if first_line:
            fallback_lessons.append(
                {
                    "title": first_line[:120],
                    "pdfPageNumber": p.get("pdfPageNumber", 1),
                    "printedPageNumber": str(p.get("printedPageNumber") or p.get("pdfPageNumber", 1)),
                    "objectives": [f"استيعاب المفاهيم الواردة في: {first_line[:80]}"],
                    "priorKnowledge": "المعارف التمهيدية للوحدة.",
                    "evaluationCriteria": "التحقق من فهم المفاهيم الرئيسة في الصفحة.",
                }
            )
    if not fallback_lessons:
        fallback_lessons = [
            {
                "title": f"محتوى مستخرج من {source_title}",
                "pdfPageNumber": 1,
                "printedPageNumber": "1",
                "objectives": ["مراجعة أهداف الدرس من الكتاب المدرسي."],
                "priorKnowledge": "",
                "evaluationCriteria": "تقييم تكويني وفق أهداف الدرس.",
            }
        ]
    return {
        "chapters": [
            {
                "title": f"فهرس مستخرج — {source_title}",
                "pdfStartPage": pages_text[0].get("pdfPageNumber", 1) if pages_text else 1,
                "printedStartPage": str(pages_text[0].get("printedPageNumber", "1")) if pages_text else "1",
                "lessons": fallback_lessons,
            }
        ],
        "modelUsed": "deterministic_fallback",
    }
