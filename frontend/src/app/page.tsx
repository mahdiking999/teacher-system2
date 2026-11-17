"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useTeacherApp, UiLang } from "../components/AppShell";

const isolateBidi = (text?: string) => {
  const s = (text || "").trim();
  return s ? `\u2068${s}\u2069` : "";
};

const DASHBOARD_COPY: Record<
  UiLang,
  {
    teacherPrefix: (sub?: string) => string;
    workspaceCrumb: string;
    pageTitle: string;
    subtitle: (sub: string, grade: string) => string;
    liveStatsBanner: (sub: string, grade: string) => string;
    loadError: string;
    heroSubtitle: string;
    teacherFallback: string;
    planningDateLabel: string;
    startNewPlanBtn: string;
    statAttentionLabel: string;
    statAttentionSub: string;
    statDraftsLabel: string;
    statDraftsSub: (total: number) => string;
    statReviewedLabel: string;
    statReviewedSub: string;
    statExportsLabel: string;
    statExportsSub: string;
    todayTasksTitle: string;
    todayTasksDesc: string;
    loadingTasks: string;
    noTasksText: string;
    createDailyPlanBtn: string;
    sourceStatusTitle: string;
    loadingText: string;
    sourceVerifiedBadge: string;
    sourceUnverifiedBadge: string;
    sourceMissingNotes: string;
    viewSourcesBtn: string;
    noPdfBadge: string;
    noPdfDesc: string;
    uploadPdfBtn: string;
    recentPlansTitle: string;
    recentPlansDesc: (sub: string, grade: string) => string;
    loadingPlans: string;
    noPlansText: (sub: string) => string;
    createFirstDailyBtn: string;
    colPlan: string;
    colType: string;
    colUpdated: string;
    colStatus: string;
    typeDaily: string;
    typeWeekly: string;
    typeFiveDay: string;
    continueDailyBtn: string;
    recentActivityTitle: string;
    recentActivityDesc: string;
    noActivityText: string;
    latestSavedPlanLabel: string;
    versionPrefix: string;
    toolsSelectedLabel: (count: number) => string;
    toolsEnabledBadge: string;
    downloadBtn: string;
    statusApproved: string;
    statusReviewed: string;
    statusNeedsRevision: string;
    statusDraft: string;
  }
> = {
  ar: {
    teacherPrefix: (sub) => `مُعلّم ${sub || "المادة"}`,
    workspaceCrumb: "مساحة المعلم / لوحة المعلم",
    pageTitle: "لوحة المعلم",
    subtitle: (sub, grade) =>
      `نظرة واضحة إلى خططك ومهامك القادمة، في مساحة مخصّصة لمادة ${sub || "المادة المختارة"} (${grade || "—"}).`,
    liveStatsBanner: (sub, grade) =>
      `ⓘ جميع الإحصاءات أدناه مشتقة حيًّا من قاعدة البيانات للسياق النشط (${sub || "—"} · ${grade || "—"}) وليست أرقامًا ثابتة.`,
    loadError: "تعذر تحميل بيانات لوحة المعلم.",
    heroSubtitle: "أكمل مراجعة الخطة اليومية، ثم جهّز عرضك وحزمة ملفاتك من مساحة واحدة.",
    teacherFallback: "المعلم",
    planningDateLabel: "تاريخ التخطيط:",
    startNewPlanBtn: "← ابدأ خطة جديدة",
    statAttentionLabel: "مهام تحتاج انتباهك",
    statAttentionSub: "تقويم ناقص + مراجعة مصدر",
    statDraftsLabel: "مسودات قيد الإعداد",
    statDraftsSub: (total) => `من أصل ${total} خطط محفوظة`,
    statReviewedLabel: "خطط مكتملة المراجعة",
    statReviewedSub: "مراجعة اكتمال، لا توثيق للمصدر",
    statExportsLabel: "حزم التصدير المولّدة",
    statExportsSub: "ملفات DOCX / PDF / PPTX حقيقية",
    todayTasksTitle: "مهام اليوم",
    todayTasksDesc: "ترتيب مقترح لإنهاء المسودات وفصل عوائق الاعتماد عن توثيق المصدر",
    loadingTasks: "جارٍ تحميل مهام السياق...",
    noTasksText: "لا توجد مهام معلّقة حاليًا. بيئة العمل جاهزة لإعداد أول خطة.",
    createDailyPlanBtn: "+ إعداد خطة درس جديدة",
    sourceStatusTitle: "حالة مصدر المنهج",
    loadingText: "جارٍ التحميل...",
    sourceVerifiedBadge: "موثّق — مراجعة بشرية معتمدة",
    sourceUnverifiedBadge: "تجريبي — غير موثّق",
    sourceMissingNotes: "السنة الدراسية والطبعة والمصدر لم تُستكمل. يتطلب الاستخدام الرسمي مراجعة المصدر أولًا.",
    viewSourcesBtn: "عرض بيانات المصدر واستيراد PDF",
    noPdfBadge: "لا يوجد ملف منهج مرفوع",
    noPdfDesc: "ارفع ملف PDF للمنهج في هذا السياق لتوثيق الفصول والدروس وأرقام الصفحات.",
    uploadPdfBtn: "رفع كتاب المنهج (PDF)",
    recentPlansTitle: "أحدث الخطط المحفوظة",
    recentPlansDesc: (sub, grade) => `جميع السجلات أدناه معزولة ضمن السياق النشط (${sub || "—"} · ${grade || "—"})`,
    loadingPlans: "جارٍ تحميل الخطط...",
    noPlansText: (sub) => `لا توجد خطط محفوظة بعد في سياق (${sub || "المادة المحددة"}).`,
    createFirstDailyBtn: "+ إنشاء أول خطة يومية",
    colPlan: "الخطة",
    colType: "النمط",
    colUpdated: "آخر تعديل",
    colStatus: "الحالة",
    typeDaily: "يومية",
    typeWeekly: "أسبوعية",
    typeFiveDay: "خمسة أيام",
    continueDailyBtn: "← متابعة المسودة اليومية",
    recentActivityTitle: "النشاط الأخير والملفات",
    recentActivityDesc: "آخر العمليات والملفات المولّدة في هذا السياق",
    noActivityText: "لا يوجد نشاط مسجّل بعد في هذا السياق.",
    latestSavedPlanLabel: "أحدث خطة محفوظة",
    versionPrefix: "الإصدار",
    toolsSelectedLabel: (count) => `اختيار ${count} وسائل تعليمية`,
    toolsEnabledBadge: "مفعّلة",
    downloadBtn: "تنزيل",
    statusApproved: "معتمدة",
    statusReviewed: "مكتملة المراجعة",
    statusNeedsRevision: "تقويم ناقص / تحتاج تعديلًا",
    statusDraft: "مسودة",
  },
  en: {
    teacherPrefix: (sub) => `${sub ? isolateBidi(sub) : "Subject"} Teacher`,
    workspaceCrumb: "Teacher Workspace / Dashboard",
    pageTitle: "Teacher Dashboard",
    subtitle: (sub, grade) =>
      `A clear overview of your plans and upcoming tasks in a dedicated workspace for ${sub ? isolateBidi(sub) : "your subject"} (${grade ? isolateBidi(grade) : "—"}).`,
    liveStatsBanner: (sub, grade) =>
      `ⓘ All metrics below are queried live from the database for the active context (${sub ? isolateBidi(sub) : "—"} · ${grade ? isolateBidi(grade) : "—"}), not static numbers.`,
    loadError: "Unable to load teacher dashboard data.",
    heroSubtitle: "Complete your daily plan review, then prepare your presentation slides and export package from one place.",
    teacherFallback: "Teacher",
    planningDateLabel: "Planning Date:",
    startNewPlanBtn: "Start a New Plan →",
    statAttentionLabel: "Items Needing Attention",
    statAttentionSub: "Missing assessment + source review",
    statDraftsLabel: "Drafts in Progress",
    statDraftsSub: (total) => `Out of ${total} saved plans`,
    statReviewedLabel: "Reviewed Plans",
    statReviewedSub: "Completeness check only, not source verification",
    statExportsLabel: "Generated Export Packages",
    statExportsSub: "Real DOCX / PDF / PPTX artifacts",
    todayTasksTitle: "Today's Tasks",
    todayTasksDesc: "Suggested priority order separating approval blockers from source verification",
    loadingTasks: "Loading context tasks...",
    noTasksText: "No pending tasks right now. Your workspace is ready for your first lesson plan.",
    createDailyPlanBtn: "+ Create New Lesson Plan",
    sourceStatusTitle: "Curriculum Source Status",
    loadingText: "Loading...",
    sourceVerifiedBadge: "Verified — Human Review Approved",
    sourceUnverifiedBadge: "Draft — Unverified",
    sourceMissingNotes: "Year, edition, and source URL are incomplete. Official use requires source review first.",
    viewSourcesBtn: "View Source Metadata & Import PDF",
    noPdfBadge: "No Curriculum PDF Uploaded",
    noPdfDesc: "Upload a curriculum textbook PDF in this context to document chapters, lessons, and page numbers.",
    uploadPdfBtn: "Upload Curriculum PDF",
    recentPlansTitle: "Latest Saved Plans",
    recentPlansDesc: (sub, grade) => `All records below are isolated within the active context (${sub ? isolateBidi(sub) : "—"} · ${grade ? isolateBidi(grade) : "—"})`,
    loadingPlans: "Loading plans...",
    noPlansText: (sub) => `No saved plans yet in context (${sub ? isolateBidi(sub) : "selected subject"}).`,
    createFirstDailyBtn: "+ Create First Daily Plan",
    colPlan: "Plan",
    colType: "Type",
    colUpdated: "Planning Date",
    colStatus: "Status",
    typeDaily: "Daily",
    typeWeekly: "Weekly",
    typeFiveDay: "Five-Day",
    continueDailyBtn: "Continue Daily Draft →",
    recentActivityTitle: "Recent Activity & Files",
    recentActivityDesc: "Latest actions and exported artifacts in this context",
    noActivityText: "No activity recorded yet in this context.",
    latestSavedPlanLabel: "Latest Saved Plan",
    versionPrefix: "Version",
    toolsSelectedLabel: (count) => `${count} teaching aids selected`,
    toolsEnabledBadge: "Active",
    downloadBtn: "Download",
    statusApproved: "Approved",
    statusReviewed: "Review Complete",
    statusNeedsRevision: "Needs Revision",
    statusDraft: "Draft",
  },
  fr: {
    teacherPrefix: (sub) => `Enseignant · ${sub ? isolateBidi(sub) : "Matière"}`,
    workspaceCrumb: "Espace Enseignant / Tableau de bord",
    pageTitle: "Tableau de bord",
    subtitle: (sub, grade) =>
      `Vue d'ensemble claire de vos plans et tâches à venir pour ${sub ? isolateBidi(sub) : "la matière sélectionnée"} (${grade ? isolateBidi(grade) : "—"}).`,
    liveStatsBanner: (sub, grade) =>
      `ⓘ Toutes les statistiques ci-dessous proviennent en direct de la base pour le contexte actif (${sub ? isolateBidi(sub) : "—"} · ${grade ? isolateBidi(grade) : "—"}).`,
    loadError: "Impossible de charger le tableau de bord.",
    heroSubtitle: "Terminez la révision du plan quotidien, puis préparez votre présentation et votre dossier d'export.",
    teacherFallback: "Enseignant",
    planningDateLabel: "Date de planification :",
    startNewPlanBtn: "Nouveau plan →",
    statAttentionLabel: "Éléments à vérifier",
    statAttentionSub: "Évaluation manquante + vérification source",
    statDraftsLabel: "Brouillons en cours",
    statDraftsSub: (total) => `Sur ${total} plans enregistrés`,
    statReviewedLabel: "Plans révisés",
    statReviewedSub: "Complétude uniquement, hors vérification source",
    statExportsLabel: "Exports générés",
    statExportsSub: "Fichiers DOCX / PDF / PPTX réels",
    todayTasksTitle: "Tâches du jour",
    todayTasksDesc: "Ordre suggéré séparant les blocages de validation de la vérification des sources",
    loadingTasks: "Chargement des tâches...",
    noTasksText: "Aucune tâche en attente. Votre espace est prêt pour votre premier plan.",
    createDailyPlanBtn: "+ Créer un plan de cours",
    sourceStatusTitle: "État de la source",
    loadingText: "Chargement...",
    sourceVerifiedBadge: "Vérifiée — Révision humaine validée",
    sourceUnverifiedBadge: "Brouillon — Non vérifié",
    sourceMissingNotes: "Année, édition ou lien source incomplet. Une vérification est requise avant usage officiel.",
    viewSourcesBtn: "Voir la source et importer un PDF",
    noPdfBadge: "Aucun manuel PDF importé",
    noPdfDesc: "Importez le PDF du programme dans ce contexte pour documenter chapitres et pages.",
    uploadPdfBtn: "Importer le manuel (PDF)",
    recentPlansTitle: "Plans récents enregistrés",
    recentPlansDesc: (sub, grade) => `Tous les enregistrements sont isolés dans le contexte actif (${sub ? isolateBidi(sub) : "—"} · ${grade ? isolateBidi(grade) : "—"})`,
    loadingPlans: "Chargement des plans...",
    noPlansText: (sub) => `Aucun plan enregistré dans ce contexte (${sub ? isolateBidi(sub) : "matière"}).`,
    createFirstDailyBtn: "+ Créer le premier plan",
    colPlan: "Plan",
    colType: "Type",
    colUpdated: "Date",
    colStatus: "Statut",
    typeDaily: "Quotidien",
    typeWeekly: "Hebdomadaire",
    typeFiveDay: "5 jours",
    continueDailyBtn: "Continuer le brouillon →",
    recentActivityTitle: "Activité récente et fichiers",
    recentActivityDesc: "Dernières opérations et fichiers générés dans ce contexte",
    noActivityText: "Aucune activité enregistrée dans ce contexte.",
    latestSavedPlanLabel: "Dernier plan enregistré",
    versionPrefix: "Version",
    toolsSelectedLabel: (count) => `${count} outils pédagogiques sélectionnés`,
    toolsEnabledBadge: "Actif",
    downloadBtn: "Télécharger",
    statusApproved: "Approuvé",
    statusReviewed: "Révision terminée",
    statusNeedsRevision: "À réviser",
    statusDraft: "Brouillon",
  },
};

function formatPlanStatusLabel(status: string | undefined, uiLang: UiLang) {
  const c = DASHBOARD_COPY[uiLang];
  if (status === "approved") return c.statusApproved;
  if (status === "reviewed") return c.statusReviewed;
  if (status === "needs_revision") return c.statusNeedsRevision;
  return c.statusDraft;
}

function formatPlanStatusBadgeClass(status?: string) {
  if (status === "approved" || status === "reviewed") return "badge-success";
  if (status === "needs_revision") return "badge-blocker";
  return "badge-neutral";
}

function formatDashboardGreeting(rawName?: string, uiLang: UiLang = "ar"): string {
  const trimmed = (rawName || "").trim();
  if (uiLang === "en") {
    return trimmed ? `Welcome, ${isolateBidi(trimmed)} — let's plan a clear lesson.` : "Welcome — let's plan a clear lesson.";
  }
  if (uiLang === "fr") {
    return trimmed ? `Bienvenue, ${isolateBidi(trimmed)} — préparons un cours structuré.` : "Bienvenue — préparons un cours structuré.";
  }
  if (!trimmed) {
    return "مرحبًا بك، لنخطّط لحصة واضحة.";
  }
  const hasExistingTitle =
    /^(?:أستاذ(?:ة)?|الأستاذ(?:ة)?|الدكتور(?:ة)?|دكتور(?:ة)?|المعلم(?:ة)?|المدرّ?س(?:ة)?)(?:\s|$)/i.test(trimmed) ||
    /^(?:د|أ|م)\s*[.\/،:-]/.test(trimmed) ||
    /^(?:Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.|Mme\.?)\s+/i.test(trimmed);
  const charCount = Array.from(trimmed).length;
  const addressed = hasExistingTitle || charCount <= 1 ? trimmed : `أستاذ ${trimmed}`;
  return `مرحبًا ${addressed}، لنخطّط لحصة واضحة.`;
}

export default function DashboardPage() {
  const { activeContext, activeContextId, uiLang, uiIsRtl, apiFetch, downloadFile } = useTeacherApp();
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const copy = DASHBOARD_COPY[uiLang];

  useEffect(() => {
    let cancelled = false;
    setSummary(null);
    setErrorMsg("");
    async function load() {
      setLoading(true);
      try {
        const res = await apiFetch(`/api/dashboard?contextId=${encodeURIComponent(activeContextId)}`);
        if (!cancelled) setSummary(res);
      } catch (e: any) {
        if (!cancelled) setErrorMsg(e?.message || copy.loadError);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (activeContextId) {
      load();
    } else {
      setLoading(false);
    }
    return () => {
      cancelled = true;
    };
  }, [activeContextId, apiFetch, copy.loadError]);

  const stats = summary?.stats || {
    attentionCount: 0,
    draftsCount: 0,
    totalPlansCount: 0,
    reviewedCount: 0,
    exportsCount: 0,
  };

  const resolveTaskRoute = (t: any) => {
    const raw = t.targetRoute || "/review";
    if (raw.startsWith("/daily-plan?planId=")) {
      const pid = raw.split("planId=")[1];
      const matched = summary?.recentPlans?.find((p: any) => p.id === pid);
      if (matched?.planType === "weekly") return `/weekly-plan?planId=${encodeURIComponent(pid)}`;
      if (matched?.planType === "five_day") return `/five-day-plan?planId=${encodeURIComponent(pid)}`;
    }
    return raw;
  };

  const planTypeLabel = (planType?: string) => {
    if (planType === "daily") return copy.typeDaily;
    if (planType === "weekly") return copy.typeWeekly;
    return copy.typeFiveDay;
  };

  return (
    <div dir={uiIsRtl ? "rtl" : "ltr"}>
      <div className="breadcrumb-line">
        {copy.teacherPrefix(activeContext?.subject)} / {copy.workspaceCrumb}
      </div>
      <h1 className="page-title">{copy.pageTitle}</h1>
      <p className="page-subtitle">
        {copy.subtitle(activeContext?.subject || "", activeContext?.grade || "—")}
      </p>

      <div className="info-banner">
        <span>{copy.liveStatsBanner(activeContext?.subject || "—", activeContext?.grade || "—")}</span>
      </div>

      {errorMsg && (
        <div className="blocker-banner">
          <span>⛔ {errorMsg}</span>
        </div>
      )}

      {/* Hero Welcome Banner */}
      <div className="hero-banner-card">
        <div>
          <h2 style={{ fontSize: "1.45rem", fontWeight: 800, marginBottom: "6px" }}>
            {formatDashboardGreeting(activeContext?.teacherName, uiLang)}
          </h2>
          <p style={{ fontSize: "0.9rem", color: "var(--sidebar-text)", marginBottom: "6px" }}>
            {copy.heroSubtitle}
          </p>
          <div style={{ fontSize: "0.78rem", color: "var(--sidebar-muted)" }}>
            <span dir="auto">{activeContext?.teacherName || copy.teacherFallback}</span> | {copy.planningDateLabel}{" "}
            {activeContext?.planningDate || new Date().toISOString().split("T")[0]}
          </div>
        </div>
        <Link href="/daily-plan" className="btn btn-primary" style={{ backgroundColor: "#176B52", padding: "11px 22px" }}>
          {copy.startNewPlanBtn}
        </Link>
      </div>

      {/* 4 Derived Stat Cards */}
      <div className="stats-grid-4">
        <div className="stat-card">
          <div className="stat-label">{copy.statAttentionLabel}</div>
          <div className="stat-number">{loading ? "..." : stats.attentionCount}</div>
          <div className="stat-sub">{copy.statAttentionSub}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{copy.statDraftsLabel}</div>
          <div className="stat-number">{loading ? "..." : stats.draftsCount}</div>
          <div className="stat-sub">{copy.statDraftsSub(stats.totalPlansCount)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{copy.statReviewedLabel}</div>
          <div className="stat-number">{loading ? "..." : stats.reviewedCount}</div>
          <div className="stat-sub">{copy.statReviewedSub}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{copy.statExportsLabel}</div>
          <div className="stat-number">{loading ? "..." : stats.exportsCount}</div>
          <div className="stat-sub">{copy.statExportsSub}</div>
        </div>
      </div>

      {/* Main Split: Today's Tasks (2/3) & Curriculum Source Status (1/3) */}
      <div className="main-split-grid">
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>{copy.todayTasksTitle}</h3>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
            {copy.todayTasksDesc}
          </p>

          {loading ? (
            <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--text-secondary)" }}>
              {copy.loadingTasks}
            </div>
          ) : !summary?.todayTasks || summary.todayTasks.length === 0 ? (
            <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--text-secondary)" }}>
              <p style={{ marginBottom: "12px", fontSize: "0.9rem" }}>{copy.noTasksText}</p>
              <Link href="/daily-plan" className="btn btn-primary" style={{ fontSize: "0.84rem" }}>
                {copy.createDailyPlanBtn}
              </Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {summary.todayTasks.map((t: any) => (
                <div
                  key={t.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    padding: "12px 14px",
                    borderRadius: "10px",
                    border: "1px solid var(--border-subtle)",
                    backgroundColor: "#fbfcfb",
                    gap: "12px",
                  }}
                >
                  <div style={{ minWidth: 0, flex: "1 1 200px" }}>
                    <div style={{ fontWeight: 700, fontSize: "0.92rem" }}>
                      <Link href={resolveTaskRoute(t)} dir="auto" style={{ color: "inherit", textDecoration: "none" }}>
                        {t.title}
                      </Link>
                    </div>
                    <div dir="auto" style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {t.subtitle}
                    </div>
                  </div>
                  <span
                    dir="auto"
                    className={`badge ${
                      t.badgeType === "blocker"
                        ? "badge-blocker"
                        : t.badgeType === "warning"
                        ? "badge-warning"
                        : "badge-neutral"
                    }`}
                  >
                    {t.badge}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "8px" }}>{copy.sourceStatusTitle}</h3>
          {loading ? (
            <div style={{ padding: "18px 0", color: "var(--text-secondary)", fontSize: "0.85rem" }}>{copy.loadingText}</div>
          ) : summary?.sources && summary.sources.length > 0 ? (
            <div>
              <span
                className={`badge ${
                  summary.sources[0].verificationStatus === "human_verified" ? "badge-success" : "badge-warning"
                }`}
                style={{ marginBottom: "10px" }}
              >
                {summary.sources[0].verificationStatus === "human_verified"
                  ? copy.sourceVerifiedBadge
                  : copy.sourceUnverifiedBadge}
              </span>
              <div dir="auto" style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: "6px" }}>
                {summary.sources[0].title}
              </div>
              <p dir="auto" style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                {summary.sources[0].reviewNotes || copy.sourceMissingNotes}
              </p>
              <Link href="/sources" className="btn btn-secondary" style={{ width: "100%" }}>
                {copy.viewSourcesBtn}
              </Link>
            </div>
          ) : (
            <div>
              <span className="badge badge-warning" style={{ marginBottom: "10px" }}>
                {copy.noPdfBadge}
              </span>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                {copy.noPdfDesc}
              </p>
              <Link href="/sources" className="btn btn-secondary" style={{ width: "100%" }}>
                {copy.uploadPdfBtn}
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Split: Recent Plans Table (2/3) & Recent Exports/Activity (1/3) */}
      <div className="main-split-grid">
        <div className="card">
          <h3 style={{ fontSize: "1.15rem", fontWeight: 800, marginBottom: "4px" }}>{copy.recentPlansTitle}</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            {copy.recentPlansDesc(activeContext?.subject || "—", activeContext?.grade || "—")}
          </p>

          {loading ? (
            <div style={{ textAlign: "center", padding: "26px 14px", color: "var(--text-secondary)" }}>
              {copy.loadingPlans}
            </div>
          ) : !summary?.recentPlans || summary.recentPlans.length === 0 ? (
            <div style={{ textAlign: "center", padding: "34px 14px", color: "var(--text-secondary)" }}>
              <p style={{ marginBottom: "12px", fontSize: "0.92rem" }}>
                {copy.noPlansText(activeContext?.subject || "")}
              </p>
              <Link href="/daily-plan" className="btn btn-primary">
                {copy.createFirstDailyBtn}
              </Link>
            </div>
          ) : (
            <div className="table-scroll-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{copy.colPlan}</th>
                    <th>{copy.colType}</th>
                    <th>{copy.colUpdated}</th>
                    <th>{copy.colStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recentPlans.map((p: any) => (
                    <tr key={p.id}>
                      <td style={{ fontWeight: 700 }}>
                        <Link
                          href={
                            p.planType === "five_day"
                              ? `/five-day-plan?planId=${encodeURIComponent(p.id)}`
                              : p.planType === "weekly"
                              ? `/weekly-plan?planId=${encodeURIComponent(p.id)}`
                              : `/daily-plan?planId=${encodeURIComponent(p.id)}`
                          }
                          dir="auto"
                          style={{ color: "var(--text-main)", textDecoration: "none" }}
                        >
                          {p.title}
                        </Link>
                      </td>
                      <td>{planTypeLabel(p.planType)}</td>
                      <td>{p.planningDate || "—"}</td>
                      <td>
                        <span className={`badge ${formatPlanStatusBadgeClass(p.status)}`}>
                          {formatPlanStatusLabel(p.status, uiLang)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: "14px" }}>
            <Link href="/daily-plan" className="btn btn-secondary">
              {copy.continueDailyBtn}
            </Link>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, marginBottom: "4px" }}>{copy.recentActivityTitle}</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
            {copy.recentActivityDesc}
          </p>

          {loading ? (
            <div style={{ textAlign: "center", padding: "20px 12px", color: "var(--text-secondary)" }}>
              {copy.loadingText}
            </div>
          ) : (!summary?.recentPlans || summary.recentPlans.length === 0) &&
            (!summary?.recentExports || summary.recentExports.length === 0) &&
            (!activeContext?.selectedTools || activeContext.selectedTools.length === 0) ? (
            <div style={{ textAlign: "center", padding: "26px 12px", color: "var(--text-secondary)" }}>
              <p style={{ fontSize: "0.85rem" }}>{copy.noActivityText}</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {summary?.recentPlans?.[0] && (
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div style={{ minWidth: 0, flex: "1 1 160px" }}>
                    <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>{copy.latestSavedPlanLabel}</div>
                    <div dir="auto" style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                      {summary.recentPlans[0].title} · v{summary.recentPlans[0].version}
                    </div>
                  </div>
                  <span className={`badge ${formatPlanStatusBadgeClass(summary.recentPlans[0].status)}`}>
                    {formatPlanStatusLabel(summary.recentPlans[0].status, uiLang)}
                  </span>
                </div>
              )}

              {activeContext?.selectedTools && activeContext.selectedTools.length > 0 && (
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div style={{ minWidth: 0, flex: "1 1 160px" }}>
                    <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>
                      {copy.toolsSelectedLabel(activeContext.selectedTools.length)}
                    </div>
                    <div dir="auto" style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                      {activeContext.selectedTools.join("، ")}
                    </div>
                  </div>
                  <span className="badge badge-success">{copy.toolsEnabledBadge}</span>
                </div>
              )}

              {(summary?.recentExports || []).map((ex: any) => (
                <div
                  key={ex.id}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div style={{ minWidth: 0, flex: "1 1 160px" }}>
                    <div dir="ltr" style={{ fontWeight: 700, fontSize: "0.84rem", overflowWrap: "anywhere", textAlign: "start" }}>
                      {ex.fileName}
                    </div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
                      {copy.versionPrefix} v{ex.planVersion} · {(ex.fileSize / 1024).toFixed(1)} KB
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await downloadFile(`/api/exports/${ex.id}/download?contextId=${encodeURIComponent(activeContextId)}`, ex.fileName);
                      } catch (err: any) {
                        setErrorMsg(err?.message || copy.loadError);
                      }
                    }}
                    className="badge badge-success"
                    style={{ textDecoration: "none", border: 0, cursor: "pointer" }}
                  >
                    {copy.downloadBtn}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
