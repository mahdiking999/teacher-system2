"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTeacherApp, WorkflowStepper } from "../../components/AppShell";

const SUBJECT_SUGGESTIONS = [
  {
    title: "اطلب تفسير الاستدلال",
    desc: "على السبورة: اطلب من الطالب شرح سبب اختيار كل خطوة أو دليل، لا النتيجة فقط.",
    phaseTarget: 2,
  },
  {
    title: "ناقش تصوّرًا شائعًا",
    desc: "بالبطاقات: اجمع تفسيرات الطلاب وناقش اختلافها دون افتراض خطأ مسبق بعينه.",
    phaseTarget: 3,
  },
  {
    title: "استخدم تمثيلًا بصريًا أو خريطة مفاهيم",
    desc: "بالسبورة والمسطرة والألوان: مثّل الفكرة التي يختارها المعلم بعد مراجعة المصدر.",
    phaseTarget: 1,
  },
  {
    title: "قارن بين استراتيجيتين أو وجهتي نظر",
    desc: "بالأقلام الملوّنة: ميّز خطوات كل طريقة ثم ناقش أوجه التشابه والاختلاف.",
    phaseTarget: 3,
  },
];

function DailyPlanContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPlanId = searchParams.get("planId") || "";

  const { activeContext, activeContextId, apiFetch, downloadFile } = useTeacherApp();
  const [plans, setPlans] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [lastExportLink, setLastExportLink] = useState<{ url: string; fileName: string } | null>(null);
  const [exportingFmt, setExportingFmt] = useState<string>("");
  const [aiDrafting, setAiDrafting] = useState<boolean>(false);
  const [aiPrompt, setAiPrompt] = useState<string>("");

  // Inline template save UI (replaces browser prompt)
  const [showTplModal, setShowTplModal] = useState<boolean>(false);
  const [newTplName, setNewTplName] = useState<string>("");
  const [savingTpl, setSavingTpl] = useState<boolean>(false);

  // Editable Plan Fields
  const [title, setTitle] = useState<string>("خطة درس يومي");
  const [sourceId, setSourceId] = useState<string>("");
  const [primaryLessonId, setPrimaryLessonId] = useState<string>("");
  const [secondaryLessonId, setSecondaryLessonId] = useState<string>("");
  const [lessonsCount, setLessonsCount] = useState<number>(1);
  const [periodsCount, setPeriodsCount] = useState<number>(1);
  const [periodMinutes, setPeriodMinutes] = useState<number>(45);
  const [objectivesText, setObjectivesText] = useState<string>("");
  const [priorKnowledge, setPriorKnowledge] = useState<string>("");
  const [phases, setPhases] = useState<any[]>([]);
  const [formativeAssessment, setFormativeAssessment] = useState<string>("");
  const [differentiation, setDifferentiation] = useState<string>("");
  const [homework, setHomework] = useState<string>("");
  const [homeEnrichmentMinutes, setHomeEnrichmentMinutes] = useState<number>(15);
  const [planningNotes, setPlanningNotes] = useState<string>("");
  const [subjectItems, setSubjectItems] = useState<any[]>([]);
  const [planVersion, setPlanVersion] = useState<number>(1);
  const [planStatus, setPlanStatus] = useState<string>("draft");

  const initBlankPlanForm = useCallback(
    (sList: any[], lList: any[], tList: any[]) => {
      const prefs = activeContext?.documentPreferences || {};
      setSelectedPlanId("");
      setTitle(activeContext ? `خطة درس — ${activeContext.subject}` : "خطة درس جديد");
      setSourceId(sList[0]?.id || "");
      setPrimaryLessonId(lList[0]?.id || "");
      setSecondaryLessonId("");
      setLessonsCount(1);
      setPeriodsCount(activeContext?.defaultPeriodsCount || 1);
      setPeriodMinutes(activeContext?.defaultPeriodMinutes || 45);
      setObjectivesText(
        typeof prefs.defaultObjectivesDraft === "string"
          ? prefs.defaultObjectivesDraft
          : lList[0]?.objectives?.join("\n") || ""
      );
      setPriorKnowledge(lList[0]?.priorKnowledge || "");
      setPhases(tList[0]?.phases ? JSON.parse(JSON.stringify(tList[0].phases)) : []);
      setFormativeAssessment("");
      setDifferentiation("");
      setHomework("");
      setHomeEnrichmentMinutes(15);
      setPlanningNotes(typeof prefs.defaultPlanningNote === "string" ? prefs.defaultPlanningNote : "");
      setSubjectItems([]);
      setPlanVersion(1);
      setPlanStatus("draft");
    },
    [activeContext]
  );

  const bindPlanToForm = useCallback((pln: any) => {
    setSelectedPlanId(pln.id);
    setTitle(pln.title || "خطة يومية");
    setSourceId(pln.sourceId || "");
    setPrimaryLessonId(pln.primaryLessonId || "");
    setSecondaryLessonId(pln.secondaryLessonId || "");
    setLessonsCount(pln.lessonsCount || 1);
    setPeriodsCount(pln.periodsCount || 1);
    setPeriodMinutes(pln.periodMinutes || 45);
    setObjectivesText((pln.objectives || []).join("\n"));
    setPriorKnowledge(pln.priorKnowledge || "");
    setPhases(pln.phases || []);
    setFormativeAssessment(pln.formativeAssessment || "");
    setDifferentiation(pln.differentiation || "");
    setHomework(pln.homework || "");
    setHomeEnrichmentMinutes(pln.homeEnrichmentMinutes ?? 0);
    setPlanningNotes(pln.planningNotes || "");
    setSubjectItems(pln.subjectItems || []);
    setPlanVersion(pln.version || 1);
    setPlanStatus(pln.status || "draft");
  }, []);

  const loadData = useCallback(
    async (keepPlanId?: string, isCancelled?: () => boolean) => {
      if (!activeContextId) {
        setPlans([]);
        setLessons([]);
        setTemplates([]);
        setSources([]);
        initBlankPlanForm([], [], []);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorMsg("");
      try {
        const [pRes, lRes, tRes, sRes] = await Promise.all([
          apiFetch(`/api/plans?contextId=${encodeURIComponent(activeContextId)}&planType=daily`),
          apiFetch(`/api/lessons?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/templates?contextId=${encodeURIComponent(activeContextId)}`),
          apiFetch(`/api/sources?contextId=${encodeURIComponent(activeContextId)}`),
        ]);
        if (isCancelled && isCancelled()) return;
        const pList = pRes.items || [];
        const lList = lRes.items || [];
        const tList = tRes.items || [];
        const sList = sRes.items || [];
        setPlans(pList);
        setLessons(lList);
        setTemplates(tList);
        setSources(sList);

        setSelectedPlanId((prev) => {
          const targetId =
            (keepPlanId && pList.some((x: any) => x.id === keepPlanId) && keepPlanId) ||
            (urlPlanId && pList.some((x: any) => x.id === urlPlanId) && urlPlanId) ||
            (prev && pList.some((x: any) => x.id === prev) && prev) ||
            (pList[0] && pList[0].id) ||
            "";
          const found = pList.find((x: any) => x.id === targetId) || null;
          if (found) {
            bindPlanToForm(found);
            return found.id;
          }
          initBlankPlanForm(sList, lList, tList);
          return "";
        });
      } catch (e: any) {
        if (!isCancelled || !isCancelled()) {
          setErrorMsg(e?.message || "تعذر تحميل بيانات الخطة اليومية.");
        }
      } finally {
        if (!isCancelled || !isCancelled()) {
          setLoading(false);
        }
      }
    },
    [activeContextId, apiFetch, urlPlanId, bindPlanToForm, initBlankPlanForm]
  );

  useEffect(() => {
    let cancelled = false;
    setFeedback("");
    setErrorMsg("");
    setAiPrompt("");
    setLastExportLink(null);
    setShowTplModal(false);
    setSelectedPlanId("");
    loadData(undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [activeContextId, urlPlanId]); // eslint-disable-line react-hooks/exhaustive-deps

  const totalAllocated = periodsCount * periodMinutes;
  const inClassSum = phases
    .filter((p) => !p.isHomeEnrichment)
    .reduce((acc, p) => acc + (Number(p.minutes) || 0), 0);
  const timeDiff = totalAllocated - inClassSum;

  const handleApplyTemplate = (tplId: string) => {
    const tpl = templates.find((t) => t.id === tplId);
    if (!tpl) return;
    setPeriodsCount(tpl.periodsCount || 1);
    setPeriodMinutes(tpl.periodMinutes || 45);
    setPhases(JSON.parse(JSON.stringify(tpl.phases || [])));
    setErrorMsg("");
    setFeedback(`تم تطبيق القالب «${tpl.name}» — يمكنك تحرير أسماء المراحل ومحتواها وأزمنتها بحرية.`);
  };

  const handleSaveTemplateFromCurrent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTplName.trim()) {
      setErrorMsg("يرجى إدخال اسم للقالب قبل الحفظ.");
      return;
    }
    setSavingTpl(true);
    setErrorMsg("");
    setFeedback("");
    try {
      await apiFetch("/api/templates", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          name: newTplName.trim(),
          description: "قالب مراحل مخصص من المعلم",
          isDefault: false,
          periodsCount,
          periodMinutes,
          phases,
        }),
      });
      setFeedback(`تم حفظ القالب «${newTplName.trim()}» بنجاح لإعادة استخدامه.`);
      setShowTplModal(false);
      setNewTplName("");
      await loadData(selectedPlanId);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ القالب الجديد.");
    } finally {
      setSavingTpl(false);
    }
  };

  const buildDraftPayload = () => {
    const currentPlan = plans.find((p) => p.id === selectedPlanId);
    const chosenSource = sources.find((s) => s.id === sourceId);
    const computedOrigin =
      chosenSource?.verificationStatus === "human_verified"
        ? "documented_source"
        : currentPlan?.contentOrigin || "authored_example";
    return {
      contextId: activeContextId,
      sourceId: sourceId || null,
      primaryLessonId: primaryLessonId || null,
      secondaryLessonId: lessonsCount === 2 ? secondaryLessonId || null : null,
      title: title.trim() || (activeContext ? `خطة درس — ${activeContext.subject}` : "خطة درس يومي"),
      planType: "daily",
      teacherName: activeContext?.teacherName || "",
      schoolName: activeContext?.schoolName || "",
      sectionName: activeContext?.sectionName || "",
      planningDate: activeContext?.planningDate || new Date().toISOString().split("T")[0],
      lessonsCount,
      periodsCount,
      periodMinutes,
      objectives: objectivesText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      priorKnowledge,
      teacherRole: currentPlan?.teacherRole || "",
      studentRole: currentPlan?.studentRole || "",
      teachingTools: activeContext?.selectedTools || ["سبورة", "أقلام ملوّنة"],
      phases,
      formativeAssessment,
      differentiation,
      homework,
      homeEnrichmentMinutes: Number(homeEnrichmentMinutes) || 0,
      referencesNote: currentPlan?.referencesNote || "",
      planningNotes,
      subjectItems,
      scheduleDays: [],
      slides: currentPlan?.slides || [],
      presentationSettings: currentPlan?.presentationSettings || {},
      contentOrigin: computedOrigin,
      expectedVersion: planVersion,
    };
  };

  const handleSaveDraft = async (): Promise<string | null> => {
    if (!activeContextId) return null;
    setSaving(true);
    setErrorMsg("");
    setFeedback("");
    const payload = buildDraftPayload();
    try {
      if (selectedPlanId) {
        const updated = await apiFetch(`/api/plans/${selectedPlanId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setFeedback(`تم حفظ المسودة (الإصدار v${updated.version}) وفحصها تلقائيًا.`);
        await loadData(updated.id);
        return updated.id;
      } else {
        const created = await apiFetch("/api/plans", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setFeedback("تم إنشاء وحفظ الخطة اليومية الجديدة.");
        await loadData(created.id);
        return created.id;
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر حفظ المسودة.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndGoToReview = async () => {
    const savedId = await handleSaveDraft();
    if (savedId) {
      router.push(`/review?planId=${encodeURIComponent(savedId)}`);
    }
  };

  const handleAiGeneratePlan = async () => {
    setAiDrafting(true);
    setFeedback("");
    setErrorMsg("");
    try {
      let targetPlanId = selectedPlanId;
      if (!targetPlanId) {
        const created = await apiFetch("/api/plans", {
          method: "POST",
          body: JSON.stringify(buildDraftPayload()),
        });
        targetPlanId = created.id;
      }
      const res = await apiFetch(`/api/plans/${targetPlanId}/ai-generate-plan`, {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          lessonTitle: title,
          customInstructions: aiPrompt,
        }),
      });
      if (res?.plan) {
        bindPlanToForm(res.plan);
        await loadData(res.plan.id);
      } else {
        await loadData(targetPlanId);
      }
      setFeedback(
        `تمت صياغة الخطة اليومية والأنشطة والتقويم بالذكاء الاصطناعي بنجاح عبر (${res?.modelUsed || "NVIDIA NIM"}). راجع الحقول وعدّلها قبل الاعتماد.`
      );
    } catch (err: any) {
      setErrorMsg(err?.message || "خطأ أثناء التوليد بالذكاء الاصطناعي.");
    } finally {
      setAiDrafting(false);
    }
  };

  const handleQuickExport = async (fmt: "docx" | "pdf") => {
    setExportingFmt(fmt);
    setErrorMsg("");
    setLastExportLink(null);
    try {
      const savedId = await handleSaveDraft();
      if (!savedId) {
        setExportingFmt("");
        return;
      }
      const res = await apiFetch("/api/exports", {
        method: "POST",
        body: JSON.stringify({
          contextId: activeContextId,
          planId: savedId,
          exportFormat: fmt,
        }),
      });
      setLastExportLink({ url: res.downloadUrl, fileName: res.fileName });
      await downloadFile(res.downloadUrl, res.fileName);
      setFeedback(`تم توليد ملف ${fmt.toUpperCase()} الحقيقي (${res.fileName}) بنجاح.`);
    } catch (err: any) {
      setErrorMsg(err?.message || "تعذر توليد الملف.");
    } finally {
      setExportingFmt("");
    }
  };

  const insertSuggestion = (sug: (typeof SUBJECT_SUGGESTIONS)[0]) => {
    const next = [...phases];
    const targetIdx = Math.min(sug.phaseTarget, next.length - 1);
    if (targetIdx >= 0 && next[targetIdx]) {
      next[targetIdx] = {
        ...next[targetIdx],
        teacherActivity: `${next[targetIdx].teacherActivity || ""} — ${sug.title}: ${sug.desc}`.trim(),
      };
      setPhases(next);
      setErrorMsg("");
      setFeedback(`تم إدراج المقترح «${sug.title}» في المرحلة رقم ${targetIdx + 1} للمراجعة.`);
    }
  };

  const movePhase = (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= phases.length) return;
    const next = [...phases];
    const tmp = next[idx];
    next[idx] = next[target];
    next[target] = tmp;
    setPhases(next.map((p, i) => ({ ...p, order: i + 1 })));
  };

  const deletePhase = (idx: number) => {
    if (phases.length <= 1) return;
    setPhases(phases.filter((_, i) => i !== idx).map((p, i) => ({ ...p, order: i + 1 })));
  };

  const handleApplyLessonContent = () => {
    const les = lessons.find((l) => l.id === primaryLessonId);
    if (!les) return;
    setTitle(les.title || title);
    if (les.objectives && les.objectives.length > 0) {
      setObjectivesText(les.objectives.join("\n"));
    }
    if (les.priorKnowledge) {
      setPriorKnowledge(les.priorKnowledge);
    }
    if (les.evaluationCriteria && !formativeAssessment.trim()) {
      setFormativeAssessment(les.evaluationCriteria);
    }
    if (les.sourceId) {
      setSourceId(les.sourceId);
    }
    setFeedback(`تم استيراد عنوان وأهداف الدرس «${les.title}» إلى مسودة الخطة.`);
  };

  const hasProjector = (activeContext?.selectedTools || []).includes("جهاز عرض");
  const pedagogicalAidEnabled = activeContext?.documentPreferences?.pedagogicalAidEnabled !== false;

  return (
    <div>
      <div className="breadcrumb-line">
        مُعلّم {activeContext?.subject || "المادة"} / مساحة المعلم / الخطة اليومية
      </div>
      <h1 className="page-title">الخطة اليومية</h1>
      <p className="page-subtitle">
        مسودة قابلة للتحرير لـ «{title}». راجع الحقول المطلوبة وتوازن الزمن قبل إعداد المخرجات.
      </p>

      <div className="info-banner">
        <span>
          ⓘ تدعم الخطة درسًا أو درسين، وحصة واحدة ({periodMinutes} د) أو حصتين ({periodMinutes * 2} د)، مع قوالب مراحل قابلة للتخصيص.
        </span>
      </div>

      <WorkflowStepper activeStep={6} />

      {/* Top Action Bar matching `الخطة اليومية.png` */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "10px",
          marginBottom: "14px",
        }}
      >
        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary" onClick={handleSaveAndGoToReview} disabled={saving || !activeContextId}>
            ✓ حفظ ومراجعة الخطة
          </button>
          <button type="button" className="btn btn-secondary" onClick={handleSaveDraft} disabled={saving || !activeContextId}>
            {saving ? "جارٍ الحفظ..." : "حفظ مسودة · قاعدة البيانات"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              initBlankPlanForm(sources, lessons, templates);
              setFeedback("تم فتح نموذج خطة يومية جديدة فارغة؛ اضغط حفظ مسودة لإنشائها.");
              setErrorMsg("");
            }}
            disabled={loading || !activeContextId}
          >
            + خطة يومية جديدة
          </button>
          <span className={`badge ${!formativeAssessment.trim() || timeDiff !== 0 ? "badge-warning" : "badge-success"}`}>
            {!formativeAssessment.trim()
              ? "مسودة قيد الإعداد · تقويم ناقص"
              : timeDiff !== 0
              ? `تعارض وقت (${inClassSum}/${totalAllocated} د)`
              : `مكتملة الأركان · الإصدار v${planVersion}`}
          </span>
        </div>

        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {plans.length > 0 && (
            <select
              aria-label="اختيار خطة يومية محفوظة"
              className="form-select"
              style={{ width: "auto" }}
              value={selectedPlanId}
              onChange={(e) => {
                const found = plans.find((p) => p.id === e.target.value);
                if (found) {
                  bindPlanToForm(found);
                  setFeedback("");
                  setErrorMsg("");
                }
              }}
            >
              {!selectedPlanId && <option value="">— مسودة جديدة غير محفوظة —</option>}
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} (v{p.version})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Compact AI Plan Drafting Bar */}
      <div className="card" style={{ padding: "14px 18px", borderColor: "rgba(23, 107, 82, 0.28)", backgroundColor: "#fcfefd" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
          <strong style={{ fontSize: "0.95rem", fontWeight: 800 }}>
            ✨ صياغة الخطة والأنشطة بالذكاء الاصطناعي (NVIDIA NIM)
          </strong>
          <span style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
            يملأ الأهداف والتمهيد ومراحل سير الحصة والتقويم والواجب تلقائيًا
          </span>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="text"
            aria-label="تعليمات إضافية لصياغة الخطة بالذكاء الاصطناعي"
            className="form-input"
            style={{ flex: "1 1 280px" }}
            placeholder="تعليمات إضافية لصياغة الخطة (اختياري): ركّز على العمل التعاوني أو أمثلة حياتية..."
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            disabled={aiDrafting}
          />
          <button
            type="button"
            className="btn btn-primary"
            disabled={aiDrafting || !activeContextId}
            onClick={handleAiGeneratePlan}
          >
            {aiDrafting
              ? "جارٍ صياغة الخطة عبر NVIDIA NIM..."
              : "✨ صياغة الخطة والأنشطة بالذكاء الاصطناعي"}
          </button>
        </div>
      </div>

      <div className="warning-banner">
        <span>
          ⚠ مادة {activeContext?.subject || "المادة المحددة"} · جميع صياغات الخطة أدناه يحرّرها المعلم لتوثيق أهداف الدرس ومراحله، ويبقى توثيق الكتاب مرتبطًا برفع ملف المنهج ومراجعته.
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
        <div className="card" style={{ textAlign: "center", padding: "36px 16px", color: "var(--text-secondary)" }}>
          جارٍ تحميل الخطة اليومية...
        </div>
      ) : (
        <div className="main-split-grid">
          <div>
            {/* Card 1: Plan Header, Source/Lesson Linkage & Objectives */}
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
                <div>
                  <h3 style={{ fontSize: "1.15rem", fontWeight: 800 }}>بطاقة الخطة</h3>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                    {activeContext?.teacherName || "المعلم"}
                    {activeContext?.sectionName ? ` | ${activeContext.sectionName}` : ""}
                    {activeContext?.planningDate ? ` | ${activeContext.planningDate}` : ""} | {totalAllocated} دقيقة ({periodsCount} حصة)
                  </p>
                </div>
                <span className="badge badge-success">
                  {planStatus === "approved" ? `معتمدة (v${planVersion})` : `إصدار v${planVersion}`}
                </span>
              </div>

              <div className="equal-split-grid" style={{ marginBottom: "10px" }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">عنوان الخطة اليومية *</label>
                  <input
                    className="form-input"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="أدخل عنوان الخطة أو الدرس..."
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">مصدر المنهج المرتبط</label>
                  <select
                    className="form-select"
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                  >
                    <option value="">— غير مرتبط بمصدر —</option>
                    {sources.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title} ({s.verificationStatus === "human_verified" ? "موثّق" : "غير موثّق"})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">الدرس الأساسي المرتبط بالخطة</label>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <select
                    className="form-select"
                    style={{ flex: "1 1 220px" }}
                    value={primaryLessonId}
                    onChange={(e) => setPrimaryLessonId(e.target.value)}
                  >
                    <option value="">— اختر درسًا من السجل —</option>
                    {lessons.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.title} {l.printedPageNumber ? `(ص ${l.printedPageNumber})` : ""}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={!primaryLessonId}
                    onClick={handleApplyLessonContent}
                  >
                    ↺ تعبئة الأهداف من الدرس
                  </button>
                </div>
              </div>

              {/* Support 1 or 2 Lessons and 1 or 2 Periods */}
              <div className="stats-grid-4" style={{ marginBottom: "12px" }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">عدد الدروس</label>
                  <select
                    className="form-select"
                    value={lessonsCount}
                    onChange={(e) => setLessonsCount(Number(e.target.value))}
                  >
                    <option value={1}>درس واحد</option>
                    <option value={2}>درسان في الخطة</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">عدد الحصص</label>
                  <select
                    className="form-select"
                    value={periodsCount}
                    onChange={(e) => setPeriodsCount(Number(e.target.value))}
                  >
                    <option value={1}>حصة واحدة ({periodMinutes} د)</option>
                    <option value={2}>حصتان ({periodMinutes * 2} د)</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">مدة الحصة (دقيقة)</label>
                  <input
                    type="number"
                    min={10}
                    max={180}
                    className="form-input"
                    value={periodMinutes}
                    onChange={(e) => setPeriodMinutes(Math.max(5, Number(e.target.value) || 45))}
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">الدرس الثاني (إن وُجد)</label>
                  <select
                    className="form-select"
                    disabled={lessonsCount < 2}
                    value={secondaryLessonId}
                    onChange={(e) => setSecondaryLessonId(e.target.value)}
                  >
                    <option value="">— اختر درسًا ثانيًا —</option>
                    {lessons.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">أهداف التعلّم · صياغة قابلة للتحرير (كل سطر هدف)</label>
                <textarea
                  className="form-textarea"
                  value={objectivesText}
                  onChange={(e) => setObjectivesText(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">التحقّق من المتطلبات والمعارف السابقة</label>
                <input
                  className="form-input"
                  placeholder="أدخل سؤالًا تشخيصيًا مناسبًا للمحتوى بعد مراجعة المصدر..."
                  value={priorKnowledge}
                  onChange={(e) => setPriorKnowledge(e.target.value)}
                />
              </div>
            </div>

            {/* Card 2: Customizable Phases Table */}
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
                <div>
                  <h3 style={{ fontSize: "1.15rem", fontWeight: 800 }}>سير الحصة ومراحل القالب القابلة للتخصيص</h3>
                  <p style={{ fontSize: "0.78rem", color: timeDiff === 0 ? "var(--primary-green)" : "var(--blocker-text)", fontWeight: 700 }}>
                    مجموع أزمنة المراحل الصفية: {inClassSum} دقيقة من أصل {totalAllocated} دقيقة{" "}
                    {timeDiff === 0
                      ? "✓ (متوازن)"
                      : timeDiff > 0
                      ? `— متبقٍ ${timeDiff} دقيقة`
                      : `— تجاوز بمقدار ${Math.abs(timeDiff)} دقيقة!`}
                  </p>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <select
                    aria-label="تطبيق قالب مراحل"
                    className="form-select"
                    style={{ width: "auto", fontSize: "0.8rem" }}
                    onChange={(e) => {
                      if (e.target.value) handleApplyTemplate(e.target.value);
                    }}
                    value=""
                  >
                    <option value="" disabled>
                      اختر قالب مراحل جاهز...
                    </option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "6px 12px", fontSize: "0.78rem" }}
                    onClick={() => {
                      setNewTplName(`قالب مخصص — ${activeContext?.subject || ""}`.trim());
                      setShowTplModal((v) => !v);
                    }}
                  >
                    حفظ كقالب للسياق
                  </button>
                </div>
              </div>

              {showTplModal && (
                <form
                  onSubmit={handleSaveTemplateFromCurrent}
                  style={{
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                    alignItems: "center",
                    padding: "10px 12px",
                    marginBottom: "12px",
                    borderRadius: "8px",
                    border: "1px solid var(--primary-green)",
                    backgroundColor: "var(--primary-tint-bg)",
                  }}
                >
                  <input
                    className="form-input"
                    style={{ flex: "1 1 220px" }}
                    placeholder="اسم القالب الجديد..."
                    value={newTplName}
                    onChange={(e) => setNewTplName(e.target.value)}
                  />
                  <button type="submit" className="btn btn-primary" style={{ padding: "6px 12px", fontSize: "0.8rem" }} disabled={savingTpl}>
                    {savingTpl ? "جارٍ الحفظ..." : "تأكيد حفظ القالب"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                    onClick={() => setShowTplModal(false)}
                  >
                    إلغاء
                  </button>
                </form>
              )}

              <div className="table-scroll-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>الحصة</th>
                      <th>المرحلة / العنصر</th>
                      <th>نشاط ودور المعلم</th>
                      <th>نشاط ودور الطالب</th>
                      <th>الزمن (د)</th>
                      <th>إجراء</th>
                    </tr>
                  </thead>
                  <tbody>
                    {phases.map((ph, idx) => (
                      <tr key={idx}>
                        <td style={{ minWidth: "85px" }}>
                          <select
                            aria-label={`الحصة للمرحلة ${idx + 1}`}
                            className="form-select"
                            style={{ padding: "5px 6px", fontSize: "0.8rem" }}
                            value={ph.periodNumber || 1}
                            onChange={(e) => {
                              const next = [...phases];
                              next[idx] = { ...next[idx], periodNumber: Number(e.target.value) };
                              setPhases(next);
                            }}
                          >
                            <option value={1}>الأولى</option>
                            <option value={2}>الثانية</option>
                          </select>
                        </td>
                        <td style={{ minWidth: "140px" }}>
                          <input
                            aria-label={`اسم المرحلة ${idx + 1}`}
                            className="form-input"
                            style={{ fontWeight: 700, padding: "6px 8px" }}
                            value={ph.phaseName || ""}
                            onChange={(e) => {
                              const next = [...phases];
                              next[idx] = { ...next[idx], phaseName: e.target.value };
                              setPhases(next);
                            }}
                          />
                        </td>
                        <td style={{ minWidth: "180px" }}>
                          <input
                            aria-label={`نشاط المعلم للمرحلة ${idx + 1}`}
                            className="form-input"
                            style={{ padding: "6px 8px" }}
                            value={ph.teacherActivity || ""}
                            onChange={(e) => {
                              const next = [...phases];
                              next[idx] = { ...next[idx], teacherActivity: e.target.value };
                              setPhases(next);
                            }}
                          />
                        </td>
                        <td style={{ minWidth: "180px" }}>
                          <input
                            aria-label={`نشاط الطالب للمرحلة ${idx + 1}`}
                            className="form-input"
                            style={{ padding: "6px 8px" }}
                            value={ph.studentActivity || ""}
                            onChange={(e) => {
                              const next = [...phases];
                              next[idx] = { ...next[idx], studentActivity: e.target.value };
                              setPhases(next);
                            }}
                          />
                        </td>
                        <td style={{ minWidth: "85px" }}>
                          <input
                            type="number"
                            min={0}
                            max={180}
                            aria-label={`زمن المرحلة ${idx + 1}`}
                            className="form-input"
                            style={{ padding: "6px 8px", color: "var(--primary-green)", fontWeight: 700 }}
                            value={ph.minutes ?? 0}
                            onChange={(e) => {
                              const val = Math.max(0, Number(e.target.value) || 0);
                              const next = [...phases];
                              next[idx] = { ...next[idx], minutes: val };
                              setPhases(next);
                            }}
                          />
                        </td>
                        <td style={{ minWidth: "95px" }}>
                          <div style={{ display: "flex", gap: "4px" }}>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ padding: "4px 6px", fontSize: "0.75rem" }}
                              disabled={idx === 0}
                              aria-label={`نقل المرحلة ${idx + 1} للأعلى`}
                              onClick={() => movePhase(idx, -1)}
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ padding: "4px 6px", fontSize: "0.75rem" }}
                              disabled={idx === phases.length - 1}
                              aria-label={`نقل المرحلة ${idx + 1} للأسفل`}
                              onClick={() => movePhase(idx, 1)}
                            >
                              ↓
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ padding: "4px 6px", fontSize: "0.75rem", color: "var(--blocker-text)" }}
                              disabled={phases.length <= 1}
                              aria-label={`حذف المرحلة ${idx + 1}`}
                              onClick={() => deletePhase(idx)}
                            >
                              ✕
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px", flexWrap: "wrap", gap: "8px" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  onClick={() =>
                    setPhases([
                      ...phases,
                      {
                        order: phases.length + 1,
                        periodNumber: periodsCount,
                        phaseName: "مرحلة مخصصة جديدة",
                        teacherActivity: "يوجه النشاط",
                        studentActivity: "يتفاعل وينفذ المهمة",
                        minutes: 5,
                        isHomeEnrichment: false,
                      },
                    ])
                  }
                >
                  + إضافة مرحلة
                </button>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  <label htmlFor="home-enrichment-min" style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                    الإثراء المنزلي (دقيقة خارج وقت الحصة):
                  </label>
                  <input
                    id="home-enrichment-min"
                    type="number"
                    min={0}
                    max={120}
                    className="form-input"
                    style={{ width: "78px", padding: "4px 8px", fontSize: "0.8rem" }}
                    value={homeEnrichmentMinutes}
                    onChange={(e) => setHomeEnrichmentMinutes(Math.max(0, Number(e.target.value) || 0))}
                  />
                </div>
              </div>
            </div>

            {/* Card 3: Assessment, Differentiation, Homework, Notes & Tool Items */}
            <div className="card">
              <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "12px" }}>التقويم ومراعاة الفروق</h3>

              <div className="form-group">
                <label className="form-label">التقويم التكويني *</label>
                <textarea
                  className={`form-textarea ${!formativeAssessment.trim() ? "error-border" : ""}`}
                  placeholder="أدخل طريقة تقويم مرتبطة بالأهداف..."
                  value={formativeAssessment}
                  onChange={(e) => setFormativeAssessment(e.target.value)}
                />
                {!formativeAssessment.trim() && (
                  <div style={{ fontSize: "0.78rem", color: "var(--blocker-text)", marginTop: "4px", fontWeight: 700 }}>
                    مطلوب: أضف طريقة التقويم قبل اكتمال المراجعة واعتماد الخطة.
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">مراعاة الفروق الفردية (التمايز) · صياغة قابلة للتحرير</label>
                <input
                  className="form-input"
                  value={differentiation}
                  onChange={(e) => setDifferentiation(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">الواجب المنزلي والتوسعة · يحرّره المعلم</label>
                <input
                  className="form-input"
                  placeholder="أدخل مهمة مناسبة بعد مراجعة المصدر؛ لا توجد تمارين رسمية مقترحة هنا..."
                  value={homework}
                  onChange={(e) => setHomework(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: subjectItems.length > 0 ? "14px" : 0 }}>
                <label className="form-label">ملاحظات التخطيط والنتائج المدرجة من الأدوات التخصصية</label>
                <textarea
                  className="form-textarea"
                  placeholder="أي ملاحظات صفية أو مخرجات أضيفت من صفحة الأدوات..."
                  value={planningNotes}
                  onChange={(e) => setPlanningNotes(e.target.value)}
                />
              </div>

              {subjectItems.length > 0 && (
                <div style={{ paddingTop: "10px", borderTop: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontWeight: 700, fontSize: "0.85rem", marginBottom: "8px" }}>
                    عناصر تخصصية مرتبطة من الأدوات ({subjectItems.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {subjectItems.map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: "8px",
                          padding: "8px 10px",
                          borderRadius: "8px",
                          border: "1px solid var(--border-subtle)",
                          backgroundColor: "#fbfcfb",
                          fontSize: "0.8rem",
                        }}
                      >
                        <span>
                          <strong>[{item.domain}]</strong>{" "}
                          {item.expression
                            ? `${item.expression} = ${item.expectedAnswer} ${item.unit || ""}`
                            : item.quote || item.hypothesis || item.topic || "عنصر تخصصي"}
                        </span>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: "3px 8px", fontSize: "0.75rem", color: "var(--blocker-text)" }}
                          onClick={() => setSubjectItems(subjectItems.filter((_, i) => i !== idx))}
                        >
                          حذف
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Left Column in RTL: Subject Pedagogical Suggestions */}
          <div>
            {pedagogicalAidEnabled && (
              <div className="card">
                <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "2px" }}>
                  مقترحات لمادة {activeContext?.subject || "المادة"}
                </h3>
                <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                  مرتبطة بالوسائل المتاحة · للمراجعة والتحرير
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {SUBJECT_SUGGESTIONS.map((sug, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: "14px",
                        borderRadius: "10px",
                        border: "1px solid var(--border-subtle)",
                        backgroundColor: "#fbfcfb",
                      }}
                    >
                      <div style={{ fontWeight: 800, fontSize: "0.92rem", marginBottom: "4px" }}>{sug.title}</div>
                      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                        {sug.desc}
                      </p>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: "5px 12px", fontSize: "0.8rem" }}
                        onClick={() => insertSuggestion(sug)}
                      >
                        إدراج بعد المراجعة
                      </button>
                    </div>
                  ))}
                </div>

                <div
                  style={{
                    marginTop: "14px",
                    padding: "12px",
                    borderRadius: "10px",
                    backgroundColor: "var(--primary-tint-bg)",
                    color: "var(--primary-green)",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                  }}
                >
                  ✓ {hasProjector ? "جهاز العرض متاح ومضمّن." : "لا جهاز عرض مطلوب."}{" "}
                  تعتمد المسودة على {(activeContext?.selectedTools || []).join(" و") || "السبورة والأقلام"}.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bottom Action Bar matching `الخطة اليومية.png` */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary" onClick={handleSaveAndGoToReview} disabled={saving || !activeContextId}>
            ← حفظ والانتقال إلى المراجعة النهائية
          </button>
          <Link href="/five-day-plan" className="btn btn-secondary">
            عرض خطة خمسة أيام
          </Link>
          <Link href="/weekly-plan" className="btn btn-secondary">
            عرض الخطة الأسبوعية
          </Link>
        </div>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!!exportingFmt || saving || !activeContextId}
            onClick={() => handleQuickExport("docx")}
          >
            {exportingFmt === "docx" ? "جارٍ التوليد..." : "تصدير DOCX قابل للتحرير"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!!exportingFmt || saving || !activeContextId}
            onClick={() => handleQuickExport("pdf")}
          >
            {exportingFmt === "pdf" ? "جارٍ التوليد..." : "تصدير PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DailyPlanPage() {
  return (
    <Suspense fallback={<div className="card">جارٍ التحميل...</div>}>
      <DailyPlanContent />
    </Suspense>
  );
}
