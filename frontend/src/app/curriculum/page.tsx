"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

export default function CurriculumPage() {
  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [sources, setSources] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [newChapterTitle, setNewChapterTitle] = useState<string>("");
  const [newChapterPdfPage, setNewChapterPdfPage] = useState<string>("");
  const [newChapterPrintedPage, setNewChapterPrintedPage] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [savingChapter, setSavingChapter] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const loadData = useCallback(
    async (isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setSources([]);
        setLessons([]);
        setSelectedSourceId("");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [sRes, lRes] = await Promise.all([
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/lessons?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const items = sRes.items || [];
        setSources(items);
        setLessons(lRes.items || []);
        setSelectedSourceId((prev) => (items.some((s: any) => s.id === prev) ? prev : items[0]?.id || ""));
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل سجلات المنهج والفصول.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setSearchQuery("");
    setStatusFilter("all");
    setNewChapterTitle("");
    setNewChapterPdfPage("");
    setNewChapterPrintedPage("");
    loadData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadData]);

  const filteredSources = sources.filter((s) => {
    const q = searchQuery.trim().toLowerCase();
    const matchesQ =
      !q ||
      (s.title || "").toLowerCase().includes(q) ||
      (s.fileName || "").toLowerCase().includes(q) ||
      (s.reviewNotes || "").toLowerCase().includes(q);
    const matchesStatus = statusFilter === "all" || s.verificationStatus === statusFilter;
    return matchesQ && matchesStatus;
  });

  const selectedSource =
    filteredSources.find((s) => s.id === selectedSourceId) ||
    filteredSources[0] ||
    (filteredSources.length === 0 ? null : sources.find((s) => s.id === selectedSourceId) || null);

  const sourceLessons = selectedSource ? lessons.filter((l) => l.sourceId === selectedSource.id) : [];

  const handleAddChapter = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setFeedback("");
    if (!selectedSource) return;
    if (!newChapterTitle.trim()) {
      setErrorMsg("يرجى إدخال عنوان الفصل قبل الحفظ.");
      return;
    }
    const parsedPdf = newChapterPdfPage.trim() ? Number.parseInt(newChapterPdfPage.trim(), 10) : null;
    if (newChapterPdfPage.trim() && (Number.isNaN(parsedPdf) || (parsedPdf ?? 0) < 1)) {
      setErrorMsg("رقم صفحة PDF يجب أن يكون عددًا صحيحًا موجبًا.");
      return;
    }

    setSavingChapter(true);
    try {
      await apiFetch("/api/chapters", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          sourceId: selectedSource.id,
          title: newChapterTitle.trim(),
          orderIndex: (selectedSource.chapters?.length || 0) + 1,
          pdfStartPage: parsedPdf,
          printedStartPage: newChapterPrintedPage.trim(),
          isDocumented: selectedSource.verificationStatus === "human_verified",
        }),
      });
      setNewChapterTitle("");
      setNewChapterPdfPage("");
      setNewChapterPrintedPage("");
      setFeedback("تمت إضافة الفصل وربطه بسجل المصدر المحدّد.");
      await loadData();
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر إضافة الفصل.");
    } finally {
      setSavingChapter(false);
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / المنهج
      </div>
      <h1 className="page-title">المنهج</h1>
      <p className="page-subtitle">
        اختر سجل المنهج لبدء التخطيط. يبقى المحتوى تجريبيًا حتى مراجعة مصدره وتوثيق طبعته وسنته.
      </p>

      <div className="info-banner">
        <span>
          ⓘ لا يتم استيراد أي فهرس رسمي وهمي من الذاكرة؛ الفصول والدروس المعروضة إما مستخرجة من ملف PDF المرفوع أو مضافة يدويًا ومعلّمة بوضوح.
        </span>
      </div>

      <WorkflowStepper activeStep={2} />

      {/* Search & Status Filter matching `المنهج.png` */}
      <div className="main-split-grid" style={{ marginBottom: "12px" }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">البحث داخل سياق ({activeContext?.subject} · {activeContext?.grade})</label>
          <input
            className="form-input"
            placeholder="ابحث عن سجل منهج أو اسم ملف..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">حالة المصدر</label>
          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">جميع السجلات المتاحة</option>
            <option value="human_verified">موثّق — مراجعة بشرية معتمدة</option>
            <option value="pending_review">معلّق — يتطلب مراجعة المصدر</option>
          </select>
        </div>
      </div>

      <div className="warning-banner">
        <span>
          ⚠ النطاق الحالي: {activeContext?.subject || "—"} للصف {activeContext?.grade || "—"} في {activeContext?.country || "—"}. اختيار سجل لا يعني توثيقه أو اعتماده رسميًا.
        </span>
      </div>

      {feedback && (
        <div className="info-banner" style={{ borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
          <span>✓ {feedback}</span>
        </div>
      )}

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {/* Main Split matching `المنهج.png`: Source Cards (Right/Main) & Selected Source Details (Left) */}
      <div className="main-split-grid">
        <div>
          {loading ? (
            <div className="card" style={{ textAlign: "center", padding: "36px 16px", color: "var(--text-secondary)" }}>
              جارٍ تحميل سجلات المنهج...
            </div>
          ) : sources.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "40px 16px" }}>
              <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📖</div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "8px" }}>
                لا يوجد كتاب منهج مرفوع بعد في سياق ({activeContext?.subject || "المادة"})
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                ارفع ملف PDF لكتاب المنهج لتوثيق الفصول والصفحات واستخراج الأهداف والدروس.
              </p>
              <div style={{ display: "flex", gap: "10px", justifyContent: "center", flexWrap: "wrap" }}>
                <Link href="/sources" className="btn btn-primary">
                  + رفع كتاب المنهج (PDF)
                </Link>
                <Link href="/lessons" className="btn btn-secondary">
                  إضافة درس يدويًا ←
                </Link>
              </div>
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "32px 16px" }}>
              <p style={{ fontSize: "0.92rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                لا توجد سجلات منهج تطابق البحث أو تصفية الحالة الحالية.
              </p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setSearchQuery("");
                  setStatusFilter("all");
                }}
              >
                إعادة تعيين البحث والتصفية
              </button>
            </div>
          ) : (
            filteredSources.map((src) => {
              const isSelected = selectedSource?.id === src.id;
              return (
                <div
                  key={src.id}
                  onClick={() => setSelectedSourceId(src.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedSourceId(src.id);
                    }
                  }}
                  className="card"
                  style={{
                    borderColor: isSelected ? "var(--primary-green)" : "var(--border-color)",
                    borderWidth: isSelected ? "2px" : "1px",
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "stretch",
                    gap: "18px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                    <div style={{ display: "flex", gap: "8px", marginBottom: "10px", flexWrap: "wrap" }}>
                      <span
                        className={`badge ${
                          src.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
                        }`}
                      >
                        {src.verificationStatus === "human_verified" ? "موثّق — معتمد" : "تجريبي — غير موثّق"}
                      </span>
                      {isSelected && <span className="badge badge-success">تم الاختيار · حالة مرئية</span>}
                    </div>
                    <h2 style={{ fontSize: "1.3rem", fontWeight: 800, marginBottom: "6px" }}>{src.title}</h2>
                    <p style={{ fontSize: "0.86rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      {src.reviewNotes || "سجل مخصّص لتوضيح رحلة التخطيط، وليس نسخة من كتاب رسمي."}
                    </p>
                    <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: "4px" }}>
                      {activeContext?.subject} · {activeContext?.grade} · {activeContext?.country}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      {src.pageCount > 0
                        ? `ملف PDF مرفوع (${src.pageCount} صفحات) · البصمة: ${src.sha256Fingerprint?.slice(0, 12)}...`
                        : "بيانات المصدر غير مكتملة — بانتظار رفع الكتاب أو اعتماد الفهرس"}
                    </div>
                  </div>

                  {/* Book Cover Tile matching `المنهج.png` */}
                  <div
                    style={{
                      flex: "0 1 145px",
                      minWidth: "120px",
                      backgroundColor: "var(--sidebar-bg)",
                      color: "#fff",
                      borderRadius: "12px",
                      padding: "18px 14px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      textAlign: "center",
                    }}
                  >
                    <div style={{ fontSize: "1.4rem" }}>📖</div>
                    <div style={{ fontWeight: 800, fontSize: "1rem", overflowWrap: "anywhere" }}>{src.title}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--sidebar-muted)" }}>
                      {activeContext?.grade} · {src.verificationStatus === "human_verified" ? "موثّق" : "غير موثّق"}
                    </div>
                  </div>
                </div>
              );
            })
          )}

          {/* What Transfers to Your Plan Card matching `المنهج.png` */}
          <div className="card">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "12px" }}>ما الذي ينتقل إلى خطتك؟</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                <span className="badge badge-success" style={{ padding: "8px" }}>📖</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>سياق المنهج المحدّد</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    اسم السجل ونطاقه وحالة التحقق وبصمة المصدر (إن وُجدت).
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                <span className="badge badge-success" style={{ padding: "8px" }}>📄</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>دروس وفصول قابلة للتخطيط</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {selectedSource?.chapters?.length || sourceLessons.length
                      ? `${selectedSource?.chapters?.length || 0} فصول و${sourceLessons.length} دروس مرتبطة بهذا المصدر.`
                      : "لا توجد فصول أو صفحات أو تمارين رسمية مختلقة في هذا النموذج."}
                  </div>
                </div>
              </div>
            </div>

            {/* Chapters List & Extracted Lessons & Add Documented Chapter Form */}
            {selectedSource && (
              <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid var(--border-subtle)" }}>
                <h4 style={{ fontSize: "0.92rem", fontWeight: 700, marginBottom: "8px" }}>
                  الفصول والدروس المسجلة ضمن هذا المصدر ({selectedSource.chapters?.length || 0} فصول · {sourceLessons.length} دروس)
                </h4>
                {selectedSource.chapters && selectedSource.chapters.length > 0 ? (
                  <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "8px", marginBottom: "12px" }}>
                    {selectedSource.chapters.map((ch: any) => {
                      const chLessons = sourceLessons.filter((l) => l.chapterId === ch.id);
                      return (
                        <li
                          key={ch.id}
                          style={{
                            padding: "10px 12px",
                            background: "#f9fbf9",
                            borderRadius: "8px",
                            border: "1px solid var(--border-subtle)",
                            fontSize: "0.84rem",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "8px",
                            }}
                          >
                            <span>
                              <strong>الفصل {ch.orderIndex}:</strong> {ch.title}{" "}
                              {(ch.printedStartPage || ch.pdfStartPage) &&
                                `(${ch.printedStartPage ? `ص مطبوعة: ${ch.printedStartPage}` : ""}${
                                  ch.printedStartPage && ch.pdfStartPage ? " · " : ""
                                }${ch.pdfStartPage ? `PDF: ${ch.pdfStartPage}` : ""})`}
                            </span>
                            <span className={`badge ${ch.isDocumented ? "badge-success" : "badge-warning"}`}>
                              {ch.provenanceLabel}
                            </span>
                          </div>
                          {chLessons.length > 0 && (
                            <div style={{ marginTop: "8px", paddingTop: "6px", borderTop: "1px dashed var(--border-color)", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                              {chLessons.map((les) => (
                                <Link
                                  key={les.id}
                                  href={`/lessons?lessonId=${encodeURIComponent(les.id)}`}
                                  className="badge badge-neutral"
                                  style={{ textDecoration: "none", border: "1px solid var(--border-color)" }}
                                >
                                  📄 {les.title}
                                  {les.printedPageNumber ? ` (ص ${les.printedPageNumber})` : ""}
                                </Link>
                              ))}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "10px" }}>
                    لم يُسجّل أي فصل بعد. يمكنك استخراج الفصول تلقائيًا من «استيراد كتاب المنهج» أو إضافة فصل يدويًا أدناه.
                  </p>
                )}

                <form onSubmit={handleAddChapter} style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <input
                    className="form-input"
                    style={{ flex: "2 1 180px" }}
                    placeholder="عنوان الفصل (حسب الكتاب أو كمثال معلّم)..."
                    value={newChapterTitle}
                    onChange={(e) => setNewChapterTitle(e.target.value)}
                  />
                  <input
                    type="number"
                    min={1}
                    className="form-input"
                    style={{ flex: "1 1 100px" }}
                    placeholder="صفحة PDF"
                    value={newChapterPdfPage}
                    onChange={(e) => setNewChapterPdfPage(e.target.value)}
                  />
                  <input
                    className="form-input"
                    style={{ flex: "1 1 110px" }}
                    placeholder="الصفحة المطبوعة"
                    value={newChapterPrintedPage}
                    onChange={(e) => setNewChapterPrintedPage(e.target.value)}
                  />
                  <button type="submit" className="btn btn-secondary" disabled={savingChapter}>
                    {savingChapter ? "جارٍ التسجيل..." : "+ تسجيل فصل"}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>

        {/* Selected Record Summary Panel matching `المنهج.png` */}
        <div className="card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "2px" }}>السجل المحدّد</h3>
          <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            تفاصيل المصدر قبل المتابعة
          </p>

          <span
            className={`badge ${
              selectedSource?.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
            }`}
            style={{ marginBottom: "10px" }}
          >
            {selectedSource?.verificationStatus === "human_verified" ? "موثّق — معتمد" : "تجريبي — غير موثّق"}
          </span>

          <div style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "14px" }}>
            {selectedSource?.title || "لا يوجد سجل محدّد"}
          </div>

          <div className="form-group">
            <label className="form-label">المادة والصف</label>
            <input
              className="form-input"
              readOnly
              value={`${activeContext?.subject || "—"} · ${activeContext?.grade || "—"} · ${activeContext?.country || "—"}`}
            />
          </div>

          <div className="equal-split-grid">
            <div className="form-group">
              <label className="form-label">السنة الدراسية</label>
              <input
                className="form-input"
                readOnly
                value={selectedSource?.bookYear || activeContext?.year || "غير مدخلة"}
              />
            </div>
            <div className="form-group">
              <label className="form-label">الطبعة</label>
              <input
                className="form-input"
                readOnly
                value={selectedSource?.edition || activeContext?.edition || "غير مدخلة"}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">رابط المصدر</label>
            <input
              className="form-input"
              readOnly
              value={selectedSource?.sourceUrl || "لم يُضف مصدر"}
            />
            <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: "4px" }}>
              مراجعة المصدر مطلوبة قبل الاستخدام الرسمي.
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "8px",
              paddingTop: "10px",
              borderTop: "1px solid var(--border-subtle)",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>حالة التحقق</div>
              <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                {selectedSource?.reviewerName
                  ? `راجعه: ${selectedSource.reviewerName}`
                  : "بانتظار بيانات المصدر ومراجعة مسؤول المنهج"}
              </div>
            </div>
            <span
              className={`badge ${
                selectedSource?.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
              }`}
            >
              {selectedSource?.verificationStatus === "human_verified" ? "معتمد" : "معلّق"}
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Notice & Action Bar matching `المنهج.png` */}
      <div className="card">
        <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "4px" }}>قبل الاستخدام الرسمي</h3>
        <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)" }}>
          أكمل السنة الدراسية والطبعة ورابط المصدر في مساحة «استيراد كتاب المنهج»، ثم اطلب مراجعة المصدر. تبقى حالة التحقق معلّقة ولا تتغيّر بمجرد اختيار المنهج.
        </p>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <Link href="/lessons" className="btn btn-primary">
            ← متابعة إلى اختيار الدرس
          </Link>
          <Link href="/" className="btn btn-secondary">
            العودة إلى لوحة المعلم
          </Link>
        </div>
        <Link href="/sources" className="btn btn-secondary">
          إدارة وتوثيق المصدر (PDF)
        </Link>
      </div>
    </div>
  );
}
