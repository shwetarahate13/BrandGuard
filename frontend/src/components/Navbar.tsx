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
} from "lucide-react";
import { User } from "../types";
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

  const navLinks = [
    { label: "Dashboard", path: "/", icon: FileText, roles: ["creator", "manager", "reviewer", "admin"] },
    { label: "New Check", path: "/new", icon: PlusCircle, roles: ["creator", "manager", "admin"] },
    { label: "Approved Sources", path: "/sources", icon: Database, roles: ["manager", "admin"] },
    { label: "Insights", path: "/insights", icon: BarChart3, roles: ["creator", "manager", "reviewer", "admin"] },
    { label: "Limitations", path: "/limitations", icon: HelpCircle, roles: ["creator", "manager", "reviewer", "admin"] },
  ];

  return (
    <>
      <header className="bg-white border-b border-stone-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-8">
              <button
                onClick={() => navigate("/")}
                className="flex items-center gap-2.5 text-left group"
              >
                <div className="w-9 h-9 rounded-lg bg-stone-900 text-amber-500 flex items-center justify-center font-bold shadow group-hover:scale-105 transition-transform">
                  <Shield className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <span className="font-bold text-lg text-stone-900 tracking-tight">BrandGuard</span>
                  <span className="ml-1 text-[10px] font-semibold tracking-wider text-amber-700 uppercase bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                    Round 2
                  </span>
                </div>
              </button>

              {/* Navigation links */}
              {user && (
                <nav className="hidden md:flex items-center gap-1">
                  {navLinks
                    .filter((link) => link.roles.includes(user.role))
                    .map((link) => {
                      const Icon = link.icon;
                      const active = currentPath === link.path;
                      return (
                        <button
                          key={link.path}
                          onClick={() => navigate(link.path)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            active
                              ? "bg-stone-900 text-white"
                              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
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

            {/* Right controls: LLM Mode, User Role, Logout */}
            <div className="flex items-center gap-3">
              {/* LLM Mode pill */}
              <button
                onClick={() => setModalOpen(true)}
                title="Review Engine Status & Transparency Notice"
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-stone-100 border border-stone-300 text-stone-700 hover:bg-stone-200 transition-colors"
              >
                <Cpu className={`w-3 h-3 ${llmMode.includes("mock") ? "text-amber-600" : "text-emerald-600"}`} />
                <span className="truncate max-w-[140px] sm:max-w-none">
                  {llmMode}
                </span>
              </button>

              {user ? (
                <div className="flex items-center gap-3 border-l border-stone-200 pl-3">
                  <div className="text-right hidden sm:block">
                    <p className="text-xs font-semibold text-stone-900 leading-tight">{user.name}</p>
                    <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.2 rounded bg-stone-100 text-stone-600 border border-stone-200">
                      {user.role}
                    </span>
                  </div>

                  <button
                    onClick={onLogout}
                    title="Sign Out"
                    className="p-2 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-lg transition-colors"
                    aria-label="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => navigate("/login")}
                  className="px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium hover:bg-stone-800"
                >
                  Sign In
                </button>
              )}
            </div>
          </div>
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
