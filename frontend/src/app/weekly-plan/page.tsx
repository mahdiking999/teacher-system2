"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

function WeeklyPlanContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [title, setTitle] = useState<string>("الخطة الأسبوعية");
  const [sourceId, setSourceId] = useState<string>("");
  const [formativeAssessment, setFormativeAssessment] = useState<string>("بطاقات خروج يومية وملاحظة أداء الطلاب.");
  const [days, setDays] = useState<any[]>([]);
  const [dailyPlans, setDailyPlans] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const buildDefaultDays = useCallback(
    (dList: any[]) => {
      const sDays = activeContext?.schoolDays || ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"];
      const hDays = activeContext?.holidays || ["الجمعة", "السبت"];
      return [
        ...sDays.map((dName, idx) => ({
          dayName: dName,
          isHoliday: false,
          lessonTitle: `حصة ${dName} — ${activeContext?.subject || "الدرس"}`,
          linkedDailyPlanId: dList[idx]?.id || "",
          activities: "التهيئة والتدريس والتدريب",
          assessment: "تقويم تكويني يومي",
          minutes: activeContext?.defaultPeriodMinutes || 45,
        })),
        ...hDays.map((hName) => ({
          dayName: hName,
          isHoliday: true,
          lessonTitle: "عطلة رسمية",
          linkedDailyPlanId: "",
          activities: "—",
          assessment: "—",
          minutes: 0,
        })),
      ];
    },
    [activeContext]
  );

  const bindPlan = useCallback((pln: any) => {
    setSelectedPlanId(pln.id);
    setTitle(pln.title || "الخطة الأسبوعية");
    setSourceId(pln.sourceId || "");
    setFormativeAssessment(pln.formativeAssessment || "");
    setDays(pln.scheduleDays || []);
  }, []);

  const loadWeekly = useCallback(
    async (keepId?: string, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setSelectedPlanId("");
        setDailyPlans([]);
        setSources([]);
        setDays([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [wRes, dRes, sRes] = await Promise.all([
          apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}&planType=weekly`),
          apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}&planType=daily`),
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const wList = wRes.items || [];
        const dList = dRes.items || [];
        const sList = sRes.items || [];
        setPlans(wList);
        setDailyPlans(dList);
        setSources(sList);

        setSelectedPlanId((prev) => {
          const targetId =
            (keepId && wList.some((p: any) => p.id === keepId) && keepId) ||
            (urlPlanId && wList.some((p: any) => p.id === urlPlanId) && urlPlanId) ||
            (prev && wList.some((p: any) => p.id === prev) && prev) ||
            wList[0]?.id ||
            "";
          const found = wList.find((p: any) => p.id === targetId) || null;
          if (found) {
            bindPlan(found);
            return found.id;
          }
          setTitle(`الخطة الأسبوعية — ${activeContext?.subject || "المادة"}`);
          setSourceId(sList[0]?.id || "");
          setFormativeAssessment("بطاقات خروج يومية وملاحظة أداء الطلاب.");
          setDays(buildDefaultDays(dList));
          return "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل الخطة الأسبوعية.");
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
    loadWeekly(undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeSchoolDays = days.filter((d) => !d.isHoliday);
  const holidaysCount = days.filter((d) => d.isHoliday).length;
  const totalWeeklyMinutes = activeSchoolDays.reduce((acc, d) => acc + (Number(d.minutes) || 0), 0);

  const moveDayRow = (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= days.length) return;
    const next = [...days];
    const tmp = next[idx];
    next[idx] = next[target];
    next[target] = tmp;
    setDays(next);
  };

  const handleSaveWeekly = async (): Promise<string | null> => {
    if (!activeContextId) return null;
    setSaving(true);
    setErrorMsg("");
    setFeedback("");
    const currentPlan = plans.find((p) => p.id === selectedPlanId);
    const chosenSource = sources.find((s) => s.id === sourceId);
    const computedOrigin =
      chosenSource?.verificationStatus === "human_verified"
        ? "documented_source"
        : currentPlan?.contentOrigin || "authored_example";
    try {
      if (currentPlan && currentPlan.id) {
        const updated = await apiFetch(`/api/plans/${currentPlan.id}`, {
          method: "PUT",
          body: JSON.stringify({
            ...currentPlan,
            title: title.trim() || currentPlan.title,
            sourceId: sourceId || null,
            formativeAssessment,
            scheduleDays: days,
            contentOrigin: computedOrigin,
            expectedVersion: currentPlan.version,
          }),
        });
        setFeedback(`تم حفظ الخطة الأسبوعية (الإصدار v${updated.version}) وحساب مجموع الزمن (${totalWeeklyMinutes} دقيقة).`);
        await loadWeekly(updated.id);
        return updated.id;
      } else {
        const created = await apiFetch("/api/plans", {
          method: "POST",
          body: JSON.stringify({
            contextId: activeContextId,
            sourceId: sourceId || null,
            title: title.trim() || `الخطة الأسبوعية — ${activeContext?.subject || "المادة"}`,
            planType: "weekly",
            periodMinutes: activeContext?.defaultPeriodMinutes || 45,
            periodsCount: 1,
            objectives: ["توزيع دروس الأسبوع على أيام الدوام الفعلية مع مراعاة العطل."],
            formativeAssessment: formativeAssessment.trim() || "بطاقات خروج يومية وملاحظة أداء الطلاب.",
            scheduleDays: days,
            contentOrigin: computedOrigin,
          }),
        });
        setFeedback(`تم إنشاء وحفظ الخطة الأسبوعية وحساب مجموع الزمن (${totalWeeklyMinutes} دقيقة).`);
        await loadWeekly(created.id);
        return created.id;
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ الخطة الأسبوعية.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndReview = async () => {
    const savedId = await handleSaveWeekly();
    if (savedId) {
      router.push(`/review?planId=${encodeURIComponent(savedId)}`);
    }
  };

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / الخطة الأسبوعية
      </div>
      <h1 className="page-title">الخطة الأسبوعية</h1>
      <p className="page-subtitle">
        توزيع الدروس والحصص والعطل على أيام الأسبوع الفعلية بحسب إعداد السياق، مع تعديل ونقل وربط الخطط اليومية وحساب مجموع الوقت.
      </p>

      <div className="info-banner">
        <span>
          ⓘ أيام الدوام والعطل مستمدة من إعداد السياق ({(activeContext?.schoolDays || []).join("، ")})؛ يمكنك تبديل أي يوم إلى عطلة أو نقل الحصة بين الأيام.
        </span>
      </div>

      <WorkflowStepper activeStep={6} />

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
        <Link
          href="/five-day-plan"
          style={{
            padding: "10px",
            borderRadius: "8px",
            color: "var(--text-secondary)",
            fontWeight: 600,
            textAlign: "center",
            textDecoration: "none",
          }}
        >
          خمسة أيام تدريس
        </Link>
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
          أسبوعية (الدوام الفعلي والعطل)
        </div>
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

      <div className="stats-grid-3">
        <div className="stat-card">
          <div className="stat-label">أيام الدوام الفعلية</div>
          <div className="stat-number">{activeSchoolDays.length} أيام</div>
          <div className="stat-sub">مقابل {holidaysCount} أيام عطلة</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">خطط يومية مرتبطة</div>
          <div className="stat-number">{days.filter((d) => d.linkedDailyPlanId).length} خطط</div>
          <div className="stat-sub">ربط مباشر بالخطط اليومية المحفوظة</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">مجموع الوقت الأسبوعي الصحيح</div>
          <div className="stat-number">{totalWeeklyMinutes} دقيقة</div>
          <div className="stat-sub">العطل الرسمية خارج مجموع وقت التدريس</div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800 }}>بيانات الخطة الأسبوعية</h3>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            {plans.length > 0 && (
              <select
                aria-label="اختيار خطة أسبوعية محفوظة"
                className="form-select"
                style={{ width: "auto" }}
                value={selectedPlanId}
                onChange={(e) => {
                  const found = plans.find((p) => p.id === e.target.value);
                  if (found) bindPlan(found);
                }}
              >
                {!selectedPlanId && <option value="">— خطة أسبوعية جديدة —</option>}
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
                setTitle(`خطة أسبوعية جديدة — ${activeContext?.subject || "المادة"}`);
                setSourceId(sources[0]?.id || "");
                setFormativeAssessment("بطاقات خروج يومية وملاحظة أداء الطلاب.");
                setDays(buildDefaultDays(dailyPlans));
                setFeedback("");
                setErrorMsg("");
              }}
            >
              + خطة أسبوعية جديدة
            </button>
          </div>
        </div>

        <div className="stats-grid-3" style={{ marginBottom: 0 }}>
          <div className="form-group">
            <label className="form-label">عنوان الخطة الأسبوعية</label>
            <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="form-group">
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
          <div className="form-group">
            <label className="form-label">التقويم التكويني العام للأسبوع *</label>
            <input
              className={`form-input ${!formativeAssessment.trim() ? "error-border" : ""}`}
              value={formativeAssessment}
              onChange={(e) => setFormativeAssessment(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "12px" }}>
          جدول الأسبوع الفعلي (تعديل، نقل، تحديد عطلة، وربط خطة يومية)
        </h3>

        {loading ? (
          <div style={{ textAlign: "center", padding: "30px 12px", color: "var(--text-secondary)" }}>
            جارٍ تحميل جدول الأسبوع...
          </div>
        ) : (
          <div className="table-scroll-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>اليوم</th>
                  <th>حالة اليوم</th>
                  <th>الدرس / الموضوع</th>
                  <th>ربط بخطة يومية</th>
                  <th>الأنشطة</th>
                  <th>التقويم</th>
                  <th>الزمن (د)</th>
                  <th>نقل</th>
                </tr>
              </thead>
              <tbody>
                {days.map((d, idx) => (
                  <tr key={idx} style={{ opacity: d.isHoliday ? 0.65 : 1 }}>
                    <td style={{ fontWeight: 800, minWidth: "85px" }}>{d.dayName}</td>
                    <td style={{ minWidth: "105px" }}>
                      <select
                        aria-label={`حالة يوم ${d.dayName}`}
                        className="form-select"
                        style={{ padding: "5px 8px", fontSize: "0.8rem" }}
                        value={d.isHoliday ? "holiday" : "school"}
                        onChange={(e) => {
                          const isHol = e.target.value === "holiday";
                          const next = [...days];
                          next[idx] = {
                            ...next[idx],
                            isHoliday: isHol,
                            lessonTitle: isHol
                              ? "عطلة رسمية"
                              : next[idx].lessonTitle === "عطلة رسمية"
                              ? `حصة ${next[idx].dayName}`
                              : next[idx].lessonTitle,
                            activities: isHol
                              ? "—"
                              : next[idx].activities === "—"
                              ? "التهيئة والتدريس والتدريب"
                              : next[idx].activities,
                            assessment: isHol ? "—" : next[idx].assessment === "—" ? "" : next[idx].assessment,
                            linkedDailyPlanId: isHol ? "" : next[idx].linkedDailyPlanId,
                            minutes: isHol ? 0 : activeContext?.defaultPeriodMinutes || 45,
                          };
                          setDays(next);
                        }}
                      >
                        <option value="school">يوم دوام</option>
                        <option value="holiday">عطلة</option>
                      </select>
                    </td>
                    <td style={{ minWidth: "160px" }}>
                      <input
                        aria-label={`درس يوم ${d.dayName}`}
                        className="form-input"
                        disabled={d.isHoliday}
                        style={{ padding: "6px 8px" }}
                        value={d.lessonTitle || ""}
                        onChange={(e) => {
                          const next = [...days];
                          next[idx] = { ...next[idx], lessonTitle: e.target.value };
                          setDays(next);
                        }}
                      />
                    </td>
                    <td style={{ minWidth: "145px" }}>
                      <select
                        aria-label={`ربط خطة ليوم ${d.dayName}`}
                        className="form-select"
                        disabled={d.isHoliday}
                        style={{ padding: "5px 8px", fontSize: "0.8rem" }}
                        value={d.linkedDailyPlanId || ""}
                        onChange={(e) => {
                          const next = [...days];
                          next[idx] = { ...next[idx], linkedDailyPlanId: e.target.value };
                          setDays(next);
                        }}
                      >
                        <option value="">— بدون ربط —</option>
                        {dailyPlans.map((dp) => (
                          <option key={dp.id} value={dp.id}>
                            {dp.title}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td style={{ minWidth: "150px" }}>
                      <input
                        aria-label={`أنشطة يوم ${d.dayName}`}
                        className="form-input"
                        disabled={d.isHoliday}
                        style={{ padding: "6px 8px" }}
                        value={d.activities || ""}
                        onChange={(e) => {
                          const next = [...days];
                          next[idx] = { ...next[idx], activities: e.target.value };
                          setDays(next);
                        }}
                      />
                    </td>
                    <td style={{ minWidth: "150px" }}>
                      <input
                        aria-label={`تقويم يوم ${d.dayName}`}
                        className="form-input"
                        disabled={d.isHoliday}
                        style={{ padding: "6px 8px" }}
                        value={d.assessment || ""}
                        onChange={(e) => {
                          const next = [...days];
                          next[idx] = { ...next[idx], assessment: e.target.value };
                          setDays(next);
                        }}
                      />
                    </td>
                    <td style={{ minWidth: "80px" }}>
                      <input
                        type="number"
                        min={0}
                        max={180}
                        disabled={d.isHoliday}
                        aria-label={`زمن يوم ${d.dayName}`}
                        className="form-input"
                        style={{ padding: "6px 8px", fontWeight: 700 }}
                        value={d.isHoliday ? 0 : d.minutes ?? 45}
                        onChange={(e) => {
                          const next = [...days];
                          next[idx] = { ...next[idx], minutes: Math.max(0, Number(e.target.value) || 0) };
                          setDays(next);
                        }}
                      />
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "4px" }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: "4px 8px" }}
                          disabled={idx === 0}
                          aria-label={`نقل يوم ${d.dayName} للأعلى`}
                          onClick={() => moveDayRow(idx, -1)}
                          title="نقل للأعلى"
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: "4px 8px" }}
                          disabled={idx === days.length - 1}
                          aria-label={`نقل يوم ${d.dayName} للأسفل`}
                          onClick={() => moveDayRow(idx, 1)}
                          title="نقل للأسفل"
                        >
                          ↓
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" onClick={handleSaveWeekly} disabled={saving || !activeContextId}>
          {saving ? "جارٍ الحفظ..." : "حفظ الخطة الأسبوعية"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={handleSaveAndReview} disabled={saving || !activeContextId}>
          حفظ والانتقال إلى المراجعة النهائية
        </button>
      </div>
    </div>
  );
}

export default function WeeklyPlanPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <WeeklyPlanContent />
    </Suspense>
  );
}
