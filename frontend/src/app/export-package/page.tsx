"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function formatPlanStatusLabel(status?: string) {
  if (status === "approved") return "معتمدة";
  if (status === "reviewed") return "مكتملة المراجعة";
  if (status === "needs_revision") return "تحتاج تعديلًا";
  return "مسودة";
}

function ExportPackageContent() {
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch, downloadFile } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [exportsList, setExportsList] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [busyFormat, setBusyFormat] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [lastExportLink, setLastExportLink] = useState<{ url: string; fileName: string } | null>(null);

  const loadData = useCallback(
    async (isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setSources([]);
        setExportsList([]);
        setSelectedPlanId("");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [pRes, eRes, sRes] = await Promise.all([
          apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/exports?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const pList = pRes.items || [];
        setPlans(pList);
        setExportsList(eRes.items || []);
        setSources(sRes.items || []);

        setSelectedPlanId((prev) => {
          if (urlPlanId && pList.some((p: any) => p.id === urlPlanId)) return urlPlanId;
          if (prev && pList.some((p: any) => p.id === prev)) return prev;
          return pList[0]?.id || "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل بيانات التصدير والحزم.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch, urlPlanId]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setLastExportLink(null);
    setSelectedPlanId("");
    loadData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentPlan = plans.find((p) => p.id === selectedPlanId) || null;
  const hasVerifiedSource = sources.some((s: any) => s.verificationStatus === "human_verified");
  const planTypeNoun =
    currentPlan?.planType === "weekly"
      ? "الأسبوعية"
      : currentPlan?.planType === "five_day"
      ? "خمسة أيام"
      : "اليومية";

  const packageItems = [
    {
      id: "docx",
      title: `الخطة ${planTypeNoun} القابلة للتحرير`,
      desc: "ملف OOXML DOCX بجداول وفقرات قابلة للتحرير واتجاه RTL/LTR",
      badge: "DOCX",
    },
    {
      id: "pdf",
      title: `نسخة قراءة وطباعة من الخطة ${planTypeNoun}`,
      desc: "ملف PDF 1.7 بنص قابل للتحديد وجداول متجهية",
      badge: "PDF",
    },
    {
      id: "pptx",
      title: "عرض تقديمي قابل للتحرير",
      desc: "شرائح تربوية بنصوص وعناصر وأشكال OOXML قابلة للتحرير في PowerPoint",
      badge: "PPTX",
    },
    {
      id: "report_pdf",
      title: "تقرير التخطيط والاكتمال",
      desc: "ملخص الخطط والمراجعات ونواقص التوثيق دون نسب نجاح طلاب مفترضة",
      badge: "PDF",
    },
    {
      id: "bundle_zip",
      title: "حزمة شاملة (تشمل سجل بيانات المصدر JSON + جميع الملفات)",
      desc: "جميع الملفات الأربعة مع سجل بيانات المصدر وبصمة الإصدار في أرشيف واحد",
      badge: "ZIP + JSON",
    },
  ];

  const handleGenerateExport = async (fmt: string) => {
    if (!currentPlan) {
      setErrorMsg("اختر خطة محفوظة أولًا قبل توليد المخرجات.");
      return;
    }
    setBusyFormat(fmt);
    setFeedback("");
    setErrorMsg("");
    setLastExportLink(null);
    try {
      const created = await apiFetch("/api/exports", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          planId: currentPlan.id,
          exportFormat: fmt,
        }),
      });
      setLastExportLink({ url: created.downloadUrl, fileName: created.fileName });
      setFeedback(
        `تم إنشاء وفحص الملف (${created.fileName}) للإصدار v${created.planVersion} بنجاح (البصمة SHA-256: ${created.contentSha256.slice(
          0,
          16
        )}...).`
      );
      await downloadFile(created.downloadUrl, created.fileName);
      await loadData();
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر توليد الملف المطلوب.");
    } finally {
      setBusyFormat("");
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / تصدير الحزمة
      </div>
      <h1 className="page-title">تصدير الحزمة والمستندات الفعلية</h1>
      <p className="page-subtitle">
        اجمع الخطة والعرض والتقرير وبيانات المصدر في ملفات حقيقية قابلة للفتح والتحرير، مرتبطة بإصدار محفوظ محدد مع الحفاظ على تنبيه التوثيق.
      </p>

      <div className="info-banner">
        <span>
          ⓘ يُصدّر كل ملف من إصدار محفوظ محدد (v{currentPlan?.version || 1}) ويُفحص بنيويًا (OOXML / PDF 1.7) قبل إتاحته للتنزيل. تعديل الخطة لاحقًا لا يغيّر الملفات المصدّرة سابقًا.
        </span>
      </div>

      <WorkflowStepper activeStep={10} />

      <div className={hasVerifiedSource ? "info-banner" : "warning-banner"}>
        <span>
          {hasVerifiedSource
            ? "✓ مصدر المنهج موثّق ومعتمد؛ تُرفق بيانات التوثيق ولقطة السياق السبعة بكل المخرجات."
            : "⚠ سجل منهج تجريبي — غير موثّق: تُرفق حالة التوثيق ولقطة السياق السبعة بكل المخرجات بصدق دون وضع ختم اعتماد كاذب على المسودات."}
        </span>
      </div>

      {feedback && (
        <div className="info-banner" style={{ borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
          <span>✓ {feedback}</span>
          {lastExportLink && (
            <button type="button" onClick={() => downloadFile(lastExportLink.url, lastExportLink.fileName)} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.78rem" }}>
              تنزيل {lastExportLink.fileName}
            </button>
          )}
        </div>
      )}

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {/* Main Split matching `تصدير الحزمة.png`: Included Outputs List (2/3) & Package Summary + Preparation Status (1/3) */}
      <div className="main-split-grid">
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
            <div>
              <h3 style={{ fontSize: "1.15rem", fontWeight: 800 }}>المخرجات المشمولة القابلة للتوليد الفوري</h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                اختر الخطة المراد تصديرها واضغط على أي صيغة لتوليد وتنزيل الملف الحقيقي
              </p>
            </div>

            {plans.length > 0 ? (
              <select
                aria-label="اختيار الخطة للتصدير"
                className="form-select"
                style={{ width: "auto" }}
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
              >
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} (الإصدار v{p.version})
                  </option>
                ))}
              </select>
            ) : (
              <span className="badge badge-warning">لا توجد خطة محددة</span>
            )}
          </div>

          {loading ? (
            <div style={{ textAlign: "center", padding: "30px 12px", color: "var(--text-secondary)" }}>
              جارٍ تحميل الخطط وسجل التصدير...
            </div>
          ) : plans.length === 0 ? (
            <div style={{ textAlign: "center", padding: "30px 12px", color: "var(--text-secondary)" }}>
              <p style={{ marginBottom: "12px" }}>لا توجد خطط محفوظة للتصدير في هذا السياق بعد.</p>
              <Link href="/daily-plan" className="btn btn-primary">
                + إنشاء خطة جديدة
              </Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {packageItems.map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: "14px 16px",
                    borderRadius: "12px",
                    border: "1px solid var(--border-color)",
                    backgroundColor: "#fbfcfb",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "12px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ display: "flex", gap: "12px", alignItems: "center", flex: "1 1 220px" }}>
                    <span style={{ color: "var(--primary-green)", fontWeight: 800, fontSize: "1.1rem" }}>☑</span>
                    <div>
                      <div style={{ fontWeight: 800, fontSize: "0.95rem" }}>{item.title}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{item.desc}</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <span className="badge badge-success">{item.badge}</span>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                      disabled={!!busyFormat || !currentPlan}
                      onClick={() => handleGenerateExport(item.id)}
                    >
                      {busyFormat === item.id ? "جارٍ التوليد..." : `توليد وتنزيل ${item.badge}`}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="card">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "4px" }}>ملخّص الحزمة</h3>
            <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
              5 عناصر مختارة · مرتبطة بالسياق النشط ({activeContext?.subject})
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>{currentPlan?.title || "لا توجد خطة محددة"}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    الإصدار v{currentPlan?.version || 1} ·{" "}
                    {currentPlan?.planType === "daily"
                      ? `${currentPlan?.totalAllocatedMinutes || 45} دقيقة`
                      : currentPlan
                      ? `${(currentPlan.scheduleDays || []).reduce((a: number, d: any) => a + (d.isHoliday ? 0 : Number(d.minutes) || 0), 0)} دقيقة`
                      : "—"}
                  </div>
                </div>
                <span className="badge badge-neutral">خطة {planTypeNoun}</span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>المراجعة التربوية</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    حالة الخطة: {formatPlanStatusLabel(currentPlan?.status)}
                  </div>
                </div>
                <span
                  className={`badge ${
                    currentPlan?.status === "approved" || currentPlan?.status === "reviewed"
                      ? "badge-success"
                      : currentPlan?.status === "needs_revision"
                      ? "badge-blocker"
                      : "badge-warning"
                  }`}
                >
                  {formatPlanStatusLabel(currentPlan?.status)}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>مراجعة المصدر</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    تُوثّق في ترويسة المستندات وسجل JSON
                  </div>
                </div>
                <span className={`badge ${hasVerifiedSource ? "badge-success" : "badge-warning"}`}>
                  {hasVerifiedSource ? "موثّق" : "معلّق"}
                </span>
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              style={{ width: "100%" }}
              disabled={!!busyFormat || !currentPlan}
              onClick={() => handleGenerateExport("bundle_zip")}
            >
              📦 {busyFormat === "bundle_zip" ? "جارٍ تجميع الحزمة..." : "تجهيز وتنزيل الحزمة الكاملة (ZIP)"}
            </button>
          </div>

          <div className="card">
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "6px" }}>حالة التجهيز والفحص البنيوي</h3>
            <span className="badge badge-success" style={{ marginBottom: "8px" }}>
              فحص OOXML وPDF 1.7 مفعّل
            </span>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              كل ملف مولّد يمر بفحص بنيوي مستقل يتحقق من صلاحية جداول وفقرات `word/document.xml`، وشرائح `ppt/slides/slide*.xml`، وهيكل `%PDF-1.7` قبل تسليمه.
            </p>
          </div>
        </div>
      </div>

      {/* Export Package History Table matching `تصدير الحزمة.png` */}
      <div className="card">
        <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>سجل الحزم والملفات المصدّرة</h3>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
          جميع عمليات التصدير المحفوظة فعليًا في قاعدة البيانات للسياق النشط ({exportsList.length} ملفات)
        </p>

        <div className="table-scroll-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>الملف المصدّر</th>
                <th>الصيغة والإصدار</th>
                <th>بصمة المحتوى (SHA-256)</th>
                <th>فحص البنية</th>
                <th>الإجراء</th>
              </tr>
            </thead>
            <tbody>
              {exportsList.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                    اضغط على أي زر تصدير أعلاه لتوليد ملف DOCX أو PDF أو PPTX أو حزمة كاملة.
                  </td>
                </tr>
              ) : (
                exportsList.map((ex) => (
                  <tr key={ex.id}>
                    <td style={{ fontWeight: 700 }}>{ex.fileName}</td>
                    <td>
                      <span className="badge badge-neutral">{ex.exportFormat.toUpperCase()}</span> · v{ex.planVersion}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
                      {ex.contentSha256?.slice(0, 18)}...
                    </td>
                    <td>
                      <span className={`badge ${ex.structuralCheckPassed ? "badge-success" : "badge-blocker"}`}>
                        {ex.structuralCheckPassed ? "✓ سليم وقابل للفتح" : "فشل الفحص"}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={() => downloadFile(`/api/exports/${ex.id}/download?contextId=${encodeURIComponent(activeContextId)}`, ex.fileName)}
                        className="btn btn-secondary"
                        style={{ padding: "5px 12px", fontSize: "0.78rem" }}
                      >
                        تنزيل الملف الفعلي
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <Link href="/presentations" className="btn btn-secondary">
          ← العودة إلى العرض التقديمي
        </Link>
      </div>
    </div>
  );
}

export default function ExportPackagePage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <ExportPackageContent />
    </Suspense>
  );
}
