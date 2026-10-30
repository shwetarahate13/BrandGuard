import React, { useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api";
import { User } from "./types";
import { Navbar } from "./components/Navbar";
import { OnboardingTips } from "./components/OnboardingTips";
import { ToastProvider } from "./components/Toast";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { NewSubmission } from "./pages/NewSubmission";
import { ReviewScreen } from "./pages/ReviewScreen";
import { ApprovalView } from "./pages/ApprovalView";
import { AdminSources } from "./pages/AdminSources";
import { Insights } from "./pages/Insights";
import { GuidelineHealth } from "./pages/GuidelineHealth";
import { Limitations } from "./pages/Limitations";
import { CertificateLibrary } from "./pages/CertificateLibrary";
import { VerifyCertificate } from "./pages/VerifyCertificate";
import { IntegrityCheck } from "./pages/IntegrityCheck";
import { applyDarkMode, readDarkMode, saveDarkMode } from "./theme";
import { hasSeenOnboarding, markOnboardingSeen } from "./onboarding";

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [llmMode, setLlmMode] = useState("mock/offline");
  const [demoMode, setDemoMode] = useState(false);
  const [retrieval, setRetrieval] = useState({ state: "warming_up", engine: "HashingVectorizer fallback", detail: "Loading retrieval status." });
  const [demoSwitchError, setDemoSwitchError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(() => readDarkMode());
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const refreshMode = async () => {
      try {
        const mode = await api.getSystemMode();
        if (!active) return;
        setLlmMode(mode.llm_mode);
        setDemoMode(mode.demo_mode);
        setRetrieval(mode.retrieval);
        if (["warming_up", "reindexing", "not_started"].includes(mode.retrieval.state)) {
          timer = window.setTimeout(refreshMode, 1200);
        }
      } catch {
        if (!active) return;
        setLlmMode("unavailable");
        timer = window.setTimeout(refreshMode, 3000);
      }
    };
    void refreshMode();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    applyDarkMode(darkMode);
    saveDarkMode(darkMode);
  }, [darkMode]);

  useEffect(() => {
    setOnboardingOpen(Boolean(user && !hasSeenOnboarding(user.id, user.role)));
  }, [user]);

  // Sync browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (path: string) => {
    window.history.pushState({}, "", path);
    setCurrentPath(new URL(path, window.location.origin).pathname);
    window.scrollTo(0, 0);
  };

  // Check auth and system status
  useEffect(() => {
    const init = async () => {
      const token = getToken();
      if (token) {
        try {
          const me = await api.getMe();
          setUser(me);
        } catch (err) {
          clearToken();
          setUser(null);
        }
      }
      setLoading(false);
    };
    init();
  }, []);

  const handleLogout = () => {
    clearToken();
    setUser(null);
    setOnboardingOpen(false);
    navigate("/login");
  };

  const handleLoginSuccess = (loggedInUser: User) => {
    setUser(loggedInUser);
    navigate("/");
  };

  const closeOnboarding = () => {
    if (user) markOnboardingSeen(user.id, user.role);
    setOnboardingOpen(false);
  };

  const handleDemoRoleSwitch = async (role: User["role"]) => {
    setDemoSwitchError(null);
    try {
      const session = await api.demoLogin(role);
      setToken(session.access_token);
      const switchedUser = await api.getMe();
      setUser(switchedUser);
      navigate("/");
    } catch (err) {
      setDemoSwitchError(err instanceof Error ? err.message : "Unable to switch demo role.");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center text-xs font-semibold text-stone-500 animate-pulse">
        Initializing BrandGuard Governance Platform...
      </div>
    );
  }

  // Routing logic with strict Role-based UI mirroring
  const renderLogin = () => <Login onLoginSuccess={handleLoginSuccess} demoMode={demoMode} />;
  let content = null;
  if (currentPath === "/verify") {
    content = <VerifyCertificate />;
  } else if (!user && currentPath !== "/limitations") {
    content = renderLogin();
  } else if (currentPath === "/login") {
    content = renderLogin();
  } else if (currentPath === "/new") {
    // Only creators can create submissions.
    if (user && user.role !== "creator") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <NewSubmission navigate={navigate} /> : renderLogin();
    }
  } else if (currentPath.startsWith("/review/")) {
    const id = currentPath.replace("/review/", "");
    content = user ? <ReviewScreen submissionId={id} user={user} navigate={navigate} /> : renderLogin();
  } else if (currentPath.startsWith("/approval/")) {
    const id = currentPath.replace("/approval/", "");
    content = user && (user.role === "manager" || user.role === "reviewer")
      ? <ApprovalView submissionId={id} user={user} navigate={navigate} />
      : user ? <Dashboard user={user} navigate={navigate} /> : renderLogin();
  } else if (currentPath === "/sources") {
    // Creators cannot manage or view sources registry
    if (user && user.role === "creator") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <AdminSources canManage={user.role === "admin"} canViewFactImpacts={user.role === "manager" || user.role === "admin"} navigate={navigate} /> : renderLogin();
    }
  } else if (currentPath === "/insights") {
    // Only managers and admins can view organization-wide insights.
    if (user && user.role !== "manager" && user.role !== "admin") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <Insights /> : renderLogin();
    }
  } else if (currentPath === "/dashboard/guideline-health") {
    // Only Managers and Admins can view Guideline Health
    if (user && (user.role === "manager" || user.role === "admin")) {
      content = <GuidelineHealth />;
    } else {
      content = user ? <Dashboard user={user} navigate={navigate} /> : renderLogin();
    }
  } else if (currentPath === "/limitations") {
    content = <Limitations navigate={navigate} />;
  } else if (currentPath === "/certificates") {
    content = user ? <CertificateLibrary user={user} navigate={navigate} /> : renderLogin();
  } else if (currentPath === "/admin/integrity") {
    content = user?.role === "admin" ? <IntegrityCheck /> : user ? <Dashboard user={user} navigate={navigate} /> : renderLogin();
  } else {
    content = user ? <Dashboard user={user} navigate={navigate} /> : renderLogin();
  }

  return (
    <ToastProvider>
        <Navbar
          user={user}
          llmMode={llmMode}
          retrievalState={retrieval.state}
          retrievalEngine={retrieval.engine}
          retrievalDetail={retrieval.detail}
          demoMode={demoMode}
          onDemoRoleSwitch={handleDemoRoleSwitch}
          onLogout={handleLogout}
          darkMode={darkMode}
          onToggleDarkMode={() => setDarkMode((enabled) => !enabled)}
          onShowOnboarding={() => setOnboardingOpen(true)}
          currentPath={currentPath}
          navigate={navigate}
        >
          <a className="app-skip-link" href="#main-content">Skip to main content</a>
          {demoSwitchError && <div role="alert" className="app-global-error">{demoSwitchError}</div>}
          <main id="main-content" className="app-main" tabIndex={-1}>{content}</main>

          {user && onboardingOpen && <OnboardingTips role={user.role} onClose={closeOnboarding} />}

          <footer className="app-footer">
            <a href="/" onClick={(event) => { event.preventDefault(); navigate("/"); }} className="app-footer__brand">BrandGuard</a>
            <div className="app-footer__links">
              <a href="/limitations" onClick={(event) => { event.preventDefault(); navigate("/limitations"); }}>Known limitations</a>
              <a href="/verify" onClick={(event) => { event.preventDefault(); navigate("/verify"); }}>Verify certificate</a>
              <span>AI suggests. People decide.</span>
            </div>
          </footer>
        </Navbar>
    </ToastProvider>
  );
};
