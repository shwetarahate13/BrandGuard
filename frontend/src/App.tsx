import React, { useEffect, useState } from "react";
import { api, clearToken, getToken, setColdStartListener } from "./api";
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

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [llmMode, setLlmMode] = useState("mock/offline");
  const [loading, setLoading] = useState(true);
  const [isWaking, setIsWaking] = useState(false);
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  // Setup cold start listener
  useEffect(() => {
    api.getSystemMode().then((mode) => setLlmMode(mode.llm_mode)).catch(() => setLlmMode("unavailable"));
  }, []);

  useEffect(() => {
    setColdStartListener((waking) => setIsWaking(waking));
  }, []);

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

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center text-xs font-semibold text-stone-500 animate-pulse">
        Initializing BrandGuard Governance Platform...
      </div>
    );
  }

  // Routing logic with strict Role-based UI mirroring
  let content = null;
  if (!user && currentPath !== "/limitations") {
    content = <Login onLoginSuccess={handleLoginSuccess} />;
  } else if (currentPath === "/login") {
    content = <Login onLoginSuccess={handleLoginSuccess} />;
  } else if (currentPath === "/new") {
    // Only creators can create submissions.
    if (user && user.role !== "creator") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <NewSubmission navigate={navigate} /> : <Login onLoginSuccess={handleLoginSuccess} />;
    }
  } else if (currentPath.startsWith("/review/")) {
    const id = currentPath.replace("/review/", "");
    content = user ? <ReviewScreen submissionId={id} user={user} navigate={navigate} /> : <Login onLoginSuccess={handleLoginSuccess} />;
  } else if (currentPath.startsWith("/approval/")) {
    const id = currentPath.replace("/approval/", "");
    content = user && (user.role === "manager" || user.role === "reviewer")
      ? <ApprovalView submissionId={id} user={user} navigate={navigate} />
      : user ? <Dashboard user={user} navigate={navigate} /> : <Login onLoginSuccess={handleLoginSuccess} />;
  } else if (currentPath === "/sources") {
    // Creators cannot manage or view sources registry
    if (user && user.role === "creator") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <AdminSources canManage={user.role === "admin"} /> : <Login onLoginSuccess={handleLoginSuccess} />;
    }
  } else if (currentPath === "/insights") {
    // Only managers and admins can view organization-wide insights.
    if (user && user.role !== "manager" && user.role !== "admin") {
      content = <Dashboard user={user} navigate={navigate} />;
    } else {
      content = user ? <Insights /> : <Login onLoginSuccess={handleLoginSuccess} />;
    }
  } else if (currentPath === "/dashboard/guideline-health") {
    // Only Managers and Admins can view Guideline Health
    if (user && (user.role === "manager" || user.role === "admin")) {
      content = <GuidelineHealth />;
    } else {
      content = user ? <Dashboard user={user} navigate={navigate} /> : <Login onLoginSuccess={handleLoginSuccess} />;
    }
  } else if (currentPath === "/limitations") {
    content = <Limitations navigate={navigate} />;
  } else {
    content = user ? <Dashboard user={user} navigate={navigate} /> : <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <ToastProvider>
      <div className="min-h-screen flex flex-col bg-stone-50 text-stone-900 font-sans">
        <ColdStartBanner isWaking={isWaking} />

        <Navbar
          user={user}
          llmMode={llmMode}
          onLogout={handleLogout}
          currentPath={currentPath}
          navigate={navigate}
        />

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
