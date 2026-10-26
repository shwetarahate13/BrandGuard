import React, { useState } from "react";
import {
  Shield,
  FileText,
  PlusCircle,
  Database,
  BarChart3,
  HelpCircle,
  LogOut,
  Cpu,
  Flame,
  Menu,
  X,
} from "lucide-react";
import { User, UserRole } from "../types";
import { TransparencyModal } from "./TransparencyModal";

interface NavbarProps {
  user: User | null;
  llmMode: string;
  onLogout: () => void;
  currentPath: string;
  navigate: (path: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  llmMode,
  onLogout,
  currentPath,
  navigate,
}) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const getNavLinks = (role: UserRole) => {
    switch (role) {
      case "creator":
        return [
          { label: "My Work", path: "/", icon: FileText },
          { label: "New Content Check", path: "/new", icon: PlusCircle },
          { label: "Limitations", path: "/limitations", icon: HelpCircle },
        ];
      case "manager":
        return [
          { label: "Command Center", path: "/", icon: FileText },
          { label: "Guideline Health", path: "/dashboard/guideline-health", icon: Flame },
          { label: "Org Insights", path: "/insights", icon: BarChart3 },
          { label: "Approved Sources", path: "/sources", icon: Database },
          { label: "Limitations", path: "/limitations", icon: HelpCircle },
        ];
      case "reviewer":
        return [
          { label: "Compliance Desk", path: "/", icon: Shield },
          { label: "Approved Sources (Read-Only)", path: "/sources", icon: Database },
          { label: "Limitations", path: "/limitations", icon: HelpCircle },
        ];
      case "admin":
        return [
          { label: "Admin Console", path: "/", icon: FileText },
          { label: "Approved Sources", path: "/sources", icon: Database },
          { label: "Guideline Health", path: "/dashboard/guideline-health", icon: Flame },
          { label: "Org Insights", path: "/insights", icon: BarChart3 },
          { label: "Limitations", path: "/limitations", icon: HelpCircle },
        ];
      default:
        return [{ label: "Dashboard", path: "/", icon: FileText }];
    }
  };

  const activeLinks = user ? getNavLinks(user.role) : [];

  return (
    <>
      <header className="bg-white border-b border-stone-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-6">
              <button
                onClick={() => navigate("/")}
                className="flex items-center gap-2.5 text-left group"
              >
                <div className="w-9 h-9 rounded-lg bg-stone-900 text-amber-500 flex items-center justify-center font-bold shadow group-hover:scale-105 transition-transform">
                  <Shield className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <span className="font-bold text-lg text-stone-900 tracking-tight">BrandGuard</span>
                  <span className="ml-1 text-[10px] font-semibold tracking-wider text-amber-800 uppercase bg-amber-50 px-1.5 py-0.5 rounded border border-amber-300">
                    Governance
                  </span>
                </div>
              </button>

              {/* Navigation links based on role */}
              {user && (
                <nav className="hidden md:flex items-center gap-1">
                  {activeLinks.map((link) => {
                    const Icon = link.icon;
                    const active = currentPath === link.path;
                    return (
                      <button
                        key={link.path}
                        onClick={() => { navigate(link.path); setMobileOpen(false); }}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                          active
                            ? "bg-stone-900 text-white shadow-sm"
                            : "text-stone-700 hover:text-stone-950 hover:bg-stone-100"
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {link.label}
                      </button>
                    );
                  })}
                </nav>
              )}
            </div>

              {/* Right controls: LLM mode, user role, and logout */}
            <div className="flex items-center gap-3">
              {user && <button
                type="button"
                className="md:hidden p-2 rounded-lg text-stone-700 hover:bg-stone-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-stone-700"
                aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
                aria-expanded={mobileOpen}
                onClick={() => setMobileOpen((open) => !open)}
              >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>}
              {/* LLM Mode pill */}
              <button
                onClick={() => setModalOpen(true)}
                title="Review Engine Status & Transparency Notice"
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-stone-100 border border-stone-300 text-stone-800 hover:bg-stone-200 transition-colors"
              >
                <Cpu className={`w-3 h-3 ${llmMode.includes("mock") ? "text-amber-600" : "text-emerald-600"}`} />
                <span className="truncate max-w-[120px] sm:max-w-none font-semibold">
                  {llmMode}
                </span>
              </button>

              {user ? (
                <div className="flex items-center gap-3 border-l border-stone-200 pl-3">
                  <div className="text-right hidden sm:block">
                    <p className="text-xs font-bold text-stone-900 leading-tight">{user.name}</p>
                    <span className="text-[10px] uppercase font-extrabold tracking-wider px-1.5 py-0.2 rounded bg-stone-200 text-stone-800 border border-stone-300">
                      {user.role}
                    </span>
                  </div>

                  <button
                    onClick={onLogout}
                    title="Sign Out"
                    className="p-2 text-stone-500 hover:text-stone-900 hover:bg-stone-100 rounded-lg transition-colors"
                    aria-label="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => navigate("/login")}
                  className="px-3.5 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-bold hover:bg-stone-800"
                >
                  Sign In
                </button>
              )}
            </div>
          </div>
          {user && mobileOpen && <nav aria-label="Mobile navigation" className="md:hidden border-t border-stone-200 py-2 grid grid-cols-1 gap-1">
            {activeLinks.map((link) => {
              const Icon = link.icon;
              const active = currentPath === link.path;
              return <button
                key={link.path}
                onClick={() => { navigate(link.path); setMobileOpen(false); }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold text-left ${active ? "bg-stone-900 text-white" : "text-stone-700 hover:bg-stone-100"}`}
              >
                <Icon className="w-4 h-4" />{link.label}
              </button>;
            })}
          </nav>}
        </div>
      </header>

      <TransparencyModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        llmMode={llmMode}
      />
    </>
  );
};
