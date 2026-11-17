"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export interface EducationalContextItem {
  id: string;
  subject: string;
  grade: string;
  country: string;
  curriculumName: string;
  language: string;
  year: string;
  edition: string;
  uiLanguage: string;
  teacherName: string;
  schoolName: string;
  sectionName: string;
  planningDate: string;
  schoolDays: string[];
  holidays: string[];
  defaultPeriodMinutes: number;
  defaultPeriodsCount: number;
  selectedTools: string[];
  documentPreferences: Record<string, any>;
  activeTemplateId?: string;
  missingContextFields: string[];
  version: number;
}

export interface AiStatusInfo {
  loading: boolean;
  available: boolean;
  configured: boolean;
  mode: "live" | "fallback";
  textGenerationReady: boolean;
  visionGenerationReady: boolean;
  fallbackAvailable: boolean;
  model: string;
  visionModel: string;
}

export interface SourceStatusSummary {
  loading: boolean;
  total: number;
  verifiedCount: number;
  pendingCount: number;
  hasUploadedPdf: boolean;
  latestTitle: string;
  latestVerificationStatus: string;
}

export type UiLang = "ar" | "en" | "fr";

interface AppContextValue {
  contexts: EducationalContextItem[];
  activeContext: EducationalContextItem | null;
  activeContextId: string;
  loadingContext: boolean;
  uiLang: UiLang;
  uiIsRtl: boolean;
  aiStatus: AiStatusInfo;
  sourceStatus: SourceStatusSummary;
  switchContext: (ctxId: string) => void;
  refreshContexts: () => Promise<void>;
  refreshAiStatus: () => Promise<void>;
  refreshSourceStatus: (ctxId?: string) => Promise<void>;
  apiFetch: (path: string, options?: RequestInit) => Promise<any>;
  downloadFile: (path: string, fileName?: string) => Promise<void>;
  openNewContextModal: () => void;
}

const DEFAULT_AI_STATUS: AiStatusInfo = {
  loading: true,
  available: false,
  configured: false,
  mode: "fallback",
  textGenerationReady: false,
  visionGenerationReady: false,
  fallbackAvailable: true,
  model: "",
  visionModel: "",
};

const DEFAULT_SOURCE_STATUS: SourceStatusSummary = {
  loading: false,
  total: 0,
  verifiedCount: 0,
  pendingCount: 0,
  hasUploadedPdf: false,
  latestTitle: "",
  latestVerificationStatus: "pending_review",
};

const TeacherAppContext = createContext<AppContextValue | null>(null);

export function useTeacherApp() {
  const ctx = useContext(TeacherAppContext);
  if (!ctx) {
    throw new Error("useTeacherApp must be used inside AppShellProvider");
  }
  return ctx;
}

function isRtlLanguage(lang?: string): boolean {
  const lower = (lang || "ar").toLowerCase();
  return lower.startsWith("ar") || lower.startsWith("ku") || lower.startsWith("fa") || lower.startsWith("he");
}

function resolveUiLang(lang?: string): UiLang {
  const lower = (lang || "ar").toLowerCase();
  if (lower.startsWith("en")) return "en";
  if (lower.startsWith("fr")) return "fr";
  return "ar";
}

function stripTitlePrefix(name: string): string {
  let clean = name.trim();
  const prefixPatterns = [
    /^(?:الدكتور(?:ة)?|دكتور(?:ة)?|أستاذ(?:ة)?|الأستاذ(?:ة)?|المعلم(?:ة)?|المدرّ?س(?:ة)?)(?:\s+|$)/i,
    /^(?:د|أ|م)\s*[.\/،:-]\s*/,
    /^(?:Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.|Mme\.?)\s+/i,
  ];
  for (let i = 0; i < 2; i += 1) {
    for (const pat of prefixPatterns) {
      clean = clean.replace(pat, "").trim();
    }
  }
  return clean;
}

function formatAvatarInitials(rawName?: string): string {
  const trimmed = (rawName || "").trim();
  if (!trimmed) return "👤";
  const clean = stripTitlePrefix(trimmed) || trimmed;
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length === 0) return "👤";
  const firstChars = Array.from(words[0]);
  if (Array.from(clean).length <= 1 || words.length === 1) {
    return firstChars[0] || "👤";
  }
  if (/^[A-Za-z]/.test(words[0])) {
    const secondChars = Array.from(words[1]);
    return `${firstChars[0] || ""}${secondChars[0] || ""}`.toUpperCase();
  }
  return firstChars[0] || "👤";
}

const NAV_ITEMS = [
  { href: "/", labelAr: "لوحة المعلم", labelEn: "Dashboard", labelFr: "Tableau de bord", icon: "⊞" },
  { href: "/sources", labelAr: "استيراد كتاب المنهج", labelEn: "Import Curriculum PDF", labelFr: "Importer le manuel PDF", icon: "📤" },
  { href: "/curriculum", labelAr: "المنهج", labelEn: "Curriculum", labelFr: "Programme", icon: "📖" },
  { href: "/lessons", labelAr: "اختيار الدرس", labelEn: "Lessons", labelFr: "Leçons", icon: "☰" },
  { href: "/tools", labelAr: "الوسائل وأدوات المدرس", labelEn: "Teacher Tools & Aids", labelFr: "Outils pédagogiques", icon: "📏" },
  { href: "/settings", labelAr: "إعداد الخطة", labelEn: "Plan & Context Setup", labelFr: "Paramètres du contexte", icon: "⚙" },
  { href: "/daily-plan", labelAr: "الخطة اليومية", labelEn: "Daily Plan", labelFr: "Plan quotidien", icon: "📝" },
  { href: "/weekly-plan", labelAr: "الخطة الأسبوعية", labelEn: "Weekly Plan", labelFr: "Plan hebdomadaire", icon: "🗓" },
  { href: "/five-day-plan", labelAr: "خطة خمسة أيام", labelEn: "Five-Day Plan", labelFr: "Plan sur 5 jours", icon: "📅" },
  { href: "/review", labelAr: "مراجعة الخطة", labelEn: "Final Plan Review", labelFr: "Révision du plan", icon: "✓" },
  { href: "/reports", labelAr: "التقارير", labelEn: "Reports", labelFr: "Rapports", icon: "📊" },
  { href: "/presentations", labelAr: "العروض التقديمية", labelEn: "Presentations & PPTX", labelFr: "Présentations PPTX", icon: "🖥" },
  { href: "/export-package", labelAr: "تصدير الحزمة", labelEn: "Export Package", labelFr: "Exporter le dossier", icon: "📦" },
];

export const WORKFLOW_STEPS = [
  { step: 1, label: "المصدر", labelEn: "Source", labelFr: "Source", href: "/sources" },
  { step: 2, label: "المنهج", labelEn: "Curriculum", labelFr: "Programme", href: "/curriculum" },
  { step: 3, label: "الدرس", labelEn: "Lesson", labelFr: "Leçon", href: "/lessons" },
  { step: 4, label: "الوسائل", labelEn: "Tools", labelFr: "Outils", href: "/tools" },
  { step: 5, label: "الإعداد", labelEn: "Setup", labelFr: "Réglages", href: "/settings" },
  { step: 6, label: "بناء الخطة", labelEn: "Build Plan", labelFr: "Planifier", href: "/daily-plan" },
  { step: 7, label: "المراجعة", labelEn: "Review", labelFr: "Révision", href: "/review" },
  { step: 8, label: "التقارير", labelEn: "Reports", labelFr: "Rapports", href: "/reports" },
  { step: 9, label: "العروض", labelEn: "Slides", labelFr: "Diapos", href: "/presentations" },
  { step: 10, label: "التصدير", labelEn: "Export", labelFr: "Export", href: "/export-package" },
];

export function WorkflowStepper({ activeStep }: { activeStep: number }) {
  const ctx = useContext(TeacherAppContext);
  const uiLang: UiLang = ctx?.uiLang || "ar";
  return (
    <nav className="stepper-bar" aria-label={uiLang === "en" ? "Workflow steps" : uiLang === "fr" ? "Étapes du travail" : "خطوات العمل"}>
      {WORKFLOW_STEPS.map((st) => {
        const isDone = st.step < activeStep;
        const isCurrent = st.step === activeStep;
        const labelText = uiLang === "en" ? st.labelEn : uiLang === "fr" ? st.labelFr : st.label;
        return (
          <Link
            key={st.step}
            href={st.href}
            className={`stepper-item ${isDone ? "done" : ""} ${isCurrent ? "active" : ""}`}
          >
            <span className="step-circle">{isDone ? "✓" : st.step}</span>
            <span>{labelText}</span>
          </Link>
        );
      })}
    </nav>
  );
}

const buildCleanCtxForm = (teacherName = "") => ({
  subject: "",
  grade: "",
  country: "",
  curriculumName: "",
  language: "ar",
  year: "",
  edition: "",
  teacherName,
  schoolName: "",
  sectionName: "",
  defaultPeriodMinutes: 45,
});

export function AppShellProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [contexts, setContexts] = useState<EducationalContextItem[]>([]);
  const [activeContextId, setActiveContextId] = useState<string>("");
  const [loadingContext, setLoadingContext] = useState<boolean>(true);
  const [contextError, setContextError] = useState<string>("");
  const [aiStatus, setAiStatus] = useState<AiStatusInfo>(DEFAULT_AI_STATUS);
  const [sourceStatus, setSourceStatus] = useState<SourceStatusSummary>(DEFAULT_SOURCE_STATUS);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [creatingContext, setCreatingContext] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string>("");
  const [accessPin, setAccessPin] = useState<string>("");
  const [pinInput, setPinInput] = useState<string>("");
  const [accessGranted, setAccessGranted] = useState<boolean>(false);
  const [accessError, setAccessError] = useState<string>("");

  // New Context Form State — Starts 100% clean with NO assumed subject, grade, country, or teacher
  const [newCtxForm, setNewCtxForm] = useState(() => buildCleanCtxForm(""));
  const [savedTeacherName, setSavedTeacherName] = useState<string>("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = window.localStorage.getItem("agy_teacher_name") || "";
      if (stored) {
        setSavedTeacherName(stored);
        setNewCtxForm((prev) => ({ ...prev, teacherName: prev.teacherName || stored }));
      }
    }
  }, []);

  const refreshAiStatus = useCallback(async () => {
    if (!accessPin) {
      setAiStatus({ ...DEFAULT_AI_STATUS, loading: false });
      return;
    }
    try {
      const res = await fetch("/api/ai/status", {
        cache: "no-store",
        headers: { "X-Pilot-Pin": accessPin },
      });
      if (res.status === 401 || res.status === 503) {
        setAccessPin("");
        setAccessGranted(false);
        if (typeof window !== "undefined") window.sessionStorage.removeItem("agy_pilot_pin");
        return;
      }
      if (!res.ok) {
        setAiStatus({ ...DEFAULT_AI_STATUS, loading: false });
        return;
      }
      const data = await res.json();
      const isLive = Boolean(
        data?.mode === "live" ||
          data?.configured === true ||
          data?.available === true ||
          data?.textGenerationReady === true
      );
      setAiStatus({
        loading: false,
        available: isLive,
        configured: Boolean(data?.configured ?? isLive),
        mode: data?.mode === "live" || data?.mode === "fallback" ? data.mode : isLive ? "live" : "fallback",
        textGenerationReady: Boolean(data?.textGenerationReady ?? isLive),
        visionGenerationReady: Boolean(data?.visionGenerationReady ?? isLive),
        fallbackAvailable: data?.fallbackAvailable !== false,
        model: data?.model || data?.textModel || (isLive ? "NVIDIA NIM" : "توليد منهجي احتياطي"),
        visionModel: data?.visionModel || (isLive ? "NVIDIA NIM Vision" : "تفريغ يدوي / محلي"),
      });
    } catch {
      setAiStatus({ ...DEFAULT_AI_STATUS, loading: false });
    }
  }, [accessPin]);

  const refreshSourceStatus = useCallback(
    async (ctxIdOverride?: string) => {
      const targetId = ctxIdOverride ?? activeContextId;
      if (!accessPin || !targetId) {
        setSourceStatus(DEFAULT_SOURCE_STATUS);
        return;
      }
      setSourceStatus((prev) => ({ ...prev, loading: true }));
      try {
        const res = await fetch(`/api/sources?contextId=${encodeURIComponent(targetId)}`, {
          cache: "no-store",
          headers: {
            "X-Pilot-Pin": accessPin,
            "X-Active-Context-Id": targetId,
          },
        });
        if (!res.ok) {
          setSourceStatus((prev) => ({ ...prev, loading: false }));
          return;
        }
        const data = await res.json();
        const items: any[] = data?.items || [];
        const verifiedItems = items.filter((s) => s.verificationStatus === "human_verified");
        const uploadedItems = items.filter((s) => s.extractionStatus && s.extractionStatus !== "no_file");
        const primary = verifiedItems[0] || items[0] || null;
        setSourceStatus({
          loading: false,
          total: items.length,
          verifiedCount: verifiedItems.length,
          pendingCount: Math.max(0, items.length - verifiedItems.length),
          hasUploadedPdf: uploadedItems.length > 0,
          latestTitle: primary?.title || "",
          latestVerificationStatus: primary?.verificationStatus || "pending_review",
        });
      } catch {
        setSourceStatus((prev) => ({ ...prev, loading: false }));
      }
    },
    [accessPin, activeContextId]
  );

  const refreshContexts = useCallback(async () => {
    if (!accessPin) {
      setLoadingContext(false);
      return;
    }
    setContextError("");
    try {
      const res = await fetch("/api/contexts", { cache: "no-store", headers: { "X-Pilot-Pin": accessPin } });
      if (res.status === 401 || res.status === 503) {
        setAccessPin("");
        setAccessGranted(false);
        if (typeof window !== "undefined") window.sessionStorage.removeItem("agy_pilot_pin");
        throw new Error(res.status === 503 ? "خدمة الوصول غير مهيأة؛ أبلغ المسؤول." : "انتهت جلسة الوصول؛ أدخل الرمز مجددًا.");
      }
      if (!res.ok) {
        throw new Error(`تعذر تحميل السياقات التعليمية من الخادم (${res.status}).`);
      }
      const data = await res.json();
      const list: EducationalContextItem[] = data.items || [];
      setContexts(list);
      if (list.length === 0) {
        setActiveContextId("");
        setSourceStatus(DEFAULT_SOURCE_STATUS);
        if (typeof window !== "undefined") {
          window.localStorage.removeItem("agy_active_context_id");
        }
        setShowModal(true); // Automatically show first-use onboarding setup
      } else {
        const savedId = typeof window !== "undefined" ? window.localStorage.getItem("agy_active_context_id") : null;
        const resolvedId = savedId && list.some((c) => c.id === savedId) ? savedId : list[0].id;
        setActiveContextId(resolvedId);
        if (typeof window !== "undefined") {
          window.localStorage.setItem("agy_active_context_id", resolvedId);
        }
        await refreshSourceStatus(resolvedId);
      }
    } catch (err: any) {
      console.error("Failed loading contexts:", err);
      setContextError(err?.message || "تعذر الاتصال بالخادم لتحميل السياقات التعليمية.");
    } finally {
      setLoadingContext(false);
    }
  }, [accessPin, refreshSourceStatus]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedPin = window.sessionStorage.getItem("agy_pilot_pin") || "";
    if (storedPin) {
      setAccessPin(storedPin);
      setAccessGranted(true);
    }
  }, []);

  useEffect(() => {
    if (accessPin) {
      refreshContexts();
      refreshAiStatus();
    }
  }, [accessPin, refreshContexts, refreshAiStatus]);

  const activeContext = contexts.find((c) => c.id === activeContextId) || (contexts.length > 0 ? contexts[0] : null);

  useEffect(() => {
    if (accessPin && activeContext?.id) {
      refreshSourceStatus(activeContext.id);
    }
  }, [accessPin, activeContext?.id, refreshSourceStatus]);

  useEffect(() => {
    if (activeContext?.teacherName) {
      setSavedTeacherName(activeContext.teacherName);
      if (typeof window !== "undefined") {
        window.localStorage.setItem("agy_teacher_name", activeContext.teacherName);
      }
    }
  }, [activeContext]);

  useEffect(() => {
    if (activeContext && typeof document !== "undefined") {
      const lang = activeContext.language || "ar";
      document.documentElement.lang = lang;
      document.documentElement.dir = isRtlLanguage(lang) ? "rtl" : "ltr";
    }
  }, [activeContext]);

  const switchContext = useCallback((ctxId: string) => {
    setActiveContextId(ctxId);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("agy_active_context_id", ctxId);
    }
  }, []);

  const openNewContextModal = useCallback(() => {
    setModalError("");
    setNewCtxForm(buildCleanCtxForm(savedTeacherName));
    setShowModal(true);
  }, [savedTeacherName]);

  const closeNewContextModal = useCallback(() => {
    setModalError("");
    setNewCtxForm(buildCleanCtxForm(savedTeacherName));
    setShowModal(false);
  }, [savedTeacherName]);

  const apiFetch = useCallback(
    async (path: string, options: RequestInit = {}) => {
      const currentCtxId = activeContext?.id || activeContextId;
      const headers = new Headers(options.headers || {});
      if (currentCtxId) {
        headers.set("X-Active-Context-Id", currentCtxId);
      }
      headers.set("X-Pilot-Pin", accessPin);
      if (options.body !== undefined && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      const res = await fetch(path, {
        ...options,
        headers,
        cache: "no-store",
      });
      if (res.status === 401 || res.status === 503) {
        setAccessPin("");
        setAccessGranted(false);
        if (typeof window !== "undefined") window.sessionStorage.removeItem("agy_pilot_pin");
        throw new Error(res.status === 503 ? "خدمة الوصول غير مهيأة؛ أبلغ المسؤول." : "انتهت جلسة الوصول؛ أدخل الرمز مجددًا.");
      }
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const json = await res.json();
        if (!res.ok) {
          throw new Error(json.message || `خطأ في الطلب (${res.status})`);
        }
        return json;
      }
      if (!res.ok) {
        throw new Error(`فشل الاتصال بالخادم (${res.status})`);
      }
      return res;
    },
    [activeContext, activeContextId, accessPin]
  );

  const downloadFile = useCallback(
    async (path: string, fileName?: string) => {
      const currentCtxId = activeContext?.id || activeContextId;
      const headers: Record<string, string> = {
        "X-Pilot-Pin": accessPin,
      };
      if (currentCtxId) {
        headers["X-Active-Context-Id"] = currentCtxId;
      }
      const res = await fetch(path, { cache: "no-store", headers });
      if (res.status === 401 || res.status === 503) {
        setAccessPin("");
        setAccessGranted(false);
        if (typeof window !== "undefined") window.sessionStorage.removeItem("agy_pilot_pin");
        throw new Error(res.status === 503 ? "خدمة الوصول غير مهيأة؛ أبلغ المسؤول." : "انتهت جلسة الوصول؛ أدخل الرمز مجددًا.");
      }
      if (!res.ok) {
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const json = await res.json().catch(() => null);
          if (json?.message) throw new Error(json.message);
        }
        throw new Error(`فشل تنزيل الملف (${res.status})`);
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const disposition = res.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const quotedName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      const responseName = encodedName ? decodeURIComponent(encodedName) : quotedName;
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = fileName || responseName || "download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    },
    [accessPin, activeContext, activeContextId]
  );

  const handleSubmitPin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAccessError("");
    const candidate = pinInput.trim();
    try {
      const res = await fetch("/api/contexts", { cache: "no-store", headers: { "X-Pilot-Pin": candidate } });
      if (res.status === 401 || res.status === 503) {
        throw new Error("رمز الوصول غير صحيح أو غير مهيأ.");
      }
      if (!res.ok) throw new Error("تعذر التحقق من رمز الوصول.");
      setAccessPin(candidate);
      setAccessGranted(true);
      setPinInput("");
      if (typeof window !== "undefined") window.sessionStorage.setItem("agy_pilot_pin", candidate);
    } catch (err: any) {
      setAccessError(err?.message || "تعذر التحقق من رمز الوصول.");
    }
  };

  const handleLogout = () => {
    setAccessPin("");
    setAccessGranted(false);
    setContexts([]);
    setActiveContextId("");
    setSourceStatus(DEFAULT_SOURCE_STATUS);
    setAiStatus({ ...DEFAULT_AI_STATUS, loading: false });
    setLoadingContext(false);
    if (typeof window !== "undefined") window.sessionStorage.removeItem("agy_pilot_pin");
  };

  const handleCreateContext = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingContext(true);
    setModalError("");
    try {
      if (typeof window !== "undefined" && newCtxForm.teacherName.trim()) {
        window.localStorage.setItem("agy_teacher_name", newCtxForm.teacherName.trim());
        setSavedTeacherName(newCtxForm.teacherName.trim());
      }
      const created = await apiFetch("/api/contexts", {
        method: "POST",
        body: JSON.stringify(newCtxForm),
      });
      await refreshContexts();
      switchContext(created.id);
      setNewCtxForm(buildCleanCtxForm(newCtxForm.teacherName.trim() || savedTeacherName));
      setShowModal(false);
    } catch (err: any) {
      setModalError(err?.message || "تعذر إنشاء السياق التعليمي.");
    } finally {
      setCreatingContext(false);
    }
  };

  const uiIsRtl = !activeContext || isRtlLanguage(activeContext.language);
  const uiLang: UiLang = activeContext ? resolveUiLang(activeContext.language) : "ar";
  const displayTeacherName = activeContext ? activeContext.teacherName : savedTeacherName;
  const avatarInitials = formatAvatarInitials(displayTeacherName);

  if (!accessGranted) {
    return (
      <main className="page-container" style={{ maxWidth: "480px", margin: "12vh auto" }}>
        <form className="card" onSubmit={handleSubmitPin}>
          <h1 className="page-title">رمز الوصول التجريبي</h1>
          <p className="page-subtitle">أدخل رمز الوصول للمتابعة. لا يتم حفظه بعد انتهاء جلسة المتصفح.</p>
          <label className="form-label" htmlFor="pilot-access-pin">رمز الوصول</label>
          <input
            id="pilot-access-pin"
            className="form-input"
            type="password"
            autoComplete="current-password"
            value={pinInput}
            onChange={(e) => setPinInput(e.target.value)}
            required
          />
          {accessError && <div className="blocker-banner">{accessError}</div>}
          <button className="btn btn-primary" type="submit" style={{ marginTop: "14px" }}>متابعة</button>
        </form>
      </main>
    );
  }

  return (
    <TeacherAppContext.Provider
      value={{
        contexts,
        activeContext,
        activeContextId: activeContext?.id || activeContextId,
        loadingContext,
        uiLang,
        uiIsRtl,
        aiStatus,
        sourceStatus,
        switchContext,
        refreshContexts,
        refreshAiStatus,
        refreshSourceStatus,
        apiFetch,
        downloadFile,
        openNewContextModal,
      }}
    >
      <div className="app-shell" dir={uiIsRtl ? "rtl" : "ltr"}>
        {/* Sidebar (#154434) */}
        <aside
          className={`app-sidebar ${sidebarOpen ? "open" : ""}`}
          aria-label={uiLang === "en" ? "Sidebar navigation" : uiLang === "fr" ? "Navigation latérale" : "القائمة الجانبية"}
        >
          <div className="brand-header">
            <div>
              <div className="brand-title">
                {activeContext?.subject
                  ? uiLang === "en"
                    ? `\u2068${activeContext.subject}\u2069 Teacher`
                    : uiLang === "fr"
                    ? `Enseignant · \u2068${activeContext.subject}\u2069`
                    : `مُعلّم ${activeContext.subject}`
                  : uiLang === "en"
                  ? "Teacher Assistant"
                  : uiLang === "fr"
                  ? "Assistant Enseignant"
                  : "مساعد المدرس"}
              </div>
              <div className="brand-subtitle">
                {uiLang === "en"
                  ? "Lesson planning for any subject & curriculum"
                  : uiLang === "fr"
                  ? "Planification de cours multi-matières"
                  : "مساحة التخطيط لأي مادة ومنهج"}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div className="brand-icon-box" aria-hidden="true">
                📖
              </div>
              <button
                type="button"
                className="sidebar-close-btn"
                onClick={() => setSidebarOpen(false)}
                aria-label={uiLang === "en" ? "Close sidebar" : uiLang === "fr" ? "Fermer le menu" : "إغلاق القائمة الجانبية"}
              >
                ✕
              </button>
            </div>
          </div>

          <div className="context-pill-card">
            <div className="context-pill-grade">
              {activeContext?.grade ||
                (uiLang === "en" ? "No context selected yet" : uiLang === "fr" ? "Aucun contexte sélectionné" : "لم يُحدد سياق بعد")}
            </div>
            <div className="context-pill-sub">
              {activeContext
                ? `${activeContext.subject} · ${activeContext.country}`
                : uiLang === "en"
                ? "Any subject · Any grade · Any country"
                : uiLang === "fr"
                ? "Toute matière · Tout niveau · Tout pays"
                : "أي مادة · أي صف · أي بلد"}
            </div>
            <div style={{ marginTop: "8px", display: "flex", gap: "6px" }}>
              {contexts.length > 0 ? (
                <select
                  aria-label={uiLang === "en" ? "Switch educational context" : uiLang === "fr" ? "Changer de contexte" : "تبديل السياق التعليمي"}
                  value={activeContext?.id || ""}
                  onChange={(e) => switchContext(e.target.value)}
                  style={{
                    width: "100%",
                    background: "rgba(0,0,0,0.22)",
                    color: "#fff",
                    border: "1px solid rgba(255,255,255,0.2)",
                    borderRadius: "6px",
                    padding: "5px 8px",
                    fontSize: "0.78rem",
                  }}
                >
                  {contexts.map((c) => (
                    <option key={c.id} value={c.id} style={{ color: "#111" }}>
                      {c.subject || "—"} — {c.grade || "—"} ({c.country || "—"})
                    </option>
                  ))}
                </select>
              ) : (
                <button
                  type="button"
                  onClick={openNewContextModal}
                  style={{
                    width: "100%",
                    background: "#226650",
                    color: "#fff",
                    border: "1px solid rgba(255,255,255,0.25)",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    fontWeight: 700,
                  }}
                >
                  {uiLang === "en" ? "+ Setup Educational Context" : uiLang === "fr" ? "+ Configurer un contexte" : "+ إعداد سياقك التعليمي"}
                </button>
              )}
              {contexts.length > 0 && (
                <button
                  type="button"
                  onClick={openNewContextModal}
                  title={uiLang === "en" ? "Add new context" : uiLang === "fr" ? "Ajouter un contexte" : "إضافة سياق تعليمي جديد"}
                  aria-label={uiLang === "en" ? "Add new context" : uiLang === "fr" ? "Ajouter un contexte" : "إضافة سياق تعليمي جديد"}
                  style={{
                    background: "#226650",
                    color: "#fff",
                    border: "1px solid rgba(255,255,255,0.25)",
                    borderRadius: "6px",
                    padding: "4px 9px",
                    cursor: "pointer",
                    fontWeight: 700,
                  }}
                >
                  +
                </button>
              )}
            </div>
          </div>

          <nav className="sidebar-nav">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              const label = uiLang === "en" ? item.labelEn : uiLang === "fr" ? item.labelFr : item.labelAr;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`sidebar-link ${isActive ? "active" : ""}`}
                >
                  <span aria-hidden="true">{item.icon}</span>
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="sidebar-source-status">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "6px", marginBottom: "4px", flexWrap: "wrap" }}>
              <span style={{ fontWeight: 700, color: "#fff" }}>
                {activeContext
                  ? uiLang === "en"
                    ? "Curriculum Source"
                    : uiLang === "fr"
                    ? "Source du programme"
                    : "حالة مصدر المنهج"
                  : uiLang === "en"
                  ? "Context Setup"
                  : uiLang === "fr"
                  ? "Configuration"
                  : "تهيئة السياق"}
              </span>
              {activeContext && (
                <span
                  className={`badge ${
                    sourceStatus.verifiedCount > 0
                      ? "badge-success"
                      : sourceStatus.total > 0
                      ? "badge-warning"
                      : "badge-neutral"
                  }`}
                  style={{ fontSize: "0.68rem", padding: "2px 7px" }}
                >
                  {sourceStatus.verifiedCount > 0
                    ? uiLang === "en"
                      ? "Verified"
                      : uiLang === "fr"
                      ? "Vérifiée"
                      : "موثّق"
                    : sourceStatus.total > 0
                    ? uiLang === "en"
                      ? "Pending"
                      : uiLang === "fr"
                      ? "En attente"
                      : "بانتظار التوثيق"
                    : uiLang === "en"
                    ? "No file"
                    : uiLang === "fr"
                    ? "Aucun fichier"
                    : "غير مرفوع"}
                </span>
              )}
            </div>
            <div style={{ color: "var(--sidebar-muted)" }}>
              {!activeContext
                ? uiLang === "en"
                  ? "Enter your details and context to begin."
                  : uiLang === "fr"
                  ? "Saisissez vos informations pour commencer."
                  : "أدخل بياناتك وسياقك للبدء."
                : sourceStatus.verifiedCount > 0
                ? activeContext.edition && activeContext.year
                  ? uiLang === "en"
                    ? `Verified · Edition: ${activeContext.edition} · Year: ${activeContext.year}`
                    : uiLang === "fr"
                    ? `Vérifiée · Édition : ${activeContext.edition} · Année : ${activeContext.year}`
                    : `موثّق · الطبعة: ${activeContext.edition} · السنة: ${activeContext.year}`
                  : uiLang === "en"
                  ? `Verified source: ${sourceStatus.latestTitle || "Ready"}`
                  : uiLang === "fr"
                  ? `Source vérifiée : ${sourceStatus.latestTitle || "Prête"}`
                  : `تم توثيق المصدر: ${sourceStatus.latestTitle || "معتمد"}`
                : sourceStatus.hasUploadedPdf
                ? uiLang === "en"
                  ? "PDF uploaded — complete metadata & verify in Sources."
                  : uiLang === "fr"
                  ? "PDF importé — complétez et vérifiez dans Sources."
                  : "تم رفع ملف PDF — أكمل البيانات واعتمده من صفحة المصادر."
                : activeContext.edition && activeContext.year
                ? uiLang === "en"
                  ? `Edition: ${activeContext.edition} · Year: ${activeContext.year} (pending source review)`
                  : uiLang === "fr"
                  ? `Édition : ${activeContext.edition} · Année : ${activeContext.year} (en attente)`
                  : `الطبعة: ${activeContext.edition} · السنة: ${activeContext.year} (بانتظار التوثيق)`
                : uiLang === "en"
                ? "Awaiting curriculum PDF upload & verification."
                : uiLang === "fr"
                ? "En attente du manuel PDF et de sa vérification."
                : "بانتظار رفع ملف كتاب المنهج لتوثيقه."}
            </div>
          </div>
        </aside>

        {sidebarOpen && (
          <div
            role="presentation"
            className="sidebar-backdrop"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.45)",
              zIndex: 55,
            }}
          />
        )}

        {/* Main Panel */}
        <div className="app-main">
          <header className="top-bar">
            <div className="top-bar-context-info">
              <button
                type="button"
                className="mobile-menu-btn"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label={uiLang === "en" ? "Open navigation menu" : uiLang === "fr" ? "Ouvrir le menu" : "فتح القائمة الجانبية"}
              >
                {uiLang === "en" ? "☰ Menu" : uiLang === "fr" ? "☰ Menu" : "☰ القائمة"}
              </button>
              {activeContext ? (
                <span>
                  {activeContext.subject} · {activeContext.grade} · {activeContext.country}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={openNewContextModal}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--text-main)",
                    fontWeight: 700,
                    fontSize: "0.9rem",
                    cursor: "pointer",
                    textAlign: "start",
                    padding: 0,
                  }}
                >
                  {uiLang === "en"
                    ? "No context selected — click to set up"
                    : uiLang === "fr"
                    ? "Aucun contexte — cliquez pour configurer"
                    : "لم يتم تحديد سياق بعد — اضغط لإعداد سياقك التعليمي"}
                </button>
              )}
              {activeContext?.missingContextFields && activeContext.missingContextFields.length > 0 && (
                <span
                  className="badge badge-warning"
                  title={
                    uiLang === "en"
                      ? "Unknown fields stay blank instead of being guessed"
                      : "الحقول غير المعروفة تُترك فارغة مع تنبيه بدل تخمينها"
                  }
                >
                  {uiLang === "en"
                    ? `Context notice: missing (${activeContext.missingContextFields.join(", ")})`
                    : uiLang === "fr"
                    ? `Contexte incomplet : (${activeContext.missingContextFields.join(", ")})`
                    : `تنبيه سياق: ينقص (${activeContext.missingContextFields.join("، ")})`}
                </span>
              )}
              {!activeContext && (
                <button
                  type="button"
                  onClick={openNewContextModal}
                  className="badge badge-success"
                  style={{ cursor: "pointer", border: "none" }}
                >
                  {uiLang === "en" ? "+ Setup Context" : uiLang === "fr" ? "+ Configurer" : "+ إعداد سياقك التعليمي"}
                </button>
              )}
            </div>

            <div className="top-bar-user">
              <div className="avatar-circle" title={displayTeacherName || ""}>
                {avatarInitials}
              </div>
              <button type="button" className="btn btn-secondary" onClick={handleLogout} style={{ padding: "5px 9px", fontSize: "0.78rem" }}>
                {uiLang === "en" ? "Sign out" : uiLang === "fr" ? "Déconnexion" : "تسجيل الخروج"}
              </button>
              <span style={{ fontWeight: 600 }}>
                {displayTeacherName || (
                  <button
                    type="button"
                    onClick={activeContext ? undefined : openNewContextModal}
                    style={{
                      background: "none",
                      border: "none",
                      color: activeContext ? "var(--text-muted)" : "var(--primary-green)",
                      cursor: activeContext ? "default" : "pointer",
                      fontWeight: 700,
                    }}
                  >
                    {activeContext
                      ? uiLang === "en"
                        ? "Teacher name unset"
                        : uiLang === "fr"
                        ? "Nom non défini"
                        : "اسم المعلم غير محدد"
                      : uiLang === "en"
                      ? "Enter your name"
                      : uiLang === "fr"
                      ? "Saisir votre nom"
                      : "أدخل اسمك الكريم"}
                  </button>
                )}
              </span>
            </div>
          </header>

          <main className="page-container">
            {contextError && (
              <div className="blocker-banner">
                <span>⛔ {contextError}</span>
                <button type="button" className="btn btn-secondary" onClick={refreshContexts}>
                  {uiLang === "en" ? "↻ Retry" : uiLang === "fr" ? "↻ Réessayer" : "↻ إعادة المحاولة"}
                </button>
              </div>
            )}
            {children}
          </main>

          <footer className="app-footer">
            <span>
              {uiLang === "en"
                ? "Educational Planning Workspace · Source verification required prior to official use"
                : uiLang === "fr"
                ? "Espace de planification · Vérification des sources requise avant usage officiel"
                : "للتخطيط التربوي · توثيق المصدر مطلوب قبل الاستخدام الرسمي"}
            </span>
            <span>
              {contextError
                ? uiLang === "en"
                  ? "Server status: FastAPI unreachable"
                  : uiLang === "fr"
                  ? "Serveur : FastAPI inaccessible"
                  : "حالة الخادم: تعذر الاتصال بـ FastAPI"
                : activeContext
                ? uiLang === "en"
                  ? `Connected · Context isolation active (\u2068${activeContext.subject}\u2069) · AI: ${
                      aiStatus.loading ? "..." : aiStatus.mode === "live" ? "Live" : "Fallback"
                    }`
                  : uiLang === "fr"
                  ? `Connecté · Contexte isolé (\u2068${activeContext.subject}\u2069) · IA : ${
                      aiStatus.loading ? "..." : aiStatus.mode === "live" ? "En ligne" : "Secours"
                    }`
                  : `متصل بخدمة التخطيط · عزل السياقات مفعّل (${activeContext.subject}) · الذكاء الاصطناعي: ${
                      aiStatus.loading ? "..." : aiStatus.mode === "live" ? "متصل حي" : "وضع احتياطي"
                    }`
                : uiLang === "en"
                ? "Awaiting educational context setup"
                : uiLang === "fr"
                ? "En attente de configuration du contexte"
                : "بانتظار إعداد السياق التعليمي"}
            </span>
          </footer>
        </div>
      </div>

      {/* Modal for Creating a Brand New Context */}
      {showModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="إنشاء سياق تعليمي جديد"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "16px",
          }}
        >
          <div className="card" style={{ maxWidth: "580px", width: "100%", maxHeight: "90vh", overflowY: "auto" }}>
            <h2 style={{ marginBottom: "6px", fontSize: "1.25rem", fontWeight: 800 }}>
              {contexts.length === 0 ? "مرحبًا بك في مساعد المدرس — إعداد أول استخدام" : "إضافة سياق تعليمي جديد"}
            </h2>
            <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
              {contexts.length === 0
                ? "أدخل اسمك أولاً وأنشئ سياقك التعليمي للبدء فوراً. لا توجد أي مادة أو صف مفروضين مسبقًا."
                : "أنشئ سياقًا تعليميًا معزولاً لأي مادة ومنهج وصف وبلد مع حفظ إعداداته."}
            </p>
            {modalError && (
              <div className="blocker-banner">
                <span>⛔ {modalError}</span>
              </div>
            )}
            <form onSubmit={handleCreateContext}>
              <div style={{ backgroundColor: "#fbfcfb", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", marginBottom: "14px" }}>
                <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "8px", color: "var(--primary-green)" }}>
                  1. بيانات المعلم والمدرسة
                </div>
                <div className="stats-grid-3" style={{ marginBottom: 0 }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">اسم المعلم / المعلمة *</label>
                    <input
                      className="form-input"
                      placeholder="مثال: أ. محمد أحمد / د. سارة علي"
                      value={newCtxForm.teacherName}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, teacherName: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">المدرسة (اختياري)</label>
                    <input
                      className="form-input"
                      placeholder="مثال: ثانوية الأمل"
                      value={newCtxForm.schoolName}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, schoolName: e.target.value })}
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">الشعبة (اختياري)</label>
                    <input
                      className="form-input"
                      placeholder="مثال: الشعبة أ"
                      value={newCtxForm.sectionName}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, sectionName: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div style={{ backgroundColor: "#fbfcfb", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-color)", marginBottom: "14px" }}>
                <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "8px", color: "var(--primary-green)" }}>
                  2. السياق التعليمي (أدخل بيانات مادتك وصفك)
                </div>
                <div className="equal-split-grid">
                  <div className="form-group">
                    <label className="form-label">المادة (subject) *</label>
                    <input
                      className="form-input"
                      placeholder="مثال: العلوم، التاريخ، الفيزياء، اللغة الإنجليزية..."
                      value={newCtxForm.subject}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, subject: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">الصف / المرحلة (grade) *</label>
                    <input
                      className="form-input"
                      placeholder="مثال: الثالث المتوسط، الأول الثانوي، السادس الابتدائي..."
                      value={newCtxForm.grade}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, grade: e.target.value })}
                      required
                    />
                  </div>
                </div>
                <div className="equal-split-grid">
                  <div className="form-group">
                    <label className="form-label">البلد (country) *</label>
                    <input
                      className="form-input"
                      placeholder="مثال: العراق، السعودية، مصر، الأردن..."
                      value={newCtxForm.country}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, country: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">اسم المنهج (curriculumName)</label>
                    <input
                      className="form-input"
                      placeholder="مثال: المنهج الوطني، المقررات الحديثة..."
                      value={newCtxForm.curriculumName}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, curriculumName: e.target.value })}
                    />
                  </div>
                </div>
                <div className="stats-grid-4" style={{ marginBottom: 0 }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">لغة السياق</label>
                    <select
                      className="form-select"
                      value={newCtxForm.language}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, language: e.target.value })}
                    >
                      <option value="ar">العربية (RTL)</option>
                      <option value="en">English (LTR)</option>
                      <option value="ku">Kurdî (RTL)</option>
                      <option value="fr">Français (LTR)</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">زمن الحصة (د)</label>
                    <input
                      type="number"
                      min={10}
                      max={180}
                      className="form-input"
                      value={newCtxForm.defaultPeriodMinutes}
                      onChange={(e) =>
                        setNewCtxForm({ ...newCtxForm, defaultPeriodMinutes: Math.max(5, Number(e.target.value) || 45) })
                      }
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">السنة (اختياري)</label>
                    <input
                      className="form-input"
                      placeholder="تُترك فارغة"
                      value={newCtxForm.year}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, year: e.target.value })}
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">الطبعة (اختياري)</label>
                    <input
                      className="form-input"
                      placeholder="تُترك فارغة"
                      value={newCtxForm.edition}
                      onChange={(e) => setNewCtxForm({ ...newCtxForm, edition: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "16px" }}>
                {contexts.length > 0 && (
                  <button type="button" className="btn btn-secondary" onClick={closeNewContextModal} disabled={creatingContext}>
                    إلغاء
                  </button>
                )}
                <button type="submit" className="btn btn-primary" disabled={creatingContext}>
                  {creatingContext
                    ? "جارٍ الحفظ..."
                    : contexts.length === 0
                    ? "حفظ وبدء التخطيط ←"
                    : "حفظ وتفعيل السياق"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </TeacherAppContext.Provider>
  );
}
