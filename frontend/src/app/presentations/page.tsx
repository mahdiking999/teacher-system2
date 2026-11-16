"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function PresentationsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [slides, setSlides] = useState<any[]>([]);
  const [activeSlideIdx, setActiveSlideIdx] = useState<number>(0);
  const [presTitle, setPresTitle] = useState<string>("عرض الدرس");
  const [textDirection, setTextDirection] = useState<string>("rtl");
  const [layoutStyle, setLayoutStyle] = useState<string>("title_and_content");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [lastExportLink, setLastExportLink] = useState<{ url: string; fileName: string } | null>(null);
  const [aiGenerating, setAiGenerating] = useState<boolean>(false);
  const [aiSlidesCount, setAiSlidesCount] = useState<number>(6);
  const [aiCustomPrompt, setAiCustomPrompt] = useState<string>("");

  const defaultLangDir = useCallback(() => {
    const lang = (activeContext?.language || "ar").toLowerCase();
    return lang.startsWith("en") || lang.startsWith("fr") ? "ltr" : "rtl";
  }, [activeContext?.language]);

  const bindPlanSlides = useCallback(
    (pln: any, keepSlideIdx?: number) => {
      const settings = pln.presentationSettings || {};
      setSelectedPlanId(pln.id);
      setPresTitle(settings.title || pln.title || "عرض الدرس");
      setTextDirection(settings.textDirection || defaultLangDir());
      setLayoutStyle(settings.layoutStyle || "title_and_content");

      const defaultSlides =
        pln.slides && pln.slides.length > 0
          ? pln.slides
          : [
              {
                order: 1,
                title: pln.title || "عرض الدرس",
                content: `${activeContext?.subject || "المادة"} · ${activeContext?.grade || ""} · ${activeContext?.country || ""}`,
              },
              {
                order: 2,
                title: "أهداف الحصة",
                content: (pln.objectives || []).join("\n") || "أهداف الدرس القابلة للملاحظة والقياس.",
              },
              {
                order: 3,
                title: "ناقش طريقة التفكير",
                content:
                  "أدخل مهمة مناسبة للمادة بعد مراجعة المصدر، ثم اطلب من الطلاب تفسير خطواتهم.\nسؤال النقاش: ما سبب اختيارك لهذه الخطوة؟",
              },
              {
                order: 4,
                title: "قارن الاستراتيجيات",
                content: "بالأقلام الملوّنة والبطاقات: ميّز خطوات كل طريقة ثم ناقش أوجه التشابه والاختلاف.",
              },
              {
                order: 5,
                title: "تقويم ختامي",
                content: pln.formativeAssessment || "اطلب من الطالب شرح اختياره لإحدى الخطوات، ثم سجّل ملاحظة مرتبطة بالهدف.",
              },
            ];
      setSlides(defaultSlides);
      if (typeof keepSlideIdx === "number" && keepSlideIdx >= 0) {
        setActiveSlideIdx(Math.min(keepSlideIdx, defaultSlides.length - 1));
      } else {
        setActiveSlideIdx(Math.min(2, defaultSlides.length - 1));
      }
    },
    [activeContext, defaultLangDir]
  );

  const loadPlans = useCallback(
    async (keepId?: string, keepSlideIdx?: number, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setSelectedPlanId("");
        setSlides([]);
        setPresTitle("عرض الدرس");
        setTextDirection("rtl");
        setLayoutStyle("title_and_content");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const res = await apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}`);
        if (isCancelled && isCancelled()) return;
        const list = res.items || [];
        setPlans(list);
        setSelectedPlanId((prev) => {
          const targetId =
            (keepId && list.some((p: any) => p.id === keepId) && keepId) ||
            (urlPlanId && list.some((p: any) => p.id === urlPlanId) && urlPlanId) ||
            (prev && list.some((p: any) => p.id === prev) && prev) ||
            list[0]?.id ||
            "";
          const found = list.find((p: any) => p.id === targetId) || null;
          if (found) {
            bindPlanSlides(found, keepSlideIdx);
            return found.id;
          }
          setSlides([]);
          setPresTitle("عرض الدرس");
          setTextDirection(defaultLangDir());
          setLayoutStyle("title_and_content");
          return "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل الخطط والعروض.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch, urlPlanId, bindPlanSlides, defaultLangDir]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setAiCustomPrompt("");
    setLastExportLink(null);
    setSelectedPlanId("");
    loadPlans(undefined, undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentPlan = plans.find((p) => p.id === selectedPlanId) || null;
  const activeSlide = slides[activeSlideIdx] || { title: "شريحة", content: "" };
  const slideLines = String(activeSlide.content || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const handleSaveSlidesToPlan = async (): Promise<string | null> => {
    if (!currentPlan) return null;
    setSaving(true);
    setErrorMsg("");
    setFeedback("");
    try {
      const normalizedSlides = slides.map((s, idx) => ({ ...s, order: idx + 1 }));
      const updated = await apiFetch(`/api/plans/${currentPlan.id}`, {
        method: "PUT",
        body: JSON.stringify({
          ...currentPlan,
          slides: normalizedSlides,
          presentationSettings: {
            title: presTitle.trim() || currentPlan.title,
            slidesCount: normalizedSlides.length,
            textDirection,
            layoutStyle,
            companionTools: (activeContext?.selectedTools || []).join("، "),
          },
          expectedVersion: currentPlan.version,
        }),
      });
      setFeedback(`تم حفظ بنية الشرائح وإعدادات العرض في الخطة (v${updated.version}).`);
      await loadPlans(updated.id, activeSlideIdx);
      return updated.id;
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ الشرائح وإعدادات العرض.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleExportPptx = async () => {
    if (!currentPlan) return;
    setExporting(true);
    setLastExportLink(null);
    try {
      const savedId = await handleSaveSlidesToPlan();
      if (!savedId) {
        setExporting(false);
        return;
      }
      const res = await apiFetch("/api/exports", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          planId: savedId,
          exportFormat: "pptx",
        }),
      });
      setLastExportLink({ url: res.downloadUrl, fileName: res.fileName });
      window.open(res.downloadUrl, "_blank");
      setFeedback(
        `تم توليد ملف العرض (${res.fileName}) بصيغة OOXML PPTX حقيقية بنصوص وعناصر قابلة للتحرير في PowerPoint!`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر توليد ملف PPTX.");
    } finally {
      setExporting(false);
    }
  };

  const handleSaveAndGoToExportPackage = async () => {
    const savedId = await handleSaveSlidesToPlan();
    if (savedId) {
      router.push(`/export-package?planId=${encodeURIComponent(savedId)}`);
    }
  };

  const handleAiGenerateSlides = async () => {
    if (!currentPlan) return;
    setAiGenerating(true);
    setFeedback("");
    setErrorMsg("");
    try {
      const res = await apiFetch(`/api/plans/${currentPlan.id}/ai-generate-slides`, {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          slidesCount: aiSlidesCount,
          customInstructions: aiCustomPrompt,
        }),
      });
      if (res?.plan?.slides) {
        setSlides(res.plan.slides);
      }
      await loadPlans(currentPlan.id, 0);
      const count = res?.slidesCount ?? res?.plan?.slides?.length ?? aiSlidesCount;
      const model = res?.modelUsed || "NVIDIA NIM";
      setFeedback(`تم توليد ${count} شرائح ذكية بنجاح عبر (${model}). يمكنك تعديلها أو تصدير PPTX فورًا.`);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر توليد الشرائح بالذكاء الاصطناعي.");
    } finally {
      setAiGenerating(false);
    }
  };

  const moveSlide = (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= slides.length) return;
    const next = [...slides];
    const tmp = next[idx];
    next[idx] = next[target];
    next[target] = tmp;
    setSlides(next.map((s, i) => ({ ...s, order: i + 1 })));
    setActiveSlideIdx(target);
  };

  const deleteSlide = (idx: number) => {
    if (slides.length <= 1) return;
    const next = slides.filter((_, i) => i !== idx).map((s, i) => ({ ...s, order: i + 1 }));
    setSlides(next);
    setActiveSlideIdx((prev) => Math.min(prev > idx ? prev - 1 : prev, next.length - 1));
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / العروض التقديمية
      </div>
      <h1 className="page-title">العروض التقديمية</h1>
      <p className="page-subtitle">
        جهّز بنية عرض لمادة {activeContext?.subject || "المادة"} يمكن تحرير محتواه وعناصره النصية في PowerPoint بعد التصدير.
      </p>

      <div className="info-banner">
        <span>
          ⓘ تُصدّر الشرائح كعناصر نصية وأشكال OOXML قابلة للتحرير الفعلي في PowerPoint مع احترام اتجاه اللغة (RTL/LTR).
        </span>
      </div>

      <WorkflowStepper activeStep={9} />

      <div className="warning-banner">
        <span>
          ⚠ العرض مرتبط بـ «{currentPlan?.title || "الخطة المحددة"}»، ومصدر المنهج يُوسم بحسب حالة توثيقه.
        </span>
      </div>

      {feedback && (
        <div className="info-banner" style={{ borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
          <span>✓ {feedback}</span>
          {lastExportLink && (
            <a href={lastExportLink.url} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.78rem" }}>
              تنزيل {lastExportLink.fileName}
            </a>
          )}
        </div>
      )}

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 16px", color: "var(--text-secondary)" }}>
          جارٍ تحميل الشرائح والخطط...
        </div>
      ) : plans.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "44px 16px" }}>
          <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🖥</div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: "8px" }}>لا توجد خطط محفوظة بعد لإنشاء عروض تقديمية</h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
            أنشئ خطة درس من صفحة الخطة اليومية ليتم توليد شرائح العرض التقديمي القابلة للتحرير تلقائيًا.
          </p>
          <Link href="/daily-plan" className="btn btn-primary">
            + إعداد أول خطة درس
          </Link>
        </div>
      ) : (
        <>
          {/* Top Action Bar matching `العروض التقديمية.png` */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "16px" }}>
            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              <button type="button" className="btn btn-primary" disabled={exporting || saving} onClick={handleExportPptx}>
                🖥 {exporting ? "جارٍ تجهيز ملف PPTX..." : "إعداد وتنزيل عرض PPTX قابل للتحرير"}
              </button>
              <button type="button" className="btn btn-secondary" disabled={saving || exporting} onClick={handleSaveSlidesToPlan}>
                {saving ? "جارٍ الحفظ..." : "↻ تحديث وحفظ المعاينة"}
              </button>
              <span className="badge badge-success">{slides.length} شرائح · معاينة حية</span>
            </div>

            <select
              aria-label="اختيار الخطة للعرض التقديمي"
              className="form-select"
              style={{ width: "auto" }}
              value={selectedPlanId}
              onChange={(e) => {
                const found = plans.find((p) => p.id === e.target.value);
                if (found) bindPlanSlides(found);
              }}
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          </div>

          <div className="card" style={{ borderColor: "rgba(23, 107, 82, 0.28)", backgroundColor: "#fcfefd" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "10px" }}>
              <div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: 800 }}>✨ توليد الشرائح الذكي عبر OmniRoute / NVIDIA NIM</h3>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                  ينشئ شرائح عرض تعليمية متكاملة انطلاقًا من أهداف الخطة ومراحلها مع قابلية التحرير الفوري قبل التصدير.
                </p>
              </div>
              <span className="badge badge-neutral">{currentPlan?.title || "الخطة المحددة"}</span>
            </div>

            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              <select
                aria-label="عدد الشرائح المطلوب توليدها"
                className="form-select"
                style={{ width: "auto", minWidth: "130px" }}
                value={aiSlidesCount}
                onChange={(e) => setAiSlidesCount(Number(e.target.value))}
                disabled={aiGenerating}
              >
                <option value={5}>5 شرائح</option>
                <option value={6}>6 شرائح</option>
                <option value={7}>7 شرائح</option>
                <option value={8}>8 شرائح</option>
                <option value={10}>10 شرائح</option>
              </select>

              <input
                type="text"
                aria-label="ملاحظات إضافية للشرائح"
                className="form-input"
                style={{ flex: "1 1 260px" }}
                placeholder="ملاحظات إضافية للشرائح (اختياري): ركّز على الأمثلة الحياتية..."
                value={aiCustomPrompt}
                onChange={(e) => setAiCustomPrompt(e.target.value)}
                disabled={aiGenerating}
              />

              <button
                type="button"
                className="btn btn-primary"
                disabled={aiGenerating || !currentPlan}
                onClick={handleAiGenerateSlides}
              >
                {aiGenerating ? "جارٍ توليد الشرائح عبر NVIDIA NIM..." : "✨ توليد شرائح الدرس بالذكاء الاصطناعي"}
              </button>
            </div>
          </div>

          {/* 3-Column Layout matching `العروض التقديمية.png` */}
          <div className="three-col-presentation-grid">
            {/* Column 1: Slide Structure List */}
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: 800 }}>بنية الشرائح</h3>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>قابلة للترتيب والتحرير والحذف</p>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "4px 8px", fontSize: "0.76rem" }}
                  onClick={() => {
                    const next = [
                      ...slides,
                      { order: slides.length + 1, title: `شريحة ${slides.length + 1}`, content: "محتوى جديد قابل للتحرير." },
                    ];
                    setSlides(next);
                    setActiveSlideIdx(next.length - 1);
                  }}
                >
                  + شريحة
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {slides.map((s, idx) => {
                  const isCurrent = idx === activeSlideIdx;
                  return (
                    <div
                      key={idx}
                      onClick={() => setActiveSlideIdx(idx)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setActiveSlideIdx(idx);
                        }
                      }}
                      style={{
                        padding: "10px 12px",
                        borderRadius: "10px",
                        border: isCurrent ? "2px solid var(--primary-green)" : "1px solid var(--border-color)",
                        backgroundColor: isCurrent ? "var(--primary-tint-bg)" : "#fbfcfb",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "2px", gap: "4px" }}>
                        <span>شريحة {idx + 1}</span>
                        <span style={{ display: "inline-flex", gap: "2px" }}>
                          <button
                            type="button"
                            disabled={idx === 0}
                            aria-label={`نقل شريحة ${idx + 1} للأعلى`}
                            onClick={(e) => {
                              e.stopPropagation();
                              moveSlide(idx, -1);
                            }}
                            style={{ border: "none", background: "transparent", cursor: idx === 0 ? "not-allowed" : "pointer", paddingInline: "3px" }}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            disabled={idx === slides.length - 1}
                            aria-label={`نقل شريحة ${idx + 1} للأسفل`}
                            onClick={(e) => {
                              e.stopPropagation();
                              moveSlide(idx, 1);
                            }}
                            style={{
                              border: "none",
                              background: "transparent",
                              cursor: idx === slides.length - 1 ? "not-allowed" : "pointer",
                              paddingInline: "3px",
                            }}
                          >
                            ↓
                          </button>
                          {slides.length > 1 && (
                            <button
                              type="button"
                              aria-label={`حذف شريحة ${idx + 1}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteSlide(idx);
                              }}
                              style={{
                                border: "none",
                                background: "transparent",
                                color: "var(--blocker-text)",
                                cursor: "pointer",
                                paddingInline: "3px",
                                fontWeight: 700,
                              }}
                            >
                              ✕
                            </button>
                          )}
                        </span>
                      </div>
                      <div style={{ fontWeight: 800, fontSize: "0.9rem" }}>{s.title}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Column 2: Selected Slide Preview + Editable Content Fields */}
            <div>
              <div className="card">
                <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "2px" }}>معاينة الشريحة المحدّدة</h3>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                  شريحة {activeSlideIdx + 1} من {slides.length} ·{" "}
                  {layoutStyle === "comparison" ? "تخطيط مقارنة (عمودان)" : "تخطيط عنوان ومحتوى"} · مادة {activeContext?.subject}
                </p>

                {/* Visual Slide Canvas matching `العروض التقديمية.png` */}
                <div
                  dir={textDirection}
                  style={{
                    border: "1px solid var(--border-color)",
                    borderRadius: "12px",
                    padding: "22px",
                    backgroundColor: "#ffffff",
                    minHeight: "230px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      paddingBottom: "8px",
                      borderBottom: "2px solid var(--primary-green)",
                      fontSize: "0.78rem",
                      color: "var(--primary-green)",
                      fontWeight: 700,
                    }}
                  >
                    <span>
                      مُعلّم {activeContext?.subject} · {presTitle}
                    </span>
                    <span>
                      {String(activeSlideIdx + 1).padStart(2, "0")} / {String(slides.length).padStart(2, "0")}
                    </span>
                  </div>

                  <div style={{ marginBlock: "16px" }}>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: 800, marginBottom: "10px" }}>{activeSlide.title}</h2>
                    {layoutStyle === "comparison" ? (
                      <div className="equal-split-grid" style={{ gap: "10px" }}>
                        <div style={{ padding: "12px", borderRadius: "10px", backgroundColor: "#f6f7f5", border: "1px solid var(--border-color)" }}>
                          <div style={{ fontSize: "0.76rem", fontWeight: 800, color: "var(--text-secondary)", marginBottom: "6px" }}>
                            المحور الأول
                          </div>
                          <div style={{ fontSize: "0.9rem", whiteSpace: "pre-line" }}>
                            {slideLines.slice(0, Math.ceil(slideLines.length / 2)).join("\n") || "—"}
                          </div>
                        </div>
                        <div style={{ padding: "12px", borderRadius: "10px", backgroundColor: "var(--primary-tint-bg)", border: "1px solid rgba(23,107,82,0.25)" }}>
                          <div style={{ fontSize: "0.76rem", fontWeight: 800, color: "var(--primary-green)", marginBottom: "6px" }}>
                            المحور المقابل / التفاعل
                          </div>
                          <div style={{ fontSize: "0.9rem", color: "var(--primary-green)", whiteSpace: "pre-line" }}>
                            {slideLines.slice(Math.ceil(slideLines.length / 2)).join("\n") || "—"}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {slideLines.length > 0 ? (
                          <>
                            <p style={{ fontSize: "0.92rem", color: "var(--text-secondary)", whiteSpace: "pre-line" }}>
                              {slideLines[0]}
                            </p>
                            {slideLines.length > 1 && (
                              <div
                                style={{
                                  padding: "12px 16px",
                                  borderRadius: "10px",
                                  backgroundColor: "var(--primary-tint-bg)",
                                  color: "var(--primary-green)",
                                  fontWeight: 700,
                                  fontSize: "0.9rem",
                                  whiteSpace: "pre-line",
                                }}
                              >
                                {slideLines.slice(1).join("\n")}
                              </div>
                            )}
                          </>
                        ) : (
                          <p style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}>أدخل محتوى الشريحة أدناه...</p>
                        )}
                      </div>
                    )}
                  </div>

                  <div style={{ fontSize: "0.74rem", color: "var(--warning-text)" }}>
                    {currentPlan?.provenanceLabel || "محتوى تجريبي — غير موثّق"}
                  </div>
                </div>
              </div>

              <div className="card">
                <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "2px" }}>تحرير محتوى الشريحة</h3>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                  حقول نصية تتحول إلى أشكال وعناصر نصية قابلة للتحرير في ملف PPTX المصدّر
                </p>

                <div className="form-group">
                  <label className="form-label">العنوان</label>
                  <input
                    className="form-input"
                    value={activeSlide.title || ""}
                    onChange={(e) => {
                      const next = [...slides];
                      next[activeSlideIdx] = { ...next[activeSlideIdx], title: e.target.value };
                      setSlides(next);
                    }}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">المحتوى · نص قابل للتحرير (كل سطر فقرة)</label>
                  <textarea
                    className="form-textarea"
                    value={activeSlide.content || ""}
                    onChange={(e) => {
                      const next = [...slides];
                      next[activeSlideIdx] = { ...next[activeSlideIdx], content: e.target.value };
                      setSlides(next);
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Column 3: Presentation Settings matching `العروض التقديمية.png` */}
            <div className="card">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "12px" }}>إعدادات العرض</h3>

              <div className="form-group">
                <label className="form-label">عنوان العرض</label>
                <input
                  className="form-input"
                  value={presTitle}
                  onChange={(e) => setPresTitle(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">عدد الشرائح</label>
                <input className="form-input" readOnly value={`${slides.length} شرائح`} />
              </div>

              <div className="form-group">
                <label className="form-label">اتجاه النص</label>
                <select
                  className="form-select"
                  value={textDirection}
                  onChange={(e) => setTextDirection(e.target.value)}
                >
                  <option value="rtl">العربية · من اليمين إلى اليسار (RTL)</option>
                  <option value="ltr">من اليسار إلى اليمين (LTR)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">تخطيط الشريحة في المعاينة</label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <button
                    type="button"
                    className={`btn ${layoutStyle === "title_and_content" ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setLayoutStyle("title_and_content")}
                    style={{ padding: "8px", fontSize: "0.8rem" }}
                  >
                    عنوان ومحتوى
                  </button>
                  <button
                    type="button"
                    className={`btn ${layoutStyle === "comparison" ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setLayoutStyle("comparison")}
                    style={{ padding: "8px", fontSize: "0.8rem" }}
                  >
                    مقارنة
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">الوسائل المصاحبة</label>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                  {(activeContext?.selectedTools || []).join("، ") || "لا توجد وسائل محددة"}. يمكن استخدام الشرائح كمرجع تحضير إذا لم يتوفر جهاز عرض.
                </p>
                <span className="badge badge-success">محتوى مقصود للتحرير</span>
              </div>

              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                تُحفظ النصوص وعناصر المحتوى في ملف PPTX كأشكال نصية قابلة للتحرير الكامل، وليست صورًا مسطحة.
              </p>
            </div>
          </div>

          <div className="info-banner">
            <span>
              ⓘ النصوص التربوية أماكن مخصّصة لمحتوى يراجعه المعلم. عند وجود معادلات رياضية تُفصل باتجاه LTR مستقل.
            </span>
          </div>

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveAndGoToExportPackage}
              disabled={saving || exporting}
            >
              ← حفظ وإضافة العرض إلى الحزمة والتصدير
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleSaveSlidesToPlan} disabled={saving || exporting}>
              {saving ? "جارٍ الحفظ..." : "حفظ إعدادات العرض"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default function PresentationsPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <PresentationsContent />
    </Suspense>
  );
}
