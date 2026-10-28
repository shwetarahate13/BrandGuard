import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  BadgeCheck,
  BarChart3,
  Bell,
  CheckCheck,
  ChevronRight,
  Cpu,
  Database,
  FileText,
  Fingerprint,
  Flame,
  HelpCircle,
  LockKeyhole,
  LogOut,
  Menu,
  Moon,
  RotateCcw,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import { User, UserRole } from "../types";
import { Notification } from "../types";
import { api } from "../api";
import { TransparencyModal } from "./TransparencyModal";
import { Badge, Button, Input, Modal, Select } from "./ui";

interface NavbarProps {
  user: User | null;
  llmMode: string;
  retrievalState: string;
  retrievalEngine: string;
  retrievalDetail: string;
  demoMode: boolean;
  onDemoRoleSwitch: (role: UserRole) => void;
  onLogout: () => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onShowOnboarding: () => void;
  currentPath: string;
  navigate: (path: string) => void;
  children: React.ReactNode;
}

type NavLink = { label: string; path: string; icon: typeof FileText };

export const Navbar: React.FC<NavbarProps> = ({
  user,
  llmMode,
  retrievalState,
  retrievalEngine,
  retrievalDetail,
  demoMode,
  onDemoRoleSwitch,
  onLogout,
  darkMode,
  onToggleDarkMode,
  onShowOnboarding,
  currentPath,
  navigate,
  children,
}) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationActionId, setNotificationActionId] = useState<string | null>(null);
  const [markingAllRead, setMarkingAllRead] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordChanging, setPasswordChanging] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordChanged, setPasswordChanged] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const notificationButtonRef = useRef<HTMLButtonElement>(null);
  const profileButtonRef = useRef<HTMLButtonElement>(null);
  const wasMobileOpen = useRef(false);
  const notificationRequest = useRef(0);

  const refreshNotifications = useCallback(async (showLoading = true) => {
    if (!user) return;
    const requestId = ++notificationRequest.current;
    if (showLoading) setNotificationsLoading(true);
    try {
      const items = await api.getNotifications({ limit: 100 });
      if (requestId === notificationRequest.current) {
        setNotifications(items);
        setNotificationError(null);
      }
    } catch (error) {
      if (requestId === notificationRequest.current) setNotificationError(error instanceof Error ? error.message : "Unable to load notifications.");
    } finally {
      if (showLoading && requestId === notificationRequest.current) setNotificationsLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setNotificationsOpen(false);
      setNotificationsLoading(false);
      return;
    }
    void refreshNotifications();
    const refresh = window.setInterval(() => void refreshNotifications(false), 45000);
    return () => {
      notificationRequest.current += 1;
      window.clearInterval(refresh);
    };
  }, [user?.id, refreshNotifications]);

  useEffect(() => {
    if (mobileOpen && !wasMobileOpen.current) {
      sidebarRef.current?.querySelector<HTMLAnchorElement>("a[href]")?.focus();
      document.body.style.overflow = "hidden";
    } else if (!mobileOpen && wasMobileOpen.current) {
      document.body.style.overflow = "";
      menuButtonRef.current?.focus();
    }
    wasMobileOpen.current = mobileOpen;
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  useEffect(() => {
    const closePopovers = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const returnFocusTo = profileOpen ? profileButtonRef : notificationsOpen ? notificationButtonRef : null;
      setNotificationsOpen(false);
      setProfileOpen(false);
      if (mobileOpen) {
        setMobileOpen(false);
        menuButtonRef.current?.focus();
      } else returnFocusTo?.current?.focus();
    };
    window.addEventListener("keydown", closePopovers);
    return () => window.removeEventListener("keydown", closePopovers);
  }, [mobileOpen, notificationsOpen, profileOpen]);

  const unreadCount = notifications.filter((item) => !item.is_read).length;

  const markAllRead = async () => {
    if (markingAllRead || unreadCount === 0) return;
    setMarkingAllRead(true);
    try {
      await api.markAllNotificationsRead();
      setNotifications((items) => items.map((item) => ({ ...item, is_read: true })));
      setNotificationError(null);
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : "Unable to update notifications.");
    } finally {
      setMarkingAllRead(false);
    }
  };

  const openNotification = async (notification: Notification) => {
    if (notificationActionId) return;
    setNotificationActionId(notification.id);
    if (!notification.is_read) {
      try {
        await api.markNotificationRead(notification.id);
        setNotifications((items) => items.map((item) => item.id === notification.id ? { ...item, is_read: true } : item));
      } catch (error) {
        setNotificationError(error instanceof Error ? error.message : "Unable to update notification.");
        setNotificationActionId(null);
        return;
      }
    }
    setNotificationsOpen(false);
    if (notification.submission_id) {
      navigate(notification.kind === "review_assignment"
        ? `/approval/${notification.submission_id}`
        : `/review/${notification.submission_id}`);
    }
    setNotificationActionId(null);
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

  const navByRole: Record<UserRole, NavLink[]> = {
    creator: [
      { label: "My Work", path: "/", icon: FileText },
      { label: "New Content Check", path: "/new", icon: FileText },
      { label: "Certificates", path: "/certificates", icon: BadgeCheck },
      { label: "Limitations", path: "/limitations", icon: HelpCircle },
    ],
    manager: [
      { label: "Command Center", path: "/", icon: FileText },
      { label: "Guideline Health", path: "/dashboard/guideline-health", icon: Flame },
      { label: "Org Insights", path: "/insights", icon: BarChart3 },
      { label: "Approved Sources", path: "/sources", icon: Database },
      { label: "Certificates", path: "/certificates", icon: BadgeCheck },
      { label: "Limitations", path: "/limitations", icon: HelpCircle },
    ],
    reviewer: [
      { label: "Compliance Desk", path: "/", icon: ShieldCheck },
      { label: "Approved Sources (Read-Only)", path: "/sources", icon: Database },
      { label: "Certificates", path: "/certificates", icon: BadgeCheck },
      { label: "Limitations", path: "/limitations", icon: HelpCircle },
    ],
    admin: [
      { label: "Admin Console", path: "/", icon: FileText },
      { label: "Approved Sources", path: "/sources", icon: Database },
      { label: "Guideline Health", path: "/dashboard/guideline-health", icon: Flame },
      { label: "Org Insights", path: "/insights", icon: BarChart3 },
      { label: "Certificates", path: "/certificates", icon: BadgeCheck },
      { label: "Integrity Check", path: "/admin/integrity", icon: Fingerprint },
      { label: "Limitations", path: "/limitations", icon: HelpCircle },
    ],
  };
  const activeLinks = user ? navByRole[user.role] : [];
  const activeLink = activeLinks.find((link) => currentPath === link.path || (link.path !== "/" && currentPath.startsWith(`${link.path}/`)));
  const pageTitle = activeLink?.label || (
    currentPath.startsWith("/review/") ? "Review submission" :
      currentPath.startsWith("/approval/") ? "Approval dossier" :
        currentPath === "/new" ? "New content check" :
          currentPath === "/verify" ? "Verify certificate" :
            currentPath === "/limitations" ? "Known limitations" : "Sign in"
  );

  const goTo = (path: string) => {
    setMobileOpen(false);
    setProfileOpen(false);
    setNotificationsOpen(false);
    navigate(path);
  };

  const isLinkActive = (path: string) => currentPath === path || (path !== "/" && currentPath.startsWith(`${path}/`));

  const trapMobileTab = (event: React.KeyboardEvent<HTMLElement>) => {
    if (!mobileOpen || event.key !== "Tab" || !sidebarRef.current) return;
    const controls = [...sidebarRef.current.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), select:not(:disabled)')];
    if (controls.length === 0) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className={`app-shell ${user ? "" : "app-shell--guest"}`}>
      {user && mobileOpen && <button type="button" className="app-sidebar-backdrop" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
      {user && <aside ref={sidebarRef} className={`app-sidebar ${mobileOpen ? "app-sidebar--open" : ""}`} aria-label="Main navigation" onKeyDown={trapMobileTab}>
        <a href="/" onClick={(event) => { event.preventDefault(); goTo("/"); }} className="app-brand" aria-label="BrandGuard home">
          <span className="app-brand__mark"><ShieldCheck size={21} aria-hidden="true" /></span>
          <span className="app-brand__copy"><strong>BrandGuard</strong><span>Governance</span></span>
        </a>
        <div className="app-sidebar__context">
          <span className="app-sidebar__context-mark" aria-hidden="true">{user.role.slice(0, 1).toUpperCase()}</span>
          <span className="app-sidebar__context-copy"><strong>{user.role} workspace</strong><span>Brand governance</span></span>
        </div>
        <nav className="app-nav" aria-label={`${user.role} navigation`}>
          {activeLinks.map((link) => {
            const Icon = link.icon;
            const active = isLinkActive(link.path);
            return (
              <a
                key={link.path}
                href={link.path}
                aria-label={link.label}
                aria-current={active ? "page" : undefined}
                title={link.label}
                onClick={(event) => { event.preventDefault(); goTo(link.path); }}
                className={`app-nav__link ${active ? "is-active" : ""}`}
              >
                <Icon size={18} aria-hidden="true" />
                <span className="app-nav__label">{link.label}</span>
              </a>
            );
          })}
        </nav>
        <div className="app-sidebar__footer">
          <p>AI suggests. People decide.</p>
          <span>Pre-publication review workspace</span>
        </div>
      </aside>}

      <div className="app-shell__main">
        <header className="app-topbar">
          {user && <button ref={menuButtonRef} type="button" className="app-mobile-menu" aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"} aria-expanded={mobileOpen} onClick={() => setMobileOpen((open) => !open)}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>}
          {!user && <a href="/" className="app-brand app-brand--mobile" onClick={(event) => { event.preventDefault(); goTo("/"); }} aria-label="BrandGuard home">
            <span className="app-brand__mark"><ShieldCheck size={20} aria-hidden="true" /></span>
            <span className="app-brand__copy"><strong>BrandGuard</strong><span>Governance</span></span>
          </a>}
          <nav className="app-breadcrumbs" aria-label="Breadcrumb">
            <ol>
              <li><span>{user ? "Workspace" : "BrandGuard"}</span></li>
              <li aria-hidden="true"><ChevronRight size={14} /></li>
              <li aria-current="page"><strong>{pageTitle}</strong></li>
            </ol>
          </nav>

          <div className="app-topbar__controls">
            <button type="button" className="app-engine" onClick={() => setModalOpen(true)} title="Review engine status and transparency notice" aria-label={`Review engine: ${llmMode}`}>
              <Cpu size={16} aria-hidden="true" />
              <span>{llmMode}</span>
            </button>
            <span className={`app-engine-status ${retrievalState === "ready" ? "is-ready" : "is-warming"}`} title={retrievalDetail} role="status" aria-label={`Source retrieval engine: ${retrievalState}`}>
              <span className="app-engine-status__dot" aria-hidden="true" />
              <span>{retrievalState === "warming_up" || retrievalState === "reindexing" ? "Warming" : retrievalEngine === "all-MiniLM-L6-v2" ? "Neural" : "Hash"}</span>
            </span>
            <button type="button" onClick={onToggleDarkMode} className="app-icon-button" aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"} title={darkMode ? "Switch to light mode" : "Switch to dark mode"}>
              {darkMode ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
            </button>
            {user && <div className="app-popover-anchor">
              <button ref={notificationButtonRef} type="button" className={`app-icon-button ${notificationsOpen ? "is-open" : ""}`} aria-label={unreadCount ? `Notifications, ${unreadCount} unread` : "Notifications"} aria-expanded={notificationsOpen} onClick={() => { setNotificationsOpen((open) => !open); setProfileOpen(false); }}>
                <Bell size={18} aria-hidden="true" />
                {unreadCount > 0 && <span className="app-notification-count">{unreadCount > 99 ? "99+" : unreadCount}</span>}
              </button>
              {notificationsOpen && <section className="app-popover app-notifications" role="region" aria-label="Notifications">
                <div className="app-popover__heading">
                  <div><h2>Notifications</h2><p>Assignments and workflow decisions</p></div>
                  <div className="app-notifications__actions">
                    <Button variant="quiet" className="app-small-button" onClick={() => void refreshNotifications()} loading={notificationsLoading} aria-label="Refresh notifications"><RotateCcw size={14} />Refresh</Button>
                    {unreadCount > 0 && <Button variant="quiet" className="app-small-button" onClick={() => void markAllRead()} loading={markingAllRead}> <CheckCheck size={14} />Mark all read</Button>}
                  </div>
                </div>
                {notificationError && <p role="alert" className="app-inline-error">{notificationError} <button type="button" onClick={() => void refreshNotifications()} disabled={notificationsLoading}>Try again</button></p>}
                <div className="app-notifications__list">
                  {notificationsLoading && notifications.length === 0 ? <p className="app-notifications__empty" role="status">Loading notifications…</p> : notifications.length === 0 ? <p className="app-notifications__empty">No notifications yet. New assignments and decisions will appear here.</p> : notifications.map((notification) => (
                    <button type="button" key={notification.id} onClick={() => void openNotification(notification)} className={`app-notification ${notification.is_read ? "" : "is-unread"}`} disabled={!!notificationActionId} aria-busy={notificationActionId === notification.id || undefined}>
                      <span className="app-notification__dot" aria-hidden="true" />
                      <span className="app-notification__copy"><strong>{notification.title}</strong><span>{notification.message}</span><time dateTime={notification.created_at}>{new Date(notification.created_at).toLocaleString()}</time></span>
                    </button>
                  ))}
                </div>
              </section>}
            </div>}
            {user ? <div className="app-popover-anchor">
              <button ref={profileButtonRef} type="button" className={`app-profile-button ${profileOpen ? "is-open" : ""}`} aria-expanded={profileOpen} aria-label={`${user.name}, ${user.role} account`} onClick={() => { setProfileOpen((open) => !open); setNotificationsOpen(false); }}>
                <span className="app-avatar" aria-hidden="true">{user.name.trim().slice(0, 1).toLocaleUpperCase()}</span>
                <span className="app-profile-button__copy"><strong>{user.name}</strong><span>{user.role}</span></span>
                <ChevronRight size={15} className="app-profile-button__chevron" aria-hidden="true" />
              </button>
              {profileOpen && <section className="app-popover app-profile-menu" role="region" aria-label="Account menu">
                <div className="app-profile-menu__identity"><strong>{user.name}</strong><Badge tone="neutral">{user.role}</Badge></div>
                {demoMode && <label className="ui-field app-demo-role"><span>Demo role</span><Select aria-label="Switch demo role" value={user.role} onChange={(event) => onDemoRoleSwitch(event.target.value as UserRole)}>
                  <option value="creator">Creator</option><option value="manager">Manager</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option>
                </Select></label>}
                <button type="button" onClick={() => { setProfileOpen(false); onShowOnboarding(); }}><HelpCircle size={16} />Role quick start tips</button>
                <button type="button" onClick={() => { setProfileOpen(false); setPasswordModalOpen(true); setPasswordError(null); setPasswordChanged(false); }}><LockKeyhole size={16} />Change password</button>
                <button type="button" className="is-danger" onClick={onLogout}><LogOut size={16} />Sign out</button>
              </section>}
            </div> : <a href="/login" className="ui-button ui-button--primary app-sign-in" onClick={(event) => { event.preventDefault(); goTo("/login"); }}>Sign in</a>}
          </div>
        </header>

        {children}
      </div>

      <TransparencyModal isOpen={modalOpen} onClose={() => setModalOpen(false)} llmMode={llmMode} />

      <Modal open={passwordModalOpen} title={passwordChanged ? "Password changed" : "Change password"} onClose={() => { if (!passwordChanging) closePasswordModal(); }}>
        {!passwordChanged ? <form onSubmit={submitPasswordChange} className="grid gap-4">
          <p className="text-sm text-secondary">Verify your current password, then choose a new one.</p>
          {passwordError && <p role="alert" className="app-inline-error">{passwordError}</p>}
          <Input label="Current password" type="password" name="current-password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
          <Input label="New password" type="password" name="new-password" autoComplete="new-password" minLength={12} maxLength={72} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
          <Input label="Confirm new password" type="password" name="confirm-password" autoComplete="new-password" minLength={12} maxLength={72} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          <p className="text-sm text-secondary">At least 12 characters and no more than 72 UTF-8 bytes.</p>
          <div className="flex justify-end gap-2"><Button type="button" variant="quiet" onClick={closePasswordModal} disabled={passwordChanging}>Cancel</Button><Button type="submit" loading={passwordChanging}>{passwordChanging ? "Updating…" : "Change password"}</Button></div>
        </form> : <div className="grid justify-items-start gap-4"><p className="text-sm text-secondary">Your new password is ready for your next sign in.</p><Button onClick={closePasswordModal}>Done</Button></div>}
      </Modal>
    </div>
  );
};
