"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function FiveDayPlanContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [title, setTitle] = useState<string>("خطة خمسة أيام");
  const [sourceId, setSourceId] = useState<string>("");
  const [days, setDays] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const buildDefaultDays = useCallback(
    (lList: any[]) =>
      (activeContext?.schoolDays || ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"])
        .slice(0, 5)
        .map((dName, i) => ({
          dayNumber: i + 1,
          dayName: dName,
          isHoliday: false,
          lessonId: i === 0 ? lList[0]?.id || "" : "",
          lessonTitle: i === 0 ? lList[0]?.title || (activeContext ? `درس 1 — ${activeContext.subject}` : "درس 1") : "",
          linkedDailyPlanId: "",
          objectives: i === 0 ? "تحقيق أهداف اليوم الأول" : "",
          activities: "سبورة وأقلام ملوّنة وبطاقات",
          assessment: i === 0 ? "ملاحظة أداء المتعلمين" : "",
          minutes: activeContext?.defaultPeriodMinutes || 45,
        })),
    [activeContext]
  );

  const bindPlan = useCallback((pln: any) => {
    setSelectedPlanId(pln.id);
    setTitle(pln.title || "خطة خمسة أيام");
    setSourceId(pln.sourceId || "");
    setDays(pln.scheduleDays || []);
  }, []);

  const loadFiveDayPlan = useCallback(
    async (keepId?: string, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setSelectedPlanId("");
        setLessons([]);
        setSources([]);
        setDays([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [pRes, lRes, sRes] = await Promise.all([
          apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}&planType=five_day`),
          apiFetch(`/api/lessons?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const pList = pRes.items || [];
        const lList = lRes.items || [];
        const sList = sRes.items || [];
        setPlans(pList);
        setLessons(lList);
        setSources(sList);

        setSelectedPlanId((prev) => {
          const targetId =
            (keepId && pList.some((p: any) => p.id === keepId) && keepId) ||
            (urlPlanId && pList.some((p: any) => p.id === urlPlanId) && urlPlanId) ||
            (prev && pList.some((p: any) => p.id === prev) && prev) ||
            pList[0]?.id ||
            "";
          const found = pList.find((p: any) => p.id === targetId) || null;
          if (found) {
            bindPlan(found);
            return found.id;
          }
          setTitle(`خطة خمسة أيام — ${activeContext?.subject || "المادة"}`);
          setSourceId(sList[0]?.id || "");
          setDays(buildDefaultDays(lList));
          return "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل خطة الخمسة أيام.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, activeContext?.subject, apiFetch, urlPlanId, bindPlan, buildDefaultDays]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setSelectedPlanId("");
    loadFiveDayPlan(undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentPlan = plans.find((p) => p.id === selectedPlanId) || null;
  const chosenSource = sources.find((s) => s.id === (sourceId || currentPlan?.sourceId));
  const hasVerifiedSource = chosenSource?.verificationStatus === "human_verified" || currentPlan?.contentOrigin === "documented_source";

  const scheduledDaysCount = days.filter((d) => String(d.lessonTitle || "").trim() !== "").length;
  const readyForReviewCount = days.filter(
    (d) => String(d.lessonTitle || "").trim() !== "" && String(d.assessment || "").trim() !== ""
  ).length;
  const totalMinutes = days.reduce(
    (acc, d) => acc + (d.isHoliday ? 0 : Number(d.minutes ?? activeContext?.defaultPeriodMinutes ?? 45)),
    0
  );

  const handleSaveFiveDayPlan = async (): Promise<string | null> => {
    if (!activeContextId) return null;
    setSaving(true);
    setErrorMsg("");
    setFeedback("");
    const computedOrigin = hasVerifiedSource ? "documented_source" : "authored_example";
    try {
      if (currentPlan && currentPlan.id) {
        const updated = await apiFetch(`/api/plans/${currentPlan.id}`, {
          method: "PUT",
          body: JSON.stringify({
            ...currentPlan,
            title: title.trim() || currentPlan.title,
            sourceId: sourceId || null,
            scheduleDays: days,
            contentOrigin: computedOrigin,
            expectedVersion: currentPlan.version,
          }),
        });
        setFeedback(`تم حفظ خطة الخمسة أيام (الإصدار v${updated.version}) بنجاح.`);
        await loadFiveDayPlan(updated.id);
        return updated.id;
      } else {
        const created = await apiFetch("/api/plans", {
          method: "POST",
          body: JSON.stringify({
            contextId: activeContextId,
            sourceId: sourceId || null,
            title: title.trim() || `خطة خمسة أيام — ${activeContext?.subject || "المادة"}`,
            planType: "five_day",
            periodMinutes: activeContext?.defaultPeriodMinutes || 45,
            periodsCount: 1,
            objectives: ["توزيع حصص مرن لخمسة أيام تدريس متميزة."],
            formativeAssessment: "متابعة التقويم اليومي لخمسة أيام تدريس.",
            scheduleDays: days,
            contentOrigin: computedOrigin,
          }),
        });
        setFeedback("تم إنشاء وحفظ خطة الخمسة أيام بنجاح.");
        await loadFiveDayPlan(created.id);
        return created.id;
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ خطة الخمسة أيام.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndGoToReview = async () => {
    const savedId = await handleSaveFiveDayPlan();
    if (savedId) {
      router.push(`/review?planId=${encodeURIComponent(savedId)}`);
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / خطة خمسة أيام
      </div>
      <h1 className="page-title">خطة خمسة أيام</h1>
      <p className="page-subtitle">
        توزيع حصص مرن لخمسة أيام تدريس متميزة بحسب جدول المعلم، دون افتراض تسلسل رسمي للدروس أو تقويم غربي ثابت.
      </p>

      <div className="info-banner">
        <span>
          ⓘ لكل يوم من الأيام الخمسة اسم يوم قابل للتعديل بحسب إعداد الدوام، ودرس وأهداف وأنشطة وتقويم وزمن مستقل.
        </span>
      </div>

      <WorkflowStepper activeStep={6} />

      {/* Switcher between Five-Day & Weekly matching `خطة خمسة أيام.png` */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          backgroundColor: "#eef2ef",
          padding: "5px",
          borderRadius: "10px",
          marginBottom: "16px",
          border: "1px solid var(--border-color)",
        }}
      >
        <div
          style={{
            padding: "10px",
            borderRadius: "8px",
            backgroundColor: "#ffffff",
            color: "var(--primary-green)",
            fontWeight: 800,
            textAlign: "center",
          }}
        >
          خمسة أيام
        </div>
        <Link
          href="/weekly-plan"
          style={{
            padding: "10px",
            borderRadius: "8px",
            color: "var(--text-secondary)",
            fontWeight: 600,
            textAlign: "center",
            textDecoration: "none",
          }}
        >
          أسبوعية (تشمل أيام الدوام والعطل)
        </Link>
      </div>

      <div className={hasVerifiedSource ? "info-banner" : "warning-banner"}>
        <span>
          {hasVerifiedSource
            ? `✓ المصدر المرتبط (${chosenSource?.title || "موثّق"}) معتمد؛ يبقى ترتيب الأيام الخمسة مرنًا وفق جدول المعلم.`
            : "⚠ سجل منهج تجريبي · غير موثّق. الأيام ترتيب تخطيطي تجريبي؛ ليست توزيعًا رسميًا للمنهج."}
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

      {/* 3 Summary Stat Cards matching `خطة خمسة أيام.png` */}
      <div className="stats-grid-3">
        <div className="stat-card">
          <div className="stat-label">حصص محدّد لها درس</div>
          <div className="stat-number">
            {scheduledDaysCount} من {days.length || 5}
          </div>
          <div className="stat-sub">
            {hasVerifiedSource ? "مرتبطة بمصدر موثّق" : "جميع الدروس تجريبية — غير موثّقة"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">حصص جاهزة للمراجعة</div>
          <div className="stat-number">
            {readyForReviewCount} من {days.length || 5}
          </div>
          <div className="stat-sub">
            {hasVerifiedSource ? "تم التحقق من المصدر" : "توثيق المصدر ما زال معلّقًا"}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">إجمالي الزمن المحجوز</div>
          <div className="stat-number">{totalMinutes} دقيقة</div>
          <div className="stat-sub">
            مجموع دقائق الأيام المجدولة
          </div>
        </div>
      </div>

      {/* Plan Title & Source Selector */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800 }}>إعدادات خطة الخمسة أيام</h3>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {plans.length > 0 && (
              <select
                aria-label="اختيار خطة خمسة أيام محفوظة"
                className="form-select"
                style={{ width: "auto" }}
                value={selectedPlanId}
                onChange={(e) => {
                  const found = plans.find((p) => p.id === e.target.value);
                  if (found) bindPlan(found);
                }}
              >
                {!selectedPlanId && <option value="">— خطة جديدة —</option>}
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} (v{p.version})
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setSelectedPlanId("");
                setTitle(`خطة خمسة أيام جديدة — ${activeContext?.subject || "المادة"}`);
                setSourceId(sources[0]?.id || "");
                setDays(buildDefaultDays(lessons));
                setFeedback("");
                setErrorMsg("");
              }}
            >
              + خطة خمسة أيام جديدة
            </button>
          </div>
        </div>

        <div className="equal-split-grid">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">عنوان الخطة</label>
            <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">مصدر المنهج المرتبط</label>
            <select className="form-select" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              <option value="">— غير مرتبط بمصدر —</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({s.verificationStatus === "human_verified" ? "موثّق" : "معلّق"})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 5-Day Editable Schedule Table matching `خطة خمسة أيام.png` */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 800 }}>جدول الحصص (خمسة أيام تدريس)</h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              {activeContext?.sectionName || "الشعبة"} · {activeContext?.teacherName || "المعلم"} · أسبوع يحدّده المعلم
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: "0.8rem", padding: "6px 12px" }}
            onClick={() => {
              const filled = days.map((d, idx) => {
                const pickedLesson = lessons.length > 0 ? lessons[idx % lessons.length] : null;
                return {
                  ...d,
                  lessonId: d.lessonId || pickedLesson?.id || "",
                  lessonTitle: d.lessonTitle || pickedLesson?.title || `درس اليوم ${idx + 1}`,
                  activities: d.activities || "سبورة وأقلام ملوّنة وبطاقات",
                  assessment: d.assessment || "سؤال تقويمي وملاحظة أداء مرتبطة بالهدف",
                };
              });
              setDays(filled);
              setErrorMsg("");
              setFeedback("تم استكمال جدولة وتقويم الأيام الخمسة؛ اضغط حفظ المسودة لتثبيتها.");
            }}
          >
            استكمال جدولة الأيام الخمسة تلقائيًا للمراجعة
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "30px 12px", color: "var(--text-secondary)" }}>
            جارٍ تحميل جدول الحصص...
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {days.map((d, idx) => {
              const hasLesson = String(d.lessonTitle || "").trim() !== "";
              const hasAssessment = String(d.assessment || "").trim() !== "";
              return (
                <div
                  key={idx}
                  style={{
                    padding: "16px",
                    borderRadius: "12px",
                    border: "1px solid var(--border-color)",
                    backgroundColor: "#fbfcfb",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                    gap: "12px",
                    alignItems: "start",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: "3px" }}>اليوم والزمن (د)</div>
                    <input
                      aria-label={`اسم اليوم ${idx + 1}`}
                      className="form-input"
                      style={{ fontWeight: 800, padding: "5px 8px", marginBottom: "6px" }}
                      value={d.dayName || ""}
                      onChange={(e) => {
                        const next = [...days];
                        next[idx] = { ...next[idx], dayName: e.target.value };
                        setDays(next);
                      }}
                    />
                    <input
                      type="number"
                      min={0}
                      max={180}
                      aria-label={`زمن اليوم ${idx + 1}`}
                      className="form-input"
                      style={{ padding: "5px 8px", fontSize: "0.82rem" }}
                      value={d.minutes ?? 45}
                      onChange={(e) => {
                        const next = [...days];
                        next[idx] = { ...next[idx], minutes: Math.max(0, Number(e.target.value) || 0) };
                        setDays(next);
                      }}
                    />
                  </div>

                  <div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: "3px" }}>الدرس</div>
                    {lessons.length > 0 && (
                      <select
                        aria-label={`اختيار درس من السجل لليوم ${idx + 1}`}
                        className="form-select"
                        style={{ padding: "5px 8px", fontSize: "0.78rem", marginBottom: "5px" }}
                        value={d.lessonId || ""}
                        onChange={(e) => {
                          const les = lessons.find((l) => l.id === e.target.value);
                          const next = [...days];
                          next[idx] = {
                            ...next[idx],
                            lessonId: e.target.value,
                            lessonTitle: les ? les.title : next[idx].lessonTitle,
                          };
                          setDays(next);
                        }}
                      >
                        <option value="">— اختر درسًا من السجل —</option>
                        {lessons.map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.title}
                          </option>
                        ))}
                      </select>
                    )}
                    <input
                      aria-label={`درس اليوم ${idx + 1}`}
                      className="form-input"
                      placeholder="لم يُحدّد درس"
                      style={{ fontWeight: 700, padding: "6px 8px", marginBottom: "4px" }}
                      value={d.lessonTitle || ""}
                      onChange={(e) => {
                        const next = [...days];
                        next[idx] = { ...next[idx], lessonTitle: e.target.value };
                        setDays(next);
                      }}
                    />
                    <span className={`badge ${hasVerifiedSource ? "badge-success" : "badge-warning"}`}>
                      {hasVerifiedSource ? "مصدر موثّق" : "تجريبي — غير موثّق"}
                    </span>
                  </div>

                  <div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: "3px" }}>التحضير والأنشطة</div>
                    <input
                      aria-label={`أنشطة اليوم ${idx + 1}`}
                      className="form-input"
                      style={{ padding: "6px 8px" }}
                      value={d.activities || ""}
                      onChange={(e) => {
                        const next = [...days];
                        next[idx] = { ...next[idx], activities: e.target.value };
                        setDays(next);
                      }}
                    />
                  </div>

                  <div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: "3px" }}>التقويم التكويني</div>
                    <input
                      aria-label={`تقويم اليوم ${idx + 1}`}
                      className="form-input"
                      placeholder="لم تُحدّد طريقة التقويم"
                      style={{ padding: "6px 8px" }}
                      value={d.assessment || ""}
                      onChange={(e) => {
                        const next = [...days];
                        next[idx] = { ...next[idx], assessment: e.target.value };
                        setDays(next);
                      }}
                    />
                  </div>

                  <div style={{ textAlign: "start" }}>
                    <span
                      className={`badge ${
                        hasLesson && hasAssessment
                          ? "badge-success"
                          : hasLesson && !hasAssessment
                          ? "badge-blocker"
                          : "badge-neutral"
                      }`}
                      style={{ marginBottom: "8px" }}
                    >
                      {hasLesson && hasAssessment
                        ? "جاهز للمراجعة"
                        : hasLesson && !hasAssessment
                        ? "تقويم ناقص"
                        : "غير مجدول"}
                    </span>
                    <div>
                      <Link
                        href={d.linkedDailyPlanId ? `/daily-plan?planId=${encodeURIComponent(d.linkedDailyPlanId)}` : "/daily-plan"}
                        style={{ fontSize: "0.78rem", color: "var(--primary-green)", fontWeight: 700, textDecoration: "none" }}
                      >
                        {hasLesson && hasAssessment ? "تحرير الحصة ←" : "استكمال الحصة ←"}
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {readyForReviewCount < days.length && (
        <div className="blocker-banner">
          <span>
            ⛔ قبل اكتمال الخطة: أضف تقويم الأيام الناقصة، وحدّد دروس الأيام غير المجدولة أو استكملها بالزر أعلاه.
          </span>
        </div>
      )}

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" onClick={handleSaveAndGoToReview} disabled={saving || !activeContextId}>
          ← حفظ ومراجعة خطة الأيام
        </button>
        <button type="button" className="btn btn-secondary" onClick={handleSaveFiveDayPlan} disabled={saving || !activeContextId}>
          {saving ? "جارٍ الحفظ..." : "حفظ مسودة · قاعدة البيانات"}
        </button>
      </div>
    </div>
  );
}

export default function FiveDayPlanPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <FiveDayPlanContent />
    </Suspense>
  );
}
