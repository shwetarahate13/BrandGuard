import React, { useEffect, useState } from "react";
import { api, clearToken, getToken, setColdStartListener, setToken } from "./api";
import { User } from "./types";
import { Navbar } from "./components/Navbar";
import { ColdStartBanner } from "./components/ColdStartBanner";
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
import { applyDarkMode, readDarkMode, saveDarkMode } from "./theme";

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [llmMode, setLlmMode] = useState("mock/offline");
  const [demoMode, setDemoMode] = useState(false);
  const [demoSwitchError, setDemoSwitchError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isWaking, setIsWaking] = useState(false);
  const [darkMode, setDarkMode] = useState(() => readDarkMode());
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  // Setup cold start listener
  useEffect(() => {
    api.getSystemMode().then((mode) => {
      setLlmMode(mode.llm_mode);
      setDemoMode(mode.demo_mode);
    }).catch(() => setLlmMode("unavailable"));
  }, []);

  useEffect(() => {
    setColdStartListener((waking) => setIsWaking(waking));
  }, []);

  useEffect(() => {
    applyDarkMode(darkMode);
    saveDarkMode(darkMode);
  }, [darkMode]);

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
    setCurrentPath(path);
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
    navigate("/login");
  };

  const handleLoginSuccess = (loggedInUser: User) => {
    setUser(loggedInUser);
    navigate("/");
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
  if (!user && currentPath !== "/limitations") {
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
      content = user ? <AdminSources canManage={user.role === "admin"} /> : renderLogin();
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
  } else {
    content = user ? <Dashboard user={user} navigate={navigate} /> : renderLogin();
  }

  return (
    <ToastProvider>
      <div className="min-h-screen flex flex-col bg-stone-50 text-stone-900 font-sans">
        <ColdStartBanner isWaking={isWaking} />

        <Navbar
          user={user}
          llmMode={llmMode}
          demoMode={demoMode}
          onDemoRoleSwitch={handleDemoRoleSwitch}
          onLogout={handleLogout}
          darkMode={darkMode}
          onToggleDarkMode={() => setDarkMode((enabled) => !enabled)}
          currentPath={currentPath}
          navigate={navigate}
        />

        {demoSwitchError && <div role="alert" className="mx-auto mt-3 w-[min(96%,48rem)] rounded-lg border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-900">{demoSwitchError}</div>}
        <main className="flex-1">{content}</main>

        {/* Footer */}
        <footer className="bg-white border-t border-stone-200 py-6 mt-12 text-xs text-stone-500">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="font-bold text-stone-900">BrandGuard</span>
              <span>•</span>
              <span>Team Nexora (Shweta Rahate, Janvi Thakre)</span>
            </div>

            <div className="flex items-center gap-6">
              <button
                onClick={() => navigate("/limitations")}
                className="hover:text-stone-900 underline underline-offset-4"
              >
                Known Limitations & Disclosures
              </button>
              <span>Pre-publication governance • AI suggests, humans decide</span>
            </div>
          </div>
        </footer>
      </div>
    </ToastProvider>
  );
};
