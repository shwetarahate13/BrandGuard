import React, { useEffect, useState } from "react";
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
  Bell,
  CheckCheck,
  X as CloseIcon,
  LockKeyhole,
} from "lucide-react";
import { User, UserRole } from "../types";
import { Notification } from "../types";
import { api } from "../api";
import { TransparencyModal } from "./TransparencyModal";

interface NavbarProps {
  user: User | null;
  llmMode: string;
  demoMode: boolean;
  onDemoRoleSwitch: (role: UserRole) => void;
  onLogout: () => void;
  currentPath: string;
  navigate: (path: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  llmMode,
  demoMode,
  onDemoRoleSwitch,
  onLogout,
  currentPath,
  navigate,
}) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordChanging, setPasswordChanging] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordChanged, setPasswordChanged] = useState(false);

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setNotificationsOpen(false);
      return;
    }
    let active = true;
    const loadNotifications = async () => {
      try {
        const items = await api.getNotifications({ limit: 100 });
        if (active) {
          setNotifications(items);
          setNotificationError(null);
        }
      } catch (error) {
        if (active) setNotificationError(error instanceof Error ? error.message : "Unable to load notifications.");
      }
    };
    void loadNotifications();
    const refresh = window.setInterval(loadNotifications, 45000);
    return () => {
      active = false;
      window.clearInterval(refresh);
    };
  }, [user?.id]);

  const unreadCount = notifications.filter((item) => !item.is_read).length;

  const markAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications((items) => items.map((item) => ({ ...item, is_read: true })));
      setNotificationError(null);
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : "Unable to update notifications.");
    }
  };

  const openNotification = async (notification: Notification) => {
    if (!notification.is_read) {
      try {
        await api.markNotificationRead(notification.id);
        setNotifications((items) => items.map((item) => item.id === notification.id ? { ...item, is_read: true } : item));
      } catch (error) {
        setNotificationError(error instanceof Error ? error.message : "Unable to update notification.");
        return;
      }
    }
    setNotificationsOpen(false);
    if (notification.submission_id) {
      navigate(notification.kind === "review_assignment"
        ? `/approval/${notification.submission_id}`
        : `/review/${notification.submission_id}`);
    }
  };

  const closePasswordModal = () => {
    setPasswordModalOpen(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError(null);
    setPasswordChanged(false);
  };

  const submitPasswordChange = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError(null);
    if (newPassword !== confirmPassword) {
      setPasswordError("The new passwords do not match.");
      return;
    }
    setPasswordChanging(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordChanged(true);
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "Password change failed.");
    } finally {
      setPasswordChanging(false);
    }
  };

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
              {user && <div className="relative">
                <button
                  type="button"
                  aria-label={unreadCount ? `Notifications, ${unreadCount} unread` : "Notifications"}
                  aria-expanded={notificationsOpen}
                  onClick={() => setNotificationsOpen((open) => !open)}
                  className={`relative p-2 rounded-lg transition-colors ${notificationsOpen ? "bg-stone-100 text-stone-900" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"}`}
                >
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-4 h-4 px-1 rounded-full bg-rose-600 text-white text-[9px] font-bold leading-4 text-center">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>}
                </button>
                {notificationsOpen && <section
                  role="region"
                  aria-label="Notifications"
                  className="absolute right-0 top-full mt-2 w-80 max-w-[calc(100vw-1rem)] overflow-hidden rounded-xl border border-stone-200 bg-white shadow-xl z-50"
                >
                  <div className="flex items-center justify-between gap-3 border-b border-stone-200 px-4 py-3">
                    <div>
                      <h2 className="text-sm font-bold text-stone-900">Notifications</h2>
                      <p className="text-[10px] text-stone-500">Assignments and workflow decisions</p>
                    </div>
                    <div className="flex items-center gap-1">
                      {unreadCount > 0 && <button
                        type="button"
                        onClick={markAllRead}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-semibold text-stone-600 hover:bg-stone-100"
                      >
                        <CheckCheck className="h-3.5 w-3.5" /> Mark all read
                      </button>}
                      <button
                        type="button"
                        aria-label="Close notifications"
                        onClick={() => setNotificationsOpen(false)}
                        className="rounded-md p-1.5 text-stone-500 hover:bg-stone-100"
                      >
                        <CloseIcon className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  {notificationError && <p role="alert" className="px-4 py-2 text-xs text-rose-700 bg-rose-50">{notificationError}</p>}
                  <div className="max-h-96 overflow-y-auto">
                    {notifications.length === 0 ? <p className="px-4 py-8 text-center text-xs text-stone-500">No notifications yet.</p> : notifications.map((notification) => (
                      <button
                        type="button"
                        key={notification.id}
                        onClick={() => void openNotification(notification)}
                        className={`block w-full border-b border-stone-100 px-4 py-3 text-left transition-colors hover:bg-stone-50 ${notification.is_read ? "bg-white" : "bg-amber-50/70"}`}
                      >
                        <span className="flex items-start gap-2">
                          {!notification.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-600" />}
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-bold text-stone-900">{notification.title}</span>
                            <span className="mt-1 block text-[11px] leading-relaxed text-stone-600">{notification.message}</span>
                            <span className="mt-1 block text-[10px] text-stone-400">{new Date(notification.created_at).toLocaleString()}</span>
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                </section>}
              </div>}
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
                  {demoMode && <label className="hidden lg:flex items-center gap-2 text-[10px] font-semibold text-stone-600">
                    <span>Demo role</span>
                    <select
                      aria-label="Switch demo role"
                      value={user.role}
                      onChange={(event) => onDemoRoleSwitch(event.target.value as UserRole)}
                      className="rounded-lg border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-bold text-stone-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-700"
                    >
                      <option value="creator">Creator</option>
                      <option value="manager">Manager</option>
                      <option value="reviewer">Reviewer</option>
                      <option value="admin">Admin</option>
                    </select>
                  </label>}
                  <div className="text-right hidden sm:block">
                    <p className="text-xs font-bold text-stone-900 leading-tight">{user.name}</p>
                    <span className="text-[10px] uppercase font-extrabold tracking-wider px-1.5 py-0.2 rounded bg-stone-200 text-stone-800 border border-stone-300">
                      {user.role}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => { setPasswordModalOpen(true); setPasswordError(null); setPasswordChanged(false); }}
                    title="Change Password"
                    aria-label="Change password"
                    className="inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                  >
                    <LockKeyhole className="h-4 w-4" />
                    <span className="hidden xl:inline">Password</span>
                  </button>

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
            {demoMode && <label className="flex items-center justify-between gap-3 px-3 py-2 text-sm font-semibold text-stone-700">
              <span>Switch demo role</span>
              <select
                aria-label="Switch demo role"
                value={user.role}
                onChange={(event) => onDemoRoleSwitch(event.target.value as UserRole)}
                className="rounded-lg border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-bold text-stone-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-700"
              >
                <option value="creator">Creator</option>
                <option value="manager">Manager</option>
                <option value="reviewer">Reviewer</option>
                <option value="admin">Admin</option>
              </select>
            </label>}
          </nav>}
        </div>
      </header>

      <TransparencyModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        llmMode={llmMode}
      />

      {passwordModalOpen && user && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !passwordChanging) closePasswordModal();
        }}>
          <section role="dialog" aria-modal="true" aria-labelledby="password-change-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            {!passwordChanged ? (
              <>
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div>
                    <h2 id="password-change-title" className="text-lg font-bold text-stone-900">Change password</h2>
                    <p className="mt-1 text-xs text-stone-500">Verify your current password, then choose a new one.</p>
                  </div>
                  <button type="button" aria-label="Close password dialog" onClick={closePasswordModal} disabled={passwordChanging} className="rounded-lg p-1.5 text-stone-500 hover:bg-stone-100 disabled:opacity-50">
                    <CloseIcon className="h-4 w-4" />
                  </button>
                </div>
                {passwordError && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">{passwordError}</p>}
                <form onSubmit={submitPasswordChange} className="space-y-3">
                  <label className="block text-xs font-semibold text-stone-700">Current password
                    <input type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm" />
                  </label>
                  <label className="block text-xs font-semibold text-stone-700">New password
                    <input type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm" />
                  </label>
                  <label className="block text-xs font-semibold text-stone-700">Confirm new password
                    <input type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm" />
                  </label>
                  <p className="text-[11px] text-stone-500">At least 12 characters and no more than 72 UTF-8 bytes.</p>
                  <div className="flex justify-end gap-2 pt-2">
                    <button type="button" onClick={closePasswordModal} disabled={passwordChanging} className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-50">Cancel</button>
                    <button type="submit" disabled={passwordChanging} className="rounded-lg bg-stone-900 px-3 py-2 text-xs font-semibold text-white hover:bg-stone-800 disabled:opacity-50">{passwordChanging ? "Updating…" : "Change password"}</button>
                  </div>
                </form>
              </>
            ) : (
              <div className="py-3 text-center">
                <h2 id="password-change-title" className="text-lg font-bold text-emerald-800">Password changed</h2>
                <p className="mt-2 text-sm text-stone-600">Your new password is ready to use the next time you sign in.</p>
                <button type="button" onClick={closePasswordModal} className="mt-5 rounded-lg bg-stone-900 px-4 py-2 text-xs font-semibold text-white">Done</button>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
};
