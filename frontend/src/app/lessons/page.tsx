"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function LessonsContent() {
  const searchParams = useSearchParams();
  const urlLessonId = searchParams.get("lessonId") || "";
  const { activeContext, activeContextId, apiFetch } = useTeacherApp();

  const [lessons, setLessons] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [selectedLessonId, setSelectedLessonId] = useState<string>("");
  const [searchQ, setSearchQ] = useState<string>("");
  const [chapterFilter, setChapterFilter] = useState<string>("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  // Editable form state for selected lesson
  const [title, setTitle] = useState<string>("");
  const [objectives, setObjectives] = useState<string[]>([""]);
  const [priorKnowledge, setPriorKnowledge] = useState<string>("");
  const [evaluationCriteria, setEvaluationCriteria] = useState<string>("");
  const [printedPage, setPrintedPage] = useState<string>("");
  const [pdfPageNumber, setPdfPageNumber] = useState<string>("");
  const [sourceId, setSourceId] = useState<string>("");
  const [chapterId, setChapterId] = useState<string>("");

  const selectLessonObj = useCallback((les: any | null) => {
    if (!les) {
      setSelectedLessonId("");
      setTitle("");
      setObjectives([""]);
      setPriorKnowledge("");
      setEvaluationCriteria("");
      setPrintedPage("");
      setPdfPageNumber("");
      setSourceId("");
      setChapterId("");
      return;
    }
    setSelectedLessonId(les.id);
    setTitle(les.title || "");
    setObjectives(les.objectives && les.objectives.length > 0 ? les.objectives : [""]);
    setPriorKnowledge(les.priorKnowledge || "");
    setEvaluationCriteria(les.evaluationCriteria || "");
    setPrintedPage(les.printedPageNumber || "");
    setPdfPageNumber(les.pdfPageNumber ? String(les.pdfPageNumber) : "");
    setSourceId(les.sourceId || "");
    setChapterId(les.chapterId || "");
  }, []);

  const loadLessons = useCallback(
    async (keepId?: string, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setLessons([]);
        setSources([]);
        selectLessonObj(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [lRes, sRes] = await Promise.all([
          apiFetch(`/api/lessons?contextId=${encodeURIComponent(activeContextId)}&q=${encodeURIComponent(searchQ)}`),
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const list = lRes.items || [];
        const sList = sRes.items || [];
        setLessons(list);
        setSources(sList);

        setSelectedLessonId((prev) => {
          const preferredId = keepId || urlLessonId || prev;
          const found = list.find((l: any) => l.id === preferredId) || list[0] || null;
          selectLessonObj(found);
          return found ? found.id : "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل الدروس من الخادم.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, searchQ, urlLessonId, apiFetch, selectLessonObj]
  );

  // Reset filters & feedback when switching educational context
  useEffect(() => {
    setSaveMessage("");
    setErrorMsg("");
    setSearchQ("");
    setChapterFilter("all");
    setSelectedLessonId("");
  }, [activeContextId]);

  useEffect(() => {
    let cancelled = false;
    loadLessons(undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadLessons]);

  const allChapters = sources.flatMap((s: any) =>
    (s.chapters || []).map((c: any) => ({ ...c, sourceTitle: s.title, sourceId: s.id }))
  );

  const visibleLessons = lessons.filter((l) => chapterFilter === "all" || l.chapterId === chapterFilter);
  const currentLesson = lessons.find((l) => l.id === selectedLessonId) || null;
  const linkedSource = sources.find((s) => s.id === (sourceId || currentLesson?.sourceId)) || null;
  const linkedChapter = allChapters.find((c: any) => c.id === (chapterId || currentLesson?.chapterId)) || null;
  const isLinkedSourceVerified = linkedSource?.verificationStatus === "human_verified";

  const handleSaveLesson = async () => {
    if (!currentLesson) return;
    setErrorMsg("");
    setSaveMessage("");

    const parsedPdf = pdfPageNumber.trim() ? Number.parseInt(pdfPageNumber.trim(), 10) : null;
    if (pdfPageNumber.trim() && (Number.isNaN(parsedPdf) || (parsedPdf ?? 0) < 1)) {
      setErrorMsg("رقم صفحة PDF يجب أن يكون عددًا صحيحًا موجبًا.");
      return;
    }

    // Never upgrade an unverified lesson to `documented_source` unless its linked source is human_verified!
    const nextContentOrigin =
      isLinkedSourceVerified && (printedPage.trim() || parsedPdf)
        ? "documented_source"
        : currentLesson.contentOrigin === "documented_source" && isLinkedSourceVerified
        ? "documented_source"
        : "authored_example";

    setSaving(true);
    try {
      const updated = await apiFetch(`/api/lessons/${currentLesson.id}`, {
        method: "PUT",
        body: JSON.stringify({
          contextId: activeContextId,
          sourceId: sourceId || null,
          chapterId: chapterId || null,
          title: title.trim() || currentLesson.title,
          codeOrOrder: currentLesson.codeOrOrder,
          pdfPageNumber: parsedPdf,
          printedPageNumber: printedPage.trim(),
          contentOrigin: nextContentOrigin,
          objectives: objectives.filter((o) => o.trim() !== ""),
          priorKnowledge,
          activities: currentLesson.activities || [],
          questionsAndSolutions: currentLesson.questionsAndSolutions || [],
          evaluationCriteria,
          keyTermsOrQuotes: currentLesson.keyTermsOrQuotes || [],
          expectedVersion: currentLesson.version,
        }),
      });
      setSaveMessage("تم حفظ تعديلات الدرس في قاعدة البيانات بنجاح.");
      await loadLessons(updated.id);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ تعديلات الدرس.");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateNewLesson = async () => {
    setErrorMsg("");
    setSaveMessage("");
    setSaving(true);
    try {
      const defaultSourceId = sources[0]?.id || null;
      const defaultChapterId = chapterFilter !== "all" ? chapterFilter : null;
      const created = await apiFetch("/api/lessons", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          sourceId: defaultSourceId,
          chapterId: defaultChapterId,
          title: `درس جديد ${lessons.length + 1}`,
          codeOrOrder: String(lessons.length + 1),
          objectives: ["أن يحقق المتعلم الهدف التعليمي الأول للدرس."],
          priorKnowledge: "مراجعة المتطلبات السابقة للدرس.",
          evaluationCriteria: "معيار تقييم واضح ومرتبط بالهدف.",
        }),
      });
      setSaveMessage("تم إنشاء درس جديد في السياق الحالي.");
      await loadLessons(created.id);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر إنشاء درس جديد.");
    } finally {
      setSaving(false);
    }
  };

  const handleDuplicateLesson = async () => {
    if (!currentLesson) return;
    setErrorMsg("");
    setSaveMessage("");
    setSaving(true);
    try {
      const copied = await apiFetch(
        `/api/lessons/${currentLesson.id}/duplicate?contextId=${encodeURIComponent(activeContextId)}`,
        { method: "POST" }
      );
      setSaveMessage(`تم نسخ الدرس إلى «${copied.title}».`);
      await loadLessons(copied.id);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر نسخ الدرس.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / اختيار الدرس
      </div>
      <h1 className="page-title">اختيار الدرس</h1>
      <p className="page-subtitle">
        حدّد درسًا من السجل، ثم خصّص أهدافه ومعارفه السابقة ومعايير تقويمه قبل اختيار الوسائل.
      </p>

      <div className="info-banner">
        <span>
          ⓘ يمكنك إنشاء درس جديد، أو تعديل الدرس الحالي، أو نسخه، ويُحفظ التعديل مباشرة في قاعدة بيانات FastAPI.
        </span>
      </div>

      <WorkflowStepper activeStep={3} />

      <div className={currentLesson?.contentOrigin === "documented_source" ? "info-banner" : "warning-banner"}>
        <span>
          {currentLesson?.contentOrigin === "documented_source" ? "✓" : "⚠"}{" "}
          {currentLesson?.provenanceLabel || "مثال توضيحي غير موثق من الكتاب"}
          {linkedSource ? ` · المصدر: ${linkedSource.title}` : " · غير مربوط بملف مصدر موثق بعد"}
        </span>
      </div>

      {saveMessage && (
        <div className="info-banner" style={{ borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
          <span>✓ {saveMessage}</span>
        </div>
      )}

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {/* Main Split matching `اختيار الدرس.png`: Available Lessons List & Selected Lesson Details */}
      <div className="equal-split-grid">
        {/* Right Column in RTL: Available Lessons */}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
            <div>
              <h3 style={{ fontSize: "1.15rem", fontWeight: 800 }}>الدروس المتاحة</h3>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                {visibleLessons.length} سجلات داخل النطاق ({activeContext?.subject})
              </p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={handleCreateNewLesson} disabled={saving || !activeContextId}>
              + درس جديد
            </button>
          </div>

          <div className="equal-split-grid" style={{ gap: "10px" }}>
            <div className="form-group">
              <label className="form-label">البحث عن درس</label>
              <input
                className="form-input"
                placeholder="اكتب اسم الدرس..."
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">تصفية حسب الفصل</label>
              <select
                className="form-select"
                value={chapterFilter}
                onChange={(e) => setChapterFilter(e.target.value)}
              >
                <option value="all">جميع الفصول</option>
                {allChapters.map((ch: any) => (
                  <option key={ch.id} value={ch.id}>
                    {ch.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-secondary)" }}>
                جارٍ تحميل الدروس...
              </div>
            ) : visibleLessons.length === 0 ? (
              <div style={{ textAlign: "center", padding: "34px 10px", color: "var(--text-secondary)" }}>
                <p style={{ marginBottom: "12px", fontSize: "0.9rem" }}>
                  {searchQ.trim() || chapterFilter !== "all"
                    ? "لا توجد دروس تطابق عبارة البحث أو الفصل المختار."
                    : `لا توجد دروس مضافة بعد في سياق (${activeContext?.subject || "المادة"}).`}
                </p>
                {searchQ.trim() || chapterFilter !== "all" ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setSearchQ("");
                      setChapterFilter("all");
                    }}
                  >
                    إظهار جميع الدروس
                  </button>
                ) : (
                  <button type="button" className="btn btn-primary" onClick={handleCreateNewLesson} disabled={saving}>
                    + أضف أول درس
                  </button>
                )}
              </div>
            ) : (
              visibleLessons.map((les) => {
                const isSelected = les.id === selectedLessonId;
                const chObj = allChapters.find((c: any) => c.id === les.chapterId);
                const isDoc = les.contentOrigin === "documented_source";
                return (
                  <div
                    key={les.id}
                    onClick={() => selectLessonObj(les)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        selectLessonObj(les);
                      }
                    }}
                    style={{
                      padding: "14px 16px",
                      borderRadius: "12px",
                      border: isSelected ? "2px solid var(--primary-green)" : "1px solid var(--border-color)",
                      backgroundColor: isSelected ? "var(--primary-tint-bg)" : "#ffffff",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px", gap: "8px" }}>
                      <span style={{ fontWeight: 800, fontSize: "1rem" }}>{les.title}</span>
                      <span style={{ color: isSelected ? "var(--primary-green)" : "var(--text-muted)", fontWeight: 700, flexShrink: 0 }}>
                        {isSelected ? "✓ محدّد" : "○"}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                      {chObj ? `الفصل: ${chObj.title}` : "درس غير مصنف بفصل"}
                      {les.printedPageNumber ? ` · ص مطبوعة ${les.printedPageNumber}` : ""}
                      {les.pdfPageNumber ? ` · PDF ص ${les.pdfPageNumber}` : ""}
                    </div>
                    <span className={`badge ${isDoc ? "badge-success" : "badge-warning"}`}>{les.provenanceLabel}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Left Column in RTL: Selected Lesson Editable Details matching `اختيار الدرس.png` */}
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "2px" }}>تفاصيل الدرس المحدّد</h3>
          <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            أهداف ومعارف سابقة ومعايير تقويم قابلة للتحرير والحفظ الدائم
          </p>

          {!currentLesson ? (
            <div style={{ textAlign: "center", padding: "40px 10px", color: "var(--text-secondary)" }}>
              <p style={{ marginBottom: "12px" }}>أضف درسًا جديدًا أو اختر درسًا من القائمة لتعديل أهدافه ومعارفه السابقة.</p>
              <button type="button" className="btn btn-primary" onClick={handleCreateNewLesson} disabled={saving || !activeContextId}>
                + إضافة درس جديد الآن
              </button>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "12px" }}>
                <span className={`badge ${currentLesson.contentOrigin === "documented_source" ? "badge-success" : "badge-warning"}`}>
                  {currentLesson.provenanceLabel || "غير موثّق"}
                </span>
                <button type="button" className="btn btn-secondary" onClick={handleDuplicateLesson} disabled={saving}>
                  نسخ الدرس
                </button>
              </div>

              <div className="form-group">
                <label className="form-label">عنوان الدرس</label>
                <input
                  className="form-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="equal-split-grid">
                <div className="form-group">
                  <label className="form-label">المصدر المرتبط</label>
                  <select
                    className="form-select"
                    value={sourceId}
                    onChange={(e) => {
                      setSourceId(e.target.value);
                      setChapterId("");
                    }}
                  >
                    <option value="">— غير مرتبط بمصدر —</option>
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title} ({s.verificationStatus === "human_verified" ? "موثّق" : "معلّق"})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">الفصل</label>
                  <select
                    className="form-select"
                    value={chapterId}
                    onChange={(e) => setChapterId(e.target.value)}
                  >
                    <option value="">— بدون فصل —</option>
                    {allChapters
                      .filter((c: any) => !sourceId || c.sourceId === sourceId)
                      .map((c: any) => (
                        <option key={c.id} value={c.id}>
                          {c.title}
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              <div className="stats-grid-3" style={{ marginBottom: 0 }}>
                <div className="form-group">
                  <label className="form-label">نطاق الدرس</label>
                  <input
                    className="form-input"
                    readOnly
                    value={`${activeContext?.subject || "—"} · ${activeContext?.grade || "—"}`}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">رقم صفحة PDF</label>
                  <input
                    type="number"
                    min={1}
                    className="form-input"
                    placeholder="مثال: 12"
                    value={pdfPageNumber}
                    onChange={(e) => setPdfPageNumber(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">رقم الصفحة المطبوعة</label>
                  <input
                    className="form-input"
                    placeholder="اربط برقم الصفحة"
                    value={printedPage}
                    onChange={(e) => setPrintedPage(e.target.value)}
                  />
                </div>
              </div>

              {linkedChapter && (
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                  الفصل المرتبط: {linkedChapter.title}
                </div>
              )}

              {objectives.map((obj, idx) => (
                <div className="form-group" key={idx}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      الهدف التعليمي #{idx + 1} · صياغة قابلة للتحرير
                    </label>
                    {objectives.length > 1 && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: "2px 8px", fontSize: "0.75rem" }}
                        aria-label={`حذف الهدف ${idx + 1}`}
                        onClick={() => setObjectives(objectives.filter((_, i) => i !== idx))}
                      >
                        ✕ حذف
                      </button>
                    )}
                  </div>
                  <textarea
                    className="form-textarea"
                    style={{ minHeight: "66px" }}
                    value={obj}
                    onChange={(e) => {
                      const next = [...objectives];
                      next[idx] = e.target.value;
                      setObjectives(next);
                    }}
                  />
                </div>
              ))}

              <div className="form-group">
                <label className="form-label">المتطلبات والمعارف السابقة</label>
                <input
                  className="form-input"
                  value={priorKnowledge}
                  onChange={(e) => setPriorKnowledge(e.target.value)}
                  placeholder="أدخل المعارف السابقة المطلوبة للدرس..."
                />
              </div>

              <div className="form-group">
                <label className="form-label">معايير التقويم وأدلة التعلم الملائمة للمادة</label>
                <input
                  className="form-input"
                  value={evaluationCriteria}
                  onChange={(e) => setEvaluationCriteria(e.target.value)}
                  placeholder="محك تقييم أو معيار تحقق الهدف..."
                />
              </div>

              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "12px" }}>
                <button type="button" className="btn btn-primary" onClick={handleSaveLesson} disabled={saving}>
                  {saving ? "جارٍ الحفظ..." : "حفظ تفاصيل الدرس"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setObjectives([...objectives, "هدف تعليمي جديد قابل للتحرير."])}
                >
                  + إضافة هدف
                </button>
              </div>

              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "10px" }}>
                {isLinkedSourceVerified
                  ? "المصدر المرتبط موثّق؛ إدخال رقم الصفحة يربط الدرس بالمصدر المعتمد."
                  : "المصدر المرتبط غير موثّق بعد؛ تبقى نسبة الدرس تجريبية حتى اعتماد توثيق الكتاب في صفحة المصادر."}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "4px" }}>الخطوة التالية: الوسائل التعليمية وأدوات المدرس</h3>
        <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)" }}>
          اختر ما يتوفر فعلًا في الصف، واستخدم أدوات المادة التخصصية (تحليل نص، خط زمني، تجربة، أو مدقق المسائل الرياضية).
        </p>
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <Link href="/tools" className="btn btn-primary">
          ← متابعة إلى الوسائل التعليمية
        </Link>
        <Link href="/curriculum" className="btn btn-secondary">
          تغيير المنهج
        </Link>
      </div>
    </div>
  );
}

export default function LessonsPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <LessonsContent />
    </Suspense>
  );
}
