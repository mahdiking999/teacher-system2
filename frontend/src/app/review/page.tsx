"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function FinalReviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [correctionInput, setCorrectionInput] = useState<string>("");
  const [approverName, setApproverName] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [auditing, setAuditing] = useState<boolean>(false);
  const [savingCorrection, setSavingCorrection] = useState<boolean>(false);
  const [approving, setApproving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const runAuditForPlan = useCallback(
    async (planId: string, ctxId: string) => {
      if (!planId || !ctxId) return null;
      const audited = await apiFetch(
        `/api/plans/${encodeURIComponent(planId)}/audit?contextId=${encodeURIComponent(ctxId)}`,
        { method: "POST" }
      );
      return audited;
    },
    [apiFetch]
  );

  const loadPlans = useCallback(
    async (keepId?: string, runFreshAudit = true, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setSelectedPlanId("");
        setCorrectionInput("");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const res = await apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}`);
        if (isCancelled && isCancelled()) return;
        let list = res.items || [];

        let targetId =
          (keepId && list.some((p: any) => p.id === keepId) && keepId) ||
          (urlPlanId && list.some((p: any) => p.id === urlPlanId) && urlPlanId) ||
          "";

        if (!targetId) {
          setSelectedPlanId((prev) => {
            targetId = (prev && list.some((p: any) => p.id === prev) && prev) || list[0]?.id || "";
            return targetId;
          });
        } else {
          setSelectedPlanId(targetId);
        }

        if (targetId && runFreshAudit) {
          try {
            const audited = await runAuditForPlan(targetId, activeContextId);
            if (isCancelled && isCancelled()) return;
            if (audited) {
              list = list.map((p: any) => (p.id === audited.id ? audited : p));
            }
          } catch {
            // Fall back to existing review snapshot if audit endpoint fails transiently
          }
        }

        setPlans(list);
        const found = list.find((p: any) => p.id === targetId) || list[0] || null;
        if (found) {
          setSelectedPlanId(found.id);
          setCorrectionInput(found.formativeAssessment || "");
        } else {
          setSelectedPlanId("");
          setCorrectionInput("");
        }
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل الخطط للمراجعة.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch, urlPlanId, runAuditForPlan]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setSelectedPlanId("");
    setCorrectionInput("");
    setApproverName(activeContext?.teacherName || "المعلم المراجع");
    loadPlans(undefined, true, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeContext?.teacherName) {
      setApproverName((prev) => prev || activeContext.teacherName);
    }
  }, [activeContext?.teacherName]);

  const currentPlan = plans.find((p) => p.id === selectedPlanId) || null;
  const review = currentPlan?.latestReview || {
    blockersCount: 0,
    warningsCount: 0,
    passedCount: 0,
    findings: [],
  };

  const blockers = (review.findings || []).filter((f: any) => f.category === "BLOCKER");
  const hasMissingFormative = blockers.some((b: any) => b.code === "MISSING_FORMATIVE_ASSESSMENT");
  const otherBlockers = blockers.filter((b: any) => b.code !== "MISSING_FORMATIVE_ASSESSMENT");

  const getEditorRoute = (pln: any | null) => {
    if (!pln) return "/daily-plan";
    if (pln.planType === "five_day") return `/five-day-plan?planId=${encodeURIComponent(pln.id)}`;
    if (pln.planType === "weekly") return `/weekly-plan?planId=${encodeURIComponent(pln.id)}`;
    return `/daily-plan?planId=${encodeURIComponent(pln.id)}`;
  };

  const getTargetHref = (fieldTarget: string, pln: any | null) => {
    if (fieldTarget === "sourceId") return "/sources";
    if (fieldTarget === "context") return "/settings";
    if (fieldTarget === "teachingTools" || fieldTarget === "subjectItems") return "/tools";
    if (fieldTarget === "primaryLessonId") return "/lessons";
    return getEditorRoute(pln);
  };

  const handleSelectPlan = async (newId: string) => {
    setSelectedPlanId(newId);
    setFeedback("");
    setErrorMsg("");
    const found = plans.find((p) => p.id === newId);
    setCorrectionInput(found?.formativeAssessment || "");
    if (newId && activeContextId) {
      setAuditing(true);
      try {
        const audited = await runAuditForPlan(newId, activeContextId);
        if (audited) {
          setPlans((prev) => prev.map((p) => (p.id === audited.id ? audited : p)));
          setCorrectionInput(audited.formativeAssessment || "");
        }
      } catch (e: any) {
        setErrorMsg(e?.message || "تعذر تحديث نتائج التدقيق لهذه الخطة.");
      } finally {
        setAuditing(false);
      }
    }
  };

  const handleManualReAudit = async () => {
    if (!currentPlan) return;
    setAuditing(true);
    setErrorMsg("");
    setFeedback("");
    try {
      const audited = await runAuditForPlan(currentPlan.id, activeContextId);
      if (audited) {
        setPlans((prev) => prev.map((p) => (p.id === audited.id ? audited : p)));
        setFeedback(`تمت إعادة فحص الخطة (v${audited.version}) وفق أحدث بيانات السياق والمصدر.`);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر إعادة التدقيق.");
    } finally {
      setAuditing(false);
    }
  };

  const handleApplyCorrectionAndReAudit = async () => {
    if (!currentPlan) return;
    if (!correctionInput.trim()) {
      setErrorMsg("يرجى إدخال صياغة التقويم التكويني قبل تطبيق التصحيح.");
      return;
    }
    setSavingCorrection(true);
    setErrorMsg("");
    setFeedback("");
    try {
      const updated = await apiFetch(`/api/plans/${currentPlan.id}`, {
        method: "PUT",
        body: JSON.stringify({
          ...currentPlan,
          formativeAssessment: correctionInput.trim(),
          expectedVersion: currentPlan.version,
        }),
      });
      setFeedback(`تم تحديث حقل التقويم وإعادة فحص الاكتمال للإصدار (v${updated.version}).`);
      await loadPlans(updated.id, false);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر تطبيق التصحيح.");
    } finally {
      setSavingCorrection(false);
    }
  };

  const handleApprovePlan = async () => {
    if (!currentPlan) return;
    setApproving(true);
    setErrorMsg("");
    setFeedback("");
    try {
      const approved = await apiFetch(
        `/api/plans/${currentPlan.id}/approve?contextId=${encodeURIComponent(activeContextId)}&approverName=${encodeURIComponent(
          approverName.trim() || "المعلم المراجع"
        )}`,
        { method: "POST" }
      );
      setFeedback(
        `تم اعتماد الإصدار المحفوظ (v${approved.approvedVersion}) بواسطة «${approved.approvedBy}». أي تعديل لاحق سيُنشئ إصدارًا جديدًا ويزيل الاعتماد عن النسخة الجديدة مع الاحتفاظ بسجل الإصدار المعتمد.`
      );
      await loadPlans(approved.id, false);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر اعتماد الخطة.");
    } finally {
      setApproving(false);
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / مراجعة الخطة
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <h1 className="page-title">مراجعة الخطة</h1>
          <p className="page-subtitle">
            افصل بين اكتمال الخطة تربويًا وتوثيق مصدر المنهج؛ كل منهما يحتاج مراجعة مستقلة.
          </p>
        </div>

        {plans.length > 0 && (
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            <select
              aria-label="اختيار الخطة للمراجعة"
              className="form-select"
              style={{ width: "auto" }}
              value={selectedPlanId}
              onChange={(e) => handleSelectPlan(e.target.value)}
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.planType === "daily" ? "يومية" : p.planType === "weekly" ? "أسبوعية" : "خمسة أيام"} · v{p.version})
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-secondary" onClick={handleManualReAudit} disabled={auditing || !currentPlan}>
              {auditing ? "جارٍ التدقيق..." : "↻ تحديث التدقيق"}
            </button>
          </div>
        )}
      </div>

      <div className="info-banner">
        <span>
          ⓘ نتائج فحص الاكتمال والتدقيق التخصصي والرياضي أدناه محسوبة فعليًا من محرك التدقيق في خلفية Python FastAPI.
        </span>
      </div>

      <WorkflowStepper activeStep={7} />

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

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 16px", color: "var(--text-secondary)" }}>
          جارٍ تحميل الخطط وفحص الاكتمال...
        </div>
      ) : plans.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "44px 16px" }}>
          <div style={{ fontSize: "2rem", marginBottom: "8px" }}>✓</div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: "8px" }}>لا توجد خطط محفوظة للمراجعة بعد</h2>
          <p style={{ fontSize: "0.86rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
            أنشئ خطة يومية أو أسبوعية أولاً ليتم فحص اكتمالها وتدقيق عناصرها واعتمادها رسميًا.
          </p>
          <Link href="/daily-plan" className="btn btn-primary">
            + إعداد أول خطة يومية
          </Link>
        </div>
      ) : (
        <>
          {/* 3 Top Summary Cards matching `مراجعة الخطة.png` */}
          <div className="stats-grid-3">
            <div className="stat-card">
              <div className="stat-label">حقل يمنع اكتمال الخطة (عوائق الاعتماد)</div>
              <div className="stat-number" style={{ color: review.blockersCount > 0 ? "var(--blocker-text)" : "var(--text-main)" }}>
                {review.blockersCount}
              </div>
              <div className="stat-sub">{blockers[0]?.title || "لا توجد عوائق مانعة للاعتماد"}</div>
            </div>

            <div className="stat-card">
              <div className="stat-label">تحذير يحتاج مراجعة مصدر (غير مانع)</div>
              <div className="stat-number" style={{ color: "var(--warning-text)" }}>
                {review.warningsCount}
              </div>
              <div className="stat-sub">المنهج غير موثّق / أمثلة مؤلفة</div>
            </div>

            <div className="stat-card">
              <div className="stat-label">فحوص اكتمال ناجحة</div>
              <div className="stat-number" style={{ color: "var(--primary-green)" }}>
                {review.passedCount}
              </div>
              <div className="stat-sub">المدة والأهداف والوسائل والحساب</div>
            </div>
          </div>

          {/* Main Split matching `مراجعة الخطة.png`: Completeness Check Findings (2/3) & Draft Summary Sidebar (1/3) */}
          <div className="main-split-grid">
            <div className="card">
              <h3 style={{ fontSize: "1.2rem", fontWeight: 800, marginBottom: "2px" }}>نتائج فحص الاكتمال</h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                حالة المسودة الحالية (
                {currentPlan?.status === "approved"
                  ? "معتمدة"
                  : currentPlan?.status === "reviewed"
                  ? "مراجعة"
                  : "تحتاج تعديلًا / مسودة"}
                ) · لا تُعدّ هذه الفحوص اعتمادًا تلقائيًا لمصدر الكتاب
              </p>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {(review.findings || []).map((f: any, idx: number) => {
                  const isBlocker = f.category === "BLOCKER";
                  const isWarning = f.category === "SOURCE_WARNING";
                  const targetHref = getTargetHref(f.fieldTarget, currentPlan);

                  return (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        padding: "14px 16px",
                        borderRadius: "12px",
                        border: "1px solid var(--border-subtle)",
                        backgroundColor: isBlocker ? "#fffafa" : isWarning ? "#fffdf5" : "#fbfcfb",
                        gap: "12px",
                      }}
                    >
                      <div style={{ display: "flex", gap: "12px", alignItems: "flex-start", flex: "1 1 220px" }}>
                        <span
                          style={{
                            width: "34px",
                            height: "34px",
                            borderRadius: "8px",
                            backgroundColor: isBlocker
                              ? "var(--blocker-bg)"
                              : isWarning
                              ? "var(--warning-bg)"
                              : "var(--primary-tint-bg)",
                            color: isBlocker
                              ? "var(--blocker-text)"
                              : isWarning
                              ? "var(--warning-text)"
                              : "var(--primary-green)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontWeight: 800,
                            flexShrink: 0,
                          }}
                        >
                          {isBlocker ? "!" : isWarning ? "🛡" : "✓"}
                        </span>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: "0.95rem", marginBottom: "2px" }}>{f.title}</div>
                          <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                            {f.description}{" "}
                            {(isBlocker || isWarning) && (
                              <Link
                                href={targetHref}
                                style={{ color: "var(--primary-green)", fontWeight: 700, textDecoration: "none", marginInlineStart: "6px" }}
                              >
                                {isWarning ? "استكمال البيانات ←" : "إصلاح الحقل ←"}
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>

                      <span
                        className={`badge ${
                          isBlocker ? "badge-blocker" : isWarning ? "badge-warning" : "badge-success"
                        }`}
                      >
                        {isBlocker ? "مانع" : isWarning ? "تحذير" : "ناجح"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Left Column in RTL: Draft Summary & Approval Gate */}
            <div className="card">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "6px" }}>ملخّص المسودة</h3>
              <div style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: "8px" }}>
                {currentPlan?.title || "خطة غير محددة"}
              </div>

              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                {currentPlan?.status !== "approved" && (
                  <span className="badge badge-warning">مسودة قيد المراجعة</span>
                )}
                <span
                  className={`badge ${
                    currentPlan?.status === "approved"
                      ? "badge-success"
                      : review.blockersCount > 0
                      ? "badge-blocker"
                      : "badge-success"
                  }`}
                >
                  الحالة:{" "}
                  {currentPlan?.status === "approved"
                    ? `معتمدة (v${currentPlan.approvedVersion})`
                    : review.blockersCount > 0
                    ? "تحتاج تعديلًا"
                    : "مراجعة — جاهزة للاعتماد"}
                </span>
              </div>

              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                خطة {currentPlan?.planType === "daily" ? "يومية" : currentPlan?.planType === "weekly" ? "أسبوعية" : "خمسة أيام"} ·{" "}
                {currentPlan?.planType === "daily"
                  ? `${currentPlan?.totalAllocatedMinutes || 45} دقيقة`
                  : `${(currentPlan?.scheduleDays || []).reduce((a: number, d: any) => a + (d.isHoliday ? 0 : Number(d.minutes) || 0), 0)} دقيقة`}
                {currentPlan?.sectionName ? ` · ${currentPlan.sectionName}` : ""}
                <br />
                {activeContext?.subject} · {activeContext?.grade} · {activeContext?.country}
              </p>

              {review.blockersCount > 0 ? (
                <div className="blocker-banner" style={{ marginBottom: "12px" }}>
                  <span>⛔ غير مكتملة: عالج العوائق المانعة قبل الاعتماد أو الانتقال إلى المخرجات المعتمدة.</span>
                </div>
              ) : (
                <div className="info-banner" style={{ marginBottom: "12px", borderColor: "var(--primary-green)", color: "var(--primary-green)" }}>
                  <span>✓ لا توجد عوائق اعتماد! يمكنك اعتماد هذا الإصدار وتوليد المخرجات الآن.</span>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">اسم المراجع / المعتمد</label>
                <input
                  className="form-input"
                  value={approverName}
                  onChange={(e) => setApproverName(e.target.value)}
                  placeholder="أدخل اسم المراجع..."
                  disabled={currentPlan?.status === "approved"}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <Link href={getEditorRoute(currentPlan)} className="btn btn-secondary" style={{ width: "100%" }}>
                  العودة إلى المحرّر للتعديل
                </Link>

                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={review.blockersCount > 0 || currentPlan?.status === "approved" || approving}
                  title={
                    currentPlan?.status === "approved"
                      ? "تم اعتماد هذا الإصدار بالفعل"
                      : review.blockersCount > 0
                      ? "الزر معطل لوجود عائق اعتماد"
                      : "اعتماد الإصدار الحالي"
                  }
                  onClick={handleApprovePlan}
                  style={{ width: "100%" }}
                >
                  {approving
                    ? "جارٍ الاعتماد..."
                    : currentPlan?.status === "approved"
                    ? `✓ معتمدة (الإصدار v${currentPlan.approvedVersion})`
                    : "اعتماد الإصدار المحفوظ"}
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={review.blockersCount > 0 || !currentPlan}
                  title={
                    review.blockersCount > 0
                      ? "أكمل الحقول المانعة أولًا قبل إنشاء حزمة المخرجات المعتمدة"
                      : "الانتقال إلى تصدير الحزمة"
                  }
                  onClick={() => router.push(`/export-package?planId=${encodeURIComponent(currentPlan.id)}`)}
                  style={{ width: "100%" }}
                >
                  إنشاء المخرجات الآن (DOCX / PDF / PPTX)
                </button>
              </div>
            </div>
          </div>

          {/* Non-formative blockers guidance when present */}
          {otherBlockers.length > 0 && (
            <div className="card" style={{ borderColor: "var(--blocker-border)" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--blocker-text)", marginBottom: "8px" }}>
                عوائق تتطلب المعالجة في المحرر ({otherBlockers.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {otherBlockers.map((b: any, i: number) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "10px",
                      padding: "10px 12px",
                      borderRadius: "8px",
                      backgroundColor: "#fffafa",
                      border: "1px solid #fecaca",
                    }}
                  >
                    <div>
                      <strong>{b.title}:</strong> {b.remediation || b.description}
                    </div>
                    <Link href={getTargetHref(b.fieldTarget, currentPlan)} className="btn btn-secondary" style={{ padding: "5px 12px", fontSize: "0.8rem" }}>
                      فتح الحقل لإصلاحه ←
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Direct Correction Box for Formative Assessment (prominent when missing, quick-edit otherwise) */}
          {(hasMissingFormative || currentPlan?.planType === "daily") && (
            <div className="card">
              <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "2px" }}>
                {hasMissingFormative
                  ? "تصحيح مباشر ومعاينة: إدخال طريقة تقويم"
                  : "تحرير سريع لحقل التقويم التكويني"}
              </h3>
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                مقارنة مرئية قبل التعديل وبعده · يمكنك تطبيق التعديل مباشرة على الخطة المحفوظة وإعادة فحص الاكتمال
              </p>

              <div className="equal-split-grid">
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <label className="form-label">طريقة التقويم الحالية في الخطة</label>
                    <span className={`badge ${currentPlan?.formativeAssessment ? "badge-success" : "badge-blocker"}`}>
                      {currentPlan?.formativeAssessment ? "مدخلة" : "قبل التصحيح · ناقص"}
                    </span>
                  </div>
                  <textarea
                    className={`form-textarea ${!currentPlan?.formativeAssessment ? "error-border" : ""}`}
                    readOnly
                    value={currentPlan?.formativeAssessment || "لم تُدخل طريقة تقويم"}
                  />
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <label className="form-label">طريقة التقويم · صياغة قابلة للتطبيق الفوري</label>
                    <span className="badge badge-success">صياغة محرّرة</span>
                  </div>
                  <textarea
                    className="form-textarea"
                    placeholder="أدخل طريقة التقويم التكويني مرتبطة بالأهداف..."
                    value={correctionInput}
                    onChange={(e) => setCorrectionInput(e.target.value)}
                  />
                </div>
              </div>

              <div className="warning-banner" style={{ marginTop: "12px", marginBottom: 0 }}>
                <span>
                  🛡 بعد إدخال الطريقة يصبح فحص التقويم مكتملًا، لكن حالة المصدر تبقى مستقلّة ولا تتوثق إلا بعد مراجعة الكتاب في صفحة المصادر.
                </span>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            {(hasMissingFormative || currentPlan?.planType === "daily") && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleApplyCorrectionAndReAudit}
                disabled={savingCorrection}
              >
                {savingCorrection ? "جارٍ التطبيق والفحص..." : "↻ تطبيق تعديل التقويم وإعادة الفحص"}
              </button>
            )}
            <Link href="/reports" className="btn btn-secondary">
              متابعة إلى التقارير ←
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default function FinalReviewPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <FinalReviewContent />
    </Suspense>
  );
}
