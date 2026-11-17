"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

const CLASSROOM_AIDS = [
  { id: "سبورة", title: "سبورة", desc: "متاحة · شرح الخطوات وتمثيل الأفكار", icon: "📝" },
  { id: "أقلام ملوّنة", title: "أقلام ملوّنة", desc: "متاحة · تمييز الخطوات والعلاقات", icon: "✏" },
  { id: "مسطرة", title: "مسطرة", desc: "متاحة · تنظيم التمثيل البصري", icon: "📏" },
  { id: "بطاقات تعليمية", title: "بطاقات تعليمية", desc: "متاحة · مقارنة استراتيجيات الطلاب", icon: "🗂" },
  { id: "جهاز عرض", title: "جهاز عرض", desc: "اختياري · قد لا يتوفر في كل صف", icon: "📽" },
  { id: "أوراق عمل فارغة", title: "أوراق عمل فارغة", desc: "متاحة · يُدخل المعلم محتواها", icon: "📄" },
];

export default function ToolsAndAidsPage() {
  const { activeContext, activeContextId, apiFetch, refreshContexts } = useTeacherApp();
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [targetPlanId, setTargetPlanId] = useState<string>("");
  const [toolType, setToolType] = useState<string>("math_solver");
  const [mathExpr, setMathExpr] = useState<string>("(15 + 9) / 3");
  const [mathClaimed, setMathClaimed] = useState<string>("8");
  const [mathUnit, setMathUnit] = useState<string>("سم");
  const [passageText, setPassageText] = useState<string>("العلم يبني بيوتاً لا عماد لها");
  const [passageAuthor, setPassageAuthor] = useState<string>("أحمد شوقي");
  const [timelineEvents, setTimelineEvents] = useState<string>(
    "1921 | تأسيس الدولة | وثيقة تاريخية\n1958 | إعلان الجمهورية | سجل رسمي"
  );
  const [hypothesis, setHypothesis] = useState<string>("تزداد سرعة التفاعل بارتفاع درجة الحرارة");
  const [sciVariables, setSciVariables] = useState<string>("المستقل: درجة الحرارة | التابع: سرعة التفاعل | الضابط: التركيز والحجم");
  const [sciSafety, setSciSafety] = useState<string>("ارتداء النظارات الواقية وإشراف المعلم");
  const [sciUnit, setSciUnit] = useState<string>("درجة مئوية / ثانية");
  const [wsTopic, setWsTopic] = useState<string>("");
  const [wsPrompt, setWsPrompt] = useState<string>("أسئلة متدرجة تراعي الفروق الفردية");
  const [wsRubric, setWsRubric] = useState<string>("معيار تقييم واضح يربط الأداء بالهدف التعليمي");

  const [toolResult, setToolResult] = useState<any>(null);
  const [editableToolOutput, setEditableToolOutput] = useState<string>("");
  const [runningTool, setRunningTool] = useState<boolean>(false);
  const [addingToPlan, setAddingToPlan] = useState<boolean>(false);
  const [savingAid, setSavingAid] = useState<string | null>(null);
  const savingAidLockRef = useRef<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (activeContext?.selectedTools) {
      setSelectedTools(activeContext.selectedTools);
    } else {
      setSelectedTools([]);
    }
  }, [activeContext]);

  const loadPlans = useCallback(
    async (isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setTargetPlanId("");
        return;
      }
      try {
        const res = await apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}`);
        if (isCancelled && isCancelled()) return;
        const pList = res.items || [];
        setPlans(pList);
        const preferred = pList.find((p: any) => p.planType === "daily") || pList[0];
        setTargetPlanId((prev) => (pList.some((p: any) => p.id === prev) ? prev : preferred?.id || ""));
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل الخطط المتاحة للربط.");
        }
      }
    },
    [activeContextId, apiFetch]
  );

  useEffect(() => {
    let cancelled = false;
    setToolResult(null);
    setEditableToolOutput("");
    setFeedback("");
    setErrorMsg("");
    setWsTopic(activeContext?.subject || "");
    loadPlans(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, activeContext?.subject, loadPlans]);

  const isAidSelected = (aidId: string) =>
    selectedTools.includes(aidId) || (aidId === "أوراق عمل فارغة" && selectedTools.includes("أوراق عمل"));

  const toggleAid = async (aidId: string) => {
    if (savingAidLockRef.current || !activeContext) return;
    savingAidLockRef.current = true;
    setSavingAid(aidId);

    const previous = [...selectedTools];
    const currentlySelected = isAidSelected(aidId);
    let next: string[];
    if (aidId === "أوراق عمل فارغة") {
      const stripped = previous.filter((t) => t !== "أوراق عمل فارغة" && t !== "أوراق عمل");
      next = currentlySelected ? stripped : [...stripped, "أوراق عمل فارغة"];
    } else {
      next = currentlySelected ? previous.filter((t) => t !== aidId) : [...previous, aidId];
    }

    setSelectedTools(next);
    setErrorMsg("");
    try {
      await apiFetch(`/api/contexts/${activeContextId}`, {
        method: "PUT",
        body: JSON.stringify({
          ...activeContext,
          selectedTools: next,
          expectedVersion: activeContext.version,
        }),
      });
      await refreshContexts();
    } catch (e: any) {
      setSelectedTools(previous);
      setErrorMsg(e?.message || "تعذر حفظ تحديث الوسائل التعليمية؛ تم التراجع عن التغيير.");
    } finally {
      savingAidLockRef.current = false;
      setSavingAid(null);
    }
  };

  const handleRunTool = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setFeedback("");
    setRunningTool(true);
    let inputs: Record<string, any> = {};
    if (toolType === "math_solver") {
      inputs = { expression: mathExpr, claimedAnswer: mathClaimed, unit: mathUnit };
    } else if (toolType === "text_analysis") {
      inputs = { passage: passageText, authorOrSource: passageAuthor };
    } else if (toolType === "historical_timeline") {
      const evs = timelineEvents
        .split("\n")
        .map((ln) => ln.trim())
        .filter(Boolean)
        .map((ln) => {
          const [year, event, evidence] = ln.split("|").map((s) => (s || "").trim());
          return { year, event, evidence };
        });
      inputs = { events: evs };
    } else if (toolType === "science_experiment") {
      inputs = { hypothesis, variables: sciVariables, safety: sciSafety, unit: sciUnit };
    } else {
      inputs = {
        topic: wsTopic.trim() || activeContext?.subject || "الدرس الحالي",
        prompt: wsPrompt.trim(),
        rubric: wsRubric.trim(),
      };
    }

    try {
      const res = await apiFetch("/api/tools/execute", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          toolType,
          title: toolType === "worksheet_generator" ? wsTopic.trim() || `ورقة عمل — ${activeContext?.subject || ""}` : `أداة ${toolType}`,
          inputs,
        }),
      });
      setToolResult(res);
      setEditableToolOutput(res.editableOutput || "");
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر تشغيل الأداة التخصصية.");
    } finally {
      setRunningTool(false);
    }
  };

  const handleAddResultToPlan = async () => {
    setErrorMsg("");
    setFeedback("");
    if (!toolResult || !editableToolOutput.trim()) return;
    if (!toolResult.valid) {
      setErrorMsg("لا يمكن إدراج نتيجة تحتوي على خطأ تخصصي أو عدم تطابق في الخطة؛ صحّح المدخلات وأعد التحقق أولًا.");
      return;
    }
    const targetPlan = plans.find((p) => p.id === targetPlanId) || plans[0];
    if (!targetPlan) {
      setErrorMsg("لا توجد خطة محفوظة لإضافة النتيجة إليها؛ أنشئ خطة يومية أولًا.");
      return;
    }

    setAddingToPlan(true);
    try {
      const nextSubjectItems = [...(targetPlan.subjectItems || [])];
      if (toolResult.subjectItem) {
        nextSubjectItems.push(toolResult.subjectItem);
      }
      const updated = await apiFetch(`/api/plans/${targetPlan.id}`, {
        method: "PUT",
        body: JSON.stringify({
          ...targetPlan,
          planningNotes: `${targetPlan.planningNotes || ""}\n${editableToolOutput}`.trim(),
          subjectItems: nextSubjectItems,
          expectedVersion: targetPlan.version,
        }),
      });
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setFeedback(`تمت إضافة النتيجة المتحققة إلى الخطة «${updated.title}» (v${updated.version}) بنجاح.`);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر إضافة النتيجة إلى الخطة.");
    } finally {
      setAddingToPlan(false);
    }
  };

  const hasProjector = selectedTools.includes("جهاز عرض");

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / الوسائل التعليمية وأدوات المدرس
      </div>
      <h1 className="page-title">الوسائل التعليمية وأدوات المدرس</h1>
      <p className="page-subtitle">
        اختر الوسائل المتاحة فعلًا لتكوين خطة واقعية في الصف، واستخدم الأدوات التخصصية للمادة مع التحقق المستقل.
      </p>

      <div className="info-banner">
        <span>
          ⓘ السياق النشط: {activeContext?.subject} · {activeContext?.grade} · جميع المخرجات التدريبية تُعلّم بـ «مثال توضيحي غير موثق من الكتاب».
        </span>
      </div>

      <WorkflowStepper activeStep={4} />

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

      {/* Main Split matching `الوسائل التعليمية.png`: Classroom Aids Grid (2/3) & Selection Summary + Projector Alternative (1/3) */}
      <div className="main-split-grid">
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>ما المتوفر في صفك؟</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
            يمكن اختيار أكثر من وسيلة · يُحفظ الاختيار تلقائيًا في إعدادات السياق
          </p>

          <div className="stats-grid-3">
            {CLASSROOM_AIDS.map((aid) => {
              const isSelected = isAidSelected(aid.id);
              const isSavingThis = savingAid === aid.id;
              const isBusy = Boolean(savingAid);
              return (
                <div
                  key={aid.id}
                  onClick={() => {
                    if (!isBusy) toggleAid(aid.id);
                  }}
                  role="button"
                  tabIndex={isBusy ? -1 : 0}
                  aria-disabled={isBusy}
                  onKeyDown={(e) => {
                    if (!isBusy && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      toggleAid(aid.id);
                    }
                  }}
                  style={{
                    padding: "16px",
                    borderRadius: "12px",
                    border: isSelected ? "2px solid var(--primary-green)" : "1px solid var(--border-color)",
                    backgroundColor: isSelected ? "var(--primary-tint-bg)" : "#fbfcfb",
                    cursor: isBusy ? "wait" : "pointer",
                    opacity: isBusy && !isSavingThis ? 0.65 : 1,
                    transition: "opacity 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px", gap: "6px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "1.3rem" }}>{aid.icon}</span>
                    <span className={`badge ${isSavingThis ? "badge-warning" : isSelected ? "badge-success" : "badge-neutral"}`}>
                      {isSavingThis ? "جارٍ الحفظ..." : isSelected ? "محدّد" : "غير محدّد"}
                    </span>
                  </div>
                  <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: "4px" }}>{aid.title}</div>
                  <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>{aid.desc}</div>
                </div>
              );
            })}
          </div>

          {!hasProjector && (
            <div className="warning-banner" style={{ marginTop: "14px", marginBottom: 0 }}>
              <span>⚠ جهاز العرض غير متاح؛ لن يُدرج كوسيلة مطلوبة في الخطة أو المقترحات.</span>
            </div>
          )}
        </div>

        <div>
          <div className="card">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "8px" }}>ملخّص الاختيار</h3>
            <span className="badge badge-success" style={{ marginBottom: "10px" }}>
              {selectedTools.length} وسائل محدّدة
            </span>
            <p style={{ fontSize: "0.86rem", marginBottom: "12px" }}>
              {selectedTools.join("، ") || "لم تُحدّد وسيلة"}
            </p>
            <div style={{ display: "flex", gap: "8px", alignItems: "center", fontSize: "0.82rem", color: "var(--primary-green)" }}>
              <span>✓</span>
              <span>{hasProjector ? "يتضمن جهاز عرض" : "لا يعتمد على جهاز عرض — المقترحات تراعي الوسائل المتاحة فقط"}</span>
            </div>
          </div>

          {!hasProjector && (
            <div className="card">
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "6px" }}>بديل عملي لجهاز العرض</h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                استخدم السبورة والأقلام الملوّنة لتمثيل الفكرة، ثم وزّع البطاقات لمقارنة طرق التفكير. يحدّد المعلم محتوى المهمة بعد مراجعة المصدر.
              </p>
              <span className="badge badge-success">بديل مقترح · عملي</span>
            </div>
          )}
        </div>
      </div>

      {/* Specialized Subject Tools Section */}
      <div className="card">
        <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>
          أدوات المدرس التخصصية والمدقق العلمي والرياضي
        </h3>
        <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
          اختر الأداة المناسبة لمادتك (الرياضيات، الأدب واللغات، التاريخ، العلوم، أو منشئ أوراق العمل العام) مع فحص المدخلات ومنع القسمة على صفر.
        </p>

        <form onSubmit={handleRunTool}>
          <div className="form-group">
            <label className="form-label">نوع الأداة التخصصية</label>
            <select
              className="form-select"
              value={toolType}
              onChange={(e) => {
                setToolType(e.target.value);
                setToolResult(null);
                setErrorMsg("");
              }}
            >
              <option value="math_solver">مدقق المسائل والحلول الرياضية (منع القسمة على صفر وفحص الناتج والوحدات)</option>
              <option value="text_analysis">أداة تحليل نص أدبي / قرائي (فحص النسبة ومحك التفسير المفتوح)</option>
              <option value="historical_timeline">أداة الخط الزمني التاريخي (فحص تسلسل التواريخ والأدلة)</option>
              <option value="science_experiment">بطاقة تجربة علمية (الفرضية، المتغيرات، الوحدات، السلامة)</option>
              <option value="worksheet_generator">مولّد ورقة عمل صفية قابلة للتحرير لأي مادة</option>
            </select>
          </div>

          {toolType === "math_solver" && (
            <div className="stats-grid-3">
              <div className="form-group">
                <label className="form-label">العبارة الرياضية (LTR)</label>
                <input
                  className="form-input"
                  dir="ltr"
                  value={mathExpr}
                  onChange={(e) => setMathExpr(e.target.value)}
                  placeholder="(15 + 9) / 3"
                />
              </div>
              <div className="form-group">
                <label className="form-label">الناتج المتوقع</label>
                <input
                  className="form-input"
                  dir="ltr"
                  value={mathClaimed}
                  onChange={(e) => setMathClaimed(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">الوحدة</label>
                <input
                  className="form-input"
                  value={mathUnit}
                  onChange={(e) => setMathUnit(e.target.value)}
                />
              </div>
            </div>
          )}

          {toolType === "text_analysis" && (
            <div className="equal-split-grid">
              <div className="form-group">
                <label className="form-label">النص أو الشاهد الأدبي</label>
                <input
                  className="form-input"
                  value={passageText}
                  onChange={(e) => setPassageText(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">قائل النص / المصدر</label>
                <input
                  className="form-input"
                  value={passageAuthor}
                  onChange={(e) => setPassageAuthor(e.target.value)}
                />
              </div>
            </div>
          )}

          {toolType === "historical_timeline" && (
            <div className="form-group">
              <label className="form-label">الأحداث (كل سطر: السنة | الواقعة | الدليل)</label>
              <textarea
                className="form-textarea"
                value={timelineEvents}
                onChange={(e) => setTimelineEvents(e.target.value)}
              />
            </div>
          )}

          {toolType === "science_experiment" && (
            <div>
              <div className="equal-split-grid">
                <div className="form-group">
                  <label className="form-label">فرضية التجربة العلمية</label>
                  <input
                    className="form-input"
                    value={hypothesis}
                    onChange={(e) => setHypothesis(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">وحدة القياس المعتمدة</label>
                  <input
                    className="form-input"
                    value={sciUnit}
                    onChange={(e) => setSciUnit(e.target.value)}
                  />
                </div>
              </div>
              <div className="equal-split-grid">
                <div className="form-group">
                  <label className="form-label">المتغيرات (المستقل / التابع / الضابط)</label>
                  <input
                    className="form-input"
                    value={sciVariables}
                    onChange={(e) => setSciVariables(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">إجراءات السلامة</label>
                  <input
                    className="form-input"
                    value={sciSafety}
                    onChange={(e) => setSciSafety(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {toolType === "worksheet_generator" && (
            <div className="stats-grid-3">
              <div className="form-group">
                <label className="form-label">موضوع ورقة العمل</label>
                <input
                  className="form-input"
                  placeholder={activeContext?.subject || "موضوع الدرس"}
                  value={wsTopic}
                  onChange={(e) => setWsTopic(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">توجيه الأسئلة والتدرج</label>
                <input
                  className="form-input"
                  value={wsPrompt}
                  onChange={(e) => setWsPrompt(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">معيار التقويم (Rubric)</label>
                <input
                  className="form-input"
                  value={wsRubric}
                  onChange={(e) => setWsRubric(e.target.value)}
                />
              </div>
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={runningTool || !activeContextId}>
            {runningTool ? "جارٍ التحقق والتشغيل..." : "تشغيل الأداة والتحقق التخصصي"}
          </button>
        </form>

        {toolResult && (
          <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid var(--border-subtle)" }}>
            <div className={toolResult.valid ? "info-banner" : "blocker-banner"}>
              <span>
                {toolResult.valid ? "✓" : "⛔"} {toolResult.message} ({toolResult.provenanceLabel})
              </span>
            </div>

            {toolResult.editableOutput && (
              <div>
                <label className="form-label">النتيجة القابلة للتحرير والإضافة إلى الخطة:</label>
                <textarea
                  className="form-textarea"
                  value={editableToolOutput}
                  onChange={(e) => setEditableToolOutput(e.target.value)}
                />
                <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap", marginTop: "10px" }}>
                  {plans.length > 0 && (
                    <select
                      aria-label="اختر الخطة المستهدفة"
                      className="form-select"
                      style={{ width: "auto" }}
                      value={targetPlanId}
                      onChange={(e) => setTargetPlanId(e.target.value)}
                    >
                      {plans.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.title} ({p.planType === "daily" ? "يومية" : p.planType === "weekly" ? "أسبوعية" : "خمسة أيام"})
                        </option>
                      ))}
                    </select>
                  )}
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={addingToPlan || !toolResult.valid || plans.length === 0}
                    title={!toolResult.valid ? "صحح الأخطاء التخصصية أولًا قبل الإدراج في الخطة" : "إدراج النتيجة في الخطة"}
                    onClick={handleAddResultToPlan}
                  >
                    {addingToPlan ? "جارٍ الإدراج..." : "+ إدراج النتيجة في الخطة المختارة"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <Link href="/settings" className="btn btn-primary">
          ← متابعة إلى إعداد الخطة
        </Link>
        <Link href="/lessons" className="btn btn-secondary">
          العودة إلى الدرس
        </Link>
      </div>
    </div>
  );
}
