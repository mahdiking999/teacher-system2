"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

export default function SourcesImportPage() {
  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [sources, setSources] = useState<any[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [savingMeta, setSavingMeta] = useState<boolean>(false);
  const [savingPage, setSavingPage] = useState<boolean>(false);
  const [aiProcessing, setAiProcessing] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [extractedSummary, setExtractedSummary] = useState<{
    chaptersCreated: number;
    lessonsCreated: number;
    modelUsed: string;
  } | null>(null);

  // Metadata Form State matching `استيراد كتاب المنهج.png`
  const [title, setTitle] = useState<string>("كتاب المنهج");
  const [bookYear, setBookYear] = useState<string>("");
  const [edition, setEdition] = useState<string>("");
  const [sourceUrl, setSourceUrl] = useState<string>("");
  const [reviewerName, setReviewerName] = useState<string>("");
  const [reviewNotes, setReviewNotes] = useState<string>("");
  const [selectedPageIdx, setSelectedPageIdx] = useState<number>(0);
  const [correctedPageText, setCorrectedPageText] = useState<string>("");
  const [printedPageNumber, setPrintedPageNumber] = useState<string>("1");
  const [pageDirty, setPageDirty] = useState<boolean>(false);
  const [pendingPageSwitchIdx, setPendingPageSwitchIdx] = useState<number | null>(null);

  const bindSource = useCallback(
    (src: any | null, keepPageIdx?: number) => {
      if (!src) {
        setSelectedSourceId("");
        setTitle(activeContext?.curriculumName || "كتاب المنهج");
        setBookYear("");
        setEdition("");
        setSourceUrl("");
        setReviewerName("");
        setReviewNotes("");
        setSelectedPageIdx(0);
        setCorrectedPageText("");
        setPrintedPageNumber("1");
        setPageDirty(false);
        setPendingPageSwitchIdx(null);
        return;
      }
      setSelectedSourceId(src.id);
      setTitle(src.title || "سجل منهج");
      setBookYear(src.bookYear || "");
      setEdition(src.edition || "");
      setSourceUrl(src.sourceUrl || "");
      setReviewerName(src.reviewerName || "");
      setReviewNotes(src.reviewNotes || "");
      const pageIdx =
        typeof keepPageIdx === "number" && src.pages && keepPageIdx >= 0 && keepPageIdx < src.pages.length
          ? keepPageIdx
          : 0;
      setSelectedPageIdx(pageIdx);
      setPageDirty(false);
      setPendingPageSwitchIdx(null);
      if (src.pages && src.pages.length > 0) {
        const pg = src.pages[pageIdx];
        setCorrectedPageText(pg.correctedText || pg.extractedText || "");
        setPrintedPageNumber(pg.printedPageNumber || String(pg.pdfPageNumber || 1));
      } else {
        setCorrectedPageText("");
        setPrintedPageNumber("1");
      }
    },
    [activeContext?.curriculumName]
  );

  const loadSources = useCallback(
    async (keepId?: string, keepPageIdx?: number, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setSources([]);
        bindSource(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const res = await apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`);
        if (isCancelled && isCancelled()) return;
        const list = res.items || [];
        setSources(list);
        setSelectedSourceId((prev) => {
          const targetId =
            (keepId && list.some((s: any) => s.id === keepId) && keepId) ||
            (prev && list.some((s: any) => s.id === prev) && prev) ||
            (list[0] && list[0].id) ||
            "";
          const found = list.find((s: any) => s.id === targetId) || null;
          bindSource(found, keepPageIdx);
          return found ? found.id : "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل سجلات المصادر.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch, bindSource]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setExtractedSummary(null);
    setSelectedSourceId("");
    bindSource(null);
    loadSources(undefined, undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentSource = sources.find((s) => s.id === selectedSourceId) || null;
  const currentPage = currentSource?.pages?.[selectedPageIdx] || null;

  const uploadPdfFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setErrorMsg("يرجى اختيار ملف بصيغة PDF صالحة فقط.");
      return;
    }
    setUploading(true);
    setErrorMsg("");
    setFeedback("");
    setExtractedSummary(null);
    try {
      const fd = new FormData();
      fd.append("contextId", activeContextId);
      fd.append("title", title || file.name);
      fd.append("bookYear", bookYear);
      fd.append("edition", edition);
      fd.append("sourceUrl", sourceUrl);
      fd.append("file", file);

      const created = await apiFetch("/api/sources/upload", {
        method: "POST",
        body: fd,
      });
      setFeedback(
        `تم رفع وفحص توقيع PDF بنجاح (${created.pageCount} صفحات · البصمة SHA-256: ${created.sha256Fingerprint.slice(
          0,
          16
        )}... · الحالة: ${
          created.extractionStatus === "extracted_text" ? "تم استخراج النص" : "يتطلب مراجعة OCR / تفريغًا يدويًا"
        }).`
      );
      await loadSources(created.id, 0);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر رفع ملف PDF.");
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    await uploadPdfFile(file);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      await uploadPdfFile(file);
    }
  };

  const handleSaveMetadata = async (requestVerification: boolean) => {
    if (!currentSource) return;
    setSavingMeta(true);
    setErrorMsg("");
    setFeedback("");
    try {
      const updated = await apiFetch(`/api/sources/${currentSource.id}`, {
        method: "PUT",
        body: JSON.stringify({
          contextId: activeContextId,
          title,
          bookYear,
          edition,
          sourceUrl,
          isOfficialClaimed: requestVerification,
          officialEvidence: requestVerification
            ? `البلد: ${activeContext?.country} | الطبعة: ${edition} | الرابط: ${sourceUrl}`
            : "",
          reviewerName,
          reviewNotes,
          verificationStatus: requestVerification ? "human_verified" : "pending_review",
          indexApproved: requestVerification,
          expectedVersion: currentSource.version,
        }),
      });
      setFeedback(
        requestVerification
          ? `تم اعتماد توثيق المصدر ومراجعته البشرية بواسطة «${updated.reviewerName}»!`
          : "تم حفظ بيانات المصدر في قاعدة البيانات."
      );
      await loadSources(updated.id, selectedPageIdx);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ بيانات المصدر.");
    } finally {
      setSavingMeta(false);
    }
  };

  const handleSavePageCorrection = async (): Promise<boolean> => {
    if (!currentSource || !currentPage) return false;
    setSavingPage(true);
    setErrorMsg("");
    try {
      await apiFetch(`/api/sources/${currentSource.id}/pages/${currentPage.id}`, {
        method: "PUT",
        body: JSON.stringify({
          contextId: activeContextId,
          printedPageNumber,
          correctedText: correctedPageText,
          humanReviewed: true,
        }),
      });
      setPageDirty(false);
      setFeedback(`تم حفظ تصحيح النص ورقم الصفحة المطبوعة (${printedPageNumber}) لصفحة PDF رقم ${currentPage.pdfPageNumber}.`);
      await loadSources(currentSource.id, selectedPageIdx);
      return true;
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ تصحيح الصفحة.");
      return false;
    } finally {
      setSavingPage(false);
    }
  };

  const applyPageSelection = (idx: number) => {
    setSelectedPageIdx(idx);
    setPageDirty(false);
    setPendingPageSwitchIdx(null);
    const pg = currentSource?.pages?.[idx];
    if (pg) {
      setCorrectedPageText(pg.correctedText || pg.extractedText || "");
      setPrintedPageNumber(pg.printedPageNumber || String(pg.pdfPageNumber));
    }
  };

  const handlePageSelectChange = (idx: number) => {
    if (pageDirty) {
      setPendingPageSwitchIdx(idx);
      return;
    }
    applyPageSelection(idx);
  };

  const handleAiPageOcr = async () => {
    if (!currentSource || !currentPage) return;
    setAiProcessing("ocr");
    setErrorMsg("");
    setFeedback("");
    try {
      const res = await apiFetch(`/api/sources/${currentSource.id}/pages/${currentPage.id}/ai-ocr`, {
        method: "POST",
        body: JSON.stringify({ contextId: activeContextId }),
      });
      if (res?.page) {
        setCorrectedPageText(res.page.correctedText || res.page.extractedText || "");
        setPrintedPageNumber(res.page.printedPageNumber || String(currentPage.pdfPageNumber));
        setPageDirty(false);
      }
      await loadSources(currentSource.id, selectedPageIdx);
      setFeedback(
        `تم استخراج النص بالرؤية الذكية لصفحة PDF رقم ${currentPage.pdfPageNumber} عبر (${res?.modelUsed || "NVIDIA NIM Vision"}). راجع النص قبل الاعتماد.`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر تنفيذ استخراج النص بالرؤية الذكية.");
    } finally {
      setAiProcessing("");
    }
  };

  const handleAiExtractStructure = async () => {
    if (!currentSource) return;
    setAiProcessing("extract");
    setErrorMsg("");
    setFeedback("");
    try {
      const res = await apiFetch(`/api/sources/${currentSource.id}/ai-extract-structure`, {
        method: "POST",
        body: JSON.stringify({ contextId: activeContextId }),
      });
      await loadSources(currentSource.id, selectedPageIdx);
      const summaryObj = {
        chaptersCreated: res?.chaptersCreated ?? 0,
        lessonsCreated: res?.lessonsCreated ?? 0,
        modelUsed: res?.modelUsed || "NVIDIA NIM",
      };
      setExtractedSummary(summaryObj);
      setFeedback(
        `تم استخراج الفصول والدروس تلقائيًا عبر (${summaryObj.modelUsed}): أُنشئ ${summaryObj.chaptersCreated} فصلًا و${summaryObj.lessonsCreated} درسًا.`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر استخراج الفصول والدروس تلقائيًا.");
    } finally {
      setAiProcessing("");
    }
  };

  const canRequestVerification = Boolean(bookYear.trim() && edition.trim() && sourceUrl.trim() && reviewerName.trim());

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / إدارة المنهج / استيراد كتاب المنهج
      </div>
      <h1 className="page-title">استيراد كتاب المنهج والمصادر</h1>
      <p className="page-subtitle">
        مساحة مسؤول المنهج: رفع ملف PDF، فحص التوقيع الفعلي، معاينة وتصحيح النص المستخرج (OCR)، وتسجيل بيانات المصدر قبل طلب مراجعة مستقلة للتوثيق.
      </p>

      <div className="info-banner">
        <span>
          ⓘ يفحص الخادم توقيع الملف الفعلي (`%PDF-`) والحجم وعدد الصفحات ويحسب بصمة SHA-256، ويفصل بين رقم صفحة PDF ورقم الصفحة المطبوعة.
        </span>
      </div>

      <WorkflowStepper activeStep={1} />

      <div style={{ display: "flex", gap: "8px", marginBottom: "14px", flexWrap: "wrap" }}>
        <span
          className={`badge ${
            currentSource?.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
          }`}
        >
          {currentSource?.verificationStatus === "human_verified" ? "موثّق ومعتمد" : "التحقق معلّق افتراضيًا"}
        </span>
        <span className="badge badge-neutral">سياق الإدارة · {activeContext?.subject} ({activeContext?.grade})</span>
      </div>

      <div className="warning-banner">
        <span>
          ⚠ رفع الملف وحده لا يمنحه توثيقًا تلقائيًا. السنة الدراسية والطبعة ورابط المصدر ونتيجة مراجعة المصدر ضرورية قبل أي اعتماد رسمي.
        </span>
      </div>

      {feedback && (
        <div className="info-banner" style={{ borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
          <span>✓ {feedback}</span>
        </div>
      )}

      {extractedSummary && (
        <div className="card" style={{ borderColor: "var(--primary-green)", backgroundColor: "var(--primary-tint-bg)" }}>
          <div style={{ fontWeight: 800, marginBottom: "6px", color: "var(--primary-green)" }}>
            📚 اكتمل استخراج بنية الكتاب ({extractedSummary.chaptersCreated} فصول · {extractedSummary.lessonsCreated} دروس)
          </div>
          <p style={{ fontSize: "0.84rem", color: "var(--text-main)", marginBottom: "10px" }}>
            الفصول والدروس المستخرجة أصبحت متاحة الآن في صفحات المنهج واختيار الدرس للربط المباشر بالخطط اليومية.
          </p>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <Link href="/curriculum" className="btn btn-primary">
              عرض الفصول في المنهج ←
            </Link>
            <Link href="/lessons" className="btn btn-secondary">
              مراجعة وتحرير الدروس المستخرجة ←
            </Link>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {/* Top Split matching `استيراد كتاب المنهج.png`: PDF Upload Box & Selected File Status */}
      <div className="equal-split-grid">
        <div className="card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "2px" }}>رفع ملف PDF</h3>
          <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            {currentSource?.pageCount > 0
              ? `تم رفع ملف (${currentSource.pageCount} صفحات)`
              : "الحالة الابتدائية · ارفع ملف PDF نصي أو ممسوح"}
          </p>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(false);
            }}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${isDragging ? "var(--primary-green)" : "var(--border-color)"}`,
              borderRadius: "12px",
              padding: "28px 18px",
              textAlign: "center",
              backgroundColor: isDragging ? "var(--primary-tint-bg)" : "#fbfcfb",
              transition: "all 0.15s ease",
            }}
          >
            <div style={{ fontSize: "1.8rem", marginBottom: "8px", color: "var(--primary-green)" }}>☁↑</div>
            <div style={{ fontWeight: 800, fontSize: "0.98rem", marginBottom: "4px" }}>
              اسحب ملف الكتاب وأفلته هنا أو اختر ملفًا
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "14px" }}>
              PDF فقط · يُفحص التوقيع الفعلي (`%PDF-`) ولا تُضاف حالة توثيق تلقائيًا
            </div>
            <label className="btn btn-secondary" style={{ cursor: uploading ? "not-allowed" : "pointer" }}>
              {uploading ? "جارٍ رفع وفحص الملف..." : "اختيار ملف PDF حقيقي"}
              <input
                type="file"
                accept=".pdf,application/pdf"
                disabled={uploading || !activeContextId}
                onChange={handleFileUpload}
                style={{ display: "none" }}
              />
            </label>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "2px" }}>بعد اختيار ملف · بيانات البصمة والاستخراج</h3>
          <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            {currentSource?.sha256Fingerprint
              ? `بصمة SHA-256: ${currentSource.sha256Fingerprint.slice(0, 24)}...`
              : "لم يُرفع ملف PDF فعلي بعد"}
          </p>

          <div
            style={{
              padding: "16px",
              borderRadius: "12px",
              backgroundColor: "var(--primary-tint-bg)",
              border: "1px solid rgba(23, 107, 82, 0.25)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
              <div style={{ fontWeight: 800, fontSize: "0.95rem", overflowWrap: "anywhere" }}>
                📄 {currentSource?.fileName || "لم يُرفع ملف PDF بعد"}
              </div>
              <span className="badge badge-neutral">
                {currentSource?.pageCount ? `${currentSource.pageCount} صفحات` : "بانتظار الرفع"}
              </span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
              حالة الاستخراج:{" "}
              <strong>
                {currentSource?.extractionStatus === "extracted_text"
                  ? "PDF نصي (تم استخراج النص مع رقم الصفحة)"
                  : currentSource?.extractionStatus === "requires_ocr_or_manual"
                  ? "يتطلب OCR / تفريغًا يدويًا"
                  : "لا يوجد ملف مرفوع بعد"}
              </strong>
            </div>
            <span
              className={`badge ${
                currentSource?.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
              }`}
            >
              {currentSource?.verificationStatus === "human_verified" ? "تم اعتماد التوثيق" : "بانتظار بيانات المصدر والمراجعة"}
            </span>
          </div>
        </div>
      </div>

      {/* Middle Split matching `استيراد كتاب المنهج.png`: Required Source Metadata Form (2/3) & Scope + Review Workflow (1/3) */}
      <div className="main-split-grid">
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "2px" }}>بيانات المصدر المطلوبة</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
            الحقول غير معبّأة عمدًا عند عدم معرفتها؛ لا توجد بيانات كتاب رسمية مفترضة أو مخمّنة
          </p>

          <div className="form-group">
            <label className="form-label">عنوان السجل</label>
            <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="equal-split-grid">
            <div className="form-group">
              <label className="form-label">السنة الدراسية / سنة الكتاب *</label>
              <input
                className="form-input"
                placeholder="أدخل السنة بعد مراجعة المصدر..."
                value={bookYear}
                onChange={(e) => setBookYear(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">الطبعة *</label>
              <input
                className="form-input"
                placeholder="أدخل الطبعة كما تظهر في المصدر..."
                value={edition}
                onChange={(e) => setEdition(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">رابط / مرجع المصدر *</label>
            <input
              className={`form-input ${!sourceUrl.trim() ? "error-border" : ""}`}
              placeholder="أدخل رابط المصدر أو رقم الوثيقة الرسمية الذي سيُراجع..."
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
            {!sourceUrl.trim() && (
              <div style={{ fontSize: "0.75rem", color: "var(--blocker-text)", marginTop: "4px" }}>
                مثال تحقق: رابط المصدر مطلوب؛ لا يمكن طلب المراجعة واعتماد التوثيق بدونه.
              </div>
            )}
          </div>

          <div className="equal-split-grid">
            <div className="form-group">
              <label className="form-label">حالة التحقق · غير قابلة للاعتماد التلقائي</label>
              <input
                className="form-input"
                readOnly
                value={
                  currentSource?.verificationStatus === "human_verified"
                    ? "موثّق — تمت المراجعة البشرية"
                    : "معلّق — يتطلب مراجعة المصدر"
                }
              />
            </div>
            <div className="form-group">
              <label className="form-label">اسم/هوية المراجع *</label>
              <input
                className="form-input"
                placeholder="أدخل اسم المراجع البشري..."
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">ملاحظات التحقق والأدلة</label>
            <textarea
              className="form-textarea"
              placeholder="أدخل ملاحظات مراجعة المصدر والأدلة بعد الفحص..."
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
            />
          </div>

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={savingMeta || !currentSource}
              onClick={() => handleSaveMetadata(false)}
            >
              {savingMeta ? "جارٍ الحفظ..." : "حفظ بيانات ناقصة (مسودة مصدر)"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={savingMeta || !currentSource || !canRequestVerification}
              title={
                !canRequestVerification
                  ? "أدخل السنة والطبعة ورابط المصدر واسم المراجع لتفعيل الاعتماد"
                  : "اعتماد مراجعة المصدر"
              }
              onClick={() => handleSaveMetadata(true)}
            >
              {savingMeta ? "جارٍ الاعتماد..." : "اعتماد مراجعة المصدر وتوثيق الفهرس"}
            </button>
          </div>
        </div>

        <div>
          <div className="card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "10px" }}>نطاق المنهج المعزول</h3>
            <div className="form-group">
              <label className="form-label">المادة</label>
              <input className="form-input" readOnly value={activeContext?.subject || "—"} />
            </div>
            <div className="form-group" style={{ marginBottom: "6px" }}>
              <label className="form-label">الصف والبلد</label>
              <input
                className="form-input"
                readOnly
                value={`${activeContext?.grade || "—"} · ${activeContext?.country || "—"}`}
              />
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              المصدر معزول داخل هذا السياق ولا يختلط بسياقات أخرى.
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "10px" }}>مسار مراجعة المصدر</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>1. إدخال بيانات المصدر</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>السنة والطبعة والرابط مطلوبة</div>
                </div>
                <span className={`badge ${bookYear.trim() && edition.trim() && sourceUrl.trim() ? "badge-success" : "badge-blocker"}`}>
                  {bookYear.trim() && edition.trim() && sourceUrl.trim() ? "مكتمل" : "ناقص"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>2. مراجعة مستقلة</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>يفحص المراجع المصدر ويكتب ملاحظاته</div>
                </div>
                <span className={`badge ${reviewerName.trim() ? "badge-success" : "badge-warning"}`}>
                  {reviewerName.trim() ? "مدخل" : "بانتظار"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>3. تسجيل نتيجة المراجعة</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>لا توثيق تلقائيًا بمجرد رفع الملف</div>
                </div>
                <span
                  className={`badge ${
                    currentSource?.verificationStatus === "human_verified" ? "badge-success" : "badge-neutral"
                  }`}
                >
                  {currentSource?.verificationStatus === "human_verified" ? "موثّق" : "معلّق"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Page Text & OCR Ambiguity Review Section */}
      {currentSource?.pages && currentSource.pages.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>
            معاينة صفحات PDF واستخراج/تصحيح النص وفحص مواضع OCR الملتبسة
          </h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            يُحفظ رقم صفحة PDF ورقم الصفحة المطبوعة كلٌّ على حدة، مع تنبيه لمواضع الأعلام والتواريخ والاقتباسات والرموز والكسور.
          </p>

          {pendingPageSwitchIdx !== null && (
            <div className="warning-banner" style={{ marginBottom: "12px" }}>
              <span>⚠ لديك تعديلات غير محفوظة على الصفحة الحالية (#{currentPage?.pdfPageNumber}).</span>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ padding: "5px 12px", fontSize: "0.8rem" }}
                  onClick={async () => {
                    const nextIdx = pendingPageSwitchIdx;
                    const ok = await handleSavePageCorrection();
                    if (ok && nextIdx !== null) applyPageSelection(nextIdx);
                  }}
                >
                  حفظ ثم الانتقال
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "5px 12px", fontSize: "0.8rem" }}
                  onClick={() => applyPageSelection(pendingPageSwitchIdx)}
                >
                  تجاهل التعديلات والانتقال
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "5px 12px", fontSize: "0.8rem" }}
                  onClick={() => setPendingPageSwitchIdx(null)}
                >
                  إلغاء
                </button>
              </div>
            </div>
          )}

          <div className="equal-split-grid">
            <div className="form-group">
              <label className="form-label">اختر صفحة PDF للمعاينة والتصحيح</label>
              <select
                className="form-select"
                value={selectedPageIdx}
                onChange={(e) => handlePageSelectChange(Number(e.target.value))}
              >
                {currentSource.pages.map((pg: any, idx: number) => (
                  <option key={pg.id} value={idx}>
                    صفحة PDF رقم {pg.pdfPageNumber} (الصفحة المطبوعة: {pg.printedPageNumber || "—"}) —{" "}
                    {pg.humanReviewed ? "تمت مراجعتها" : "تحتاج مراجعة"}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">رقم الصفحة المطبوعة المقابل لصفحة PDF #{currentPage?.pdfPageNumber}</label>
              <input
                className="form-input"
                value={printedPageNumber}
                onChange={(e) => {
                  setPrintedPageNumber(e.target.value);
                  setPageDirty(true);
                }}
              />
            </div>
          </div>

          {currentPage?.ocrAmbiguities && currentPage.ocrAmbiguities.length > 0 && (
            <div className="warning-banner">
              <span>
                🔎 مواضع OCR تحتاج تدقيق المعلم:{" "}
                {currentPage.ocrAmbiguities.map((a: any) => `${a.type} (${a.snippet}) — ${a.reason}`).join(" | ")}
              </span>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">
              النص المستخرج القابل للتصحيح البشري قبل اعتماد الفهرس:
              {pageDirty && <span className="badge badge-warning" style={{ marginInlineStart: "8px" }}>تعديل غير محفوظ</span>}
            </label>
            <textarea
              className="form-textarea"
              value={correctedPageText}
              onChange={(e) => {
                setCorrectedPageText(e.target.value);
                setPageDirty(true);
              }}
              placeholder="النص المستخرج من الصفحة أو التفريغ اليدوي للصفحة الممسوحة..."
            />
          </div>

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={Boolean(aiProcessing) || savingPage}
              onClick={handleSavePageCorrection}
            >
              {savingPage ? "جارٍ الحفظ..." : "حفظ النص المصحح ورقم الصفحة المطبوعة"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={Boolean(aiProcessing) || savingPage || !currentSource || !currentPage}
              onClick={handleAiPageOcr}
            >
              {aiProcessing === "ocr"
                ? "جارٍ استخراج النص بالرؤية الذكية..."
                : "✨ استخراج النص بالرؤية الذكية (Vision OCR)"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={Boolean(aiProcessing) || savingPage || !currentSource}
              onClick={handleAiExtractStructure}
            >
              {aiProcessing === "extract"
                ? "جارٍ استخراج الفصول والدروس..."
                : currentSource.chapters?.length
                ? "📚 إعادة استخراج وإضافة فصول ودروس بالذكاء الاصطناعي"
                : "📚 استخراج الفصول والدروس تلقائيًا بالذكاء الاصطناعي"}
            </button>
          </div>
        </div>
      )}

      {!canRequestVerification && (
        <div className="blocker-banner">
          <span>
            ⛔ لا يمكن إتمام طلب المراجعة الرسمية: السنة الدراسية والطبعة ورابط المصدر واسم المراجع غير مكتملة. تبقى حالة التحقق معلّقة.
          </span>
        </div>
      )}

      {/* Import & Source Review Log Table matching `استيراد كتاب المنهج.png` */}
      <div className="card">
        <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>سجل الاستيراد ومراجعة المصدر</h3>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
          سجل تدقيق مصادر السياق النشط ({activeContext?.subject})
        </p>

        {loading ? (
          <div style={{ textAlign: "center", padding: "24px 12px", color: "var(--text-secondary)" }}>
            جارٍ تحميل المصادر...
          </div>
        ) : (
          <div className="table-scroll-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>السجل</th>
                  <th>الملف وبصمته</th>
                  <th>بيانات المصدر (سنة / طبعة / رابط)</th>
                  <th>حالة التحقق</th>
                  <th>تحديد</th>
                </tr>
              </thead>
              <tbody>
                {sources.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                      لا توجد مصادر مرفوعة بعد في هذا السياق.
                    </td>
                  </tr>
                ) : (
                  sources.map((s) => {
                    const isSelected = s.id === selectedSourceId;
                    return (
                      <tr
                        key={s.id}
                        onClick={() => bindSource(s)}
                        style={{
                          cursor: "pointer",
                          backgroundColor: isSelected ? "var(--primary-tint-bg)" : undefined,
                        }}
                      >
                        <td style={{ fontWeight: 700 }}>{s.title}</td>
                        <td>
                          {s.fileName || "لم يُختر ملف"}{" "}
                          {s.sha256Fingerprint ? `(${s.sha256Fingerprint.slice(0, 10)}...)` : ""}
                        </td>
                        <td>
                          {s.bookYear || s.edition
                            ? `السنة: ${s.bookYear || "—"} | الطبعة: ${s.edition || "—"}`
                            : "سنة / طبعة / رابط: غير مدخلة"}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              s.verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
                            }`}
                          >
                            {s.verificationStatus === "human_verified"
                              ? `موثّق (${s.reviewerName})`
                              : "معلّق · غير موثّق"}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className={`btn ${isSelected ? "btn-primary" : "btn-secondary"}`}
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              bindSource(s);
                            }}
                          >
                            {isSelected ? "محدّد" : "عرض"}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <Link href="/curriculum" className="btn btn-primary">
          ← متابعة إلى المنهج
        </Link>
        <Link href="/lessons" className="btn btn-secondary">
          الانتقال إلى اختيار الدرس
        </Link>
      </div>
    </div>
  );
}
