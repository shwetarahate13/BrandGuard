import React, { useEffect, useState } from "react";
import {
  Users,
  Settings,
  Shield,
  FileSpreadsheet,
  RotateCcw,
  Plus,
  Key,
  CheckCircle,
  Database,
  Cpu,
  Download,
  AlertTriangle,
} from "lucide-react";
import { api } from "../../api";
import { User, SystemSettings, AuditLog, FeedbackCategoryStats, SystemStatus } from "../../types";
import { Skeleton } from "../Skeleton";
import { useToast } from "../Toast";
import { EmptyState } from "../ui";

interface AdminDashboardProps {
  user: User;
  navigate: (path: string) => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ user, navigate }) => {
  const [users, setUsers] = useState<User[]>([]);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackCategoryStats[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"users" | "settings" | "audit" | "feedback">("users");

  // New user form state
  const [showUserModal, setShowUserModal] = useState(false);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState("creator");

  // Password reset state
  const [resetUserId, setResetUserId] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const [uList, sData, logs, fb, health] = await Promise.all([
        api.getUsers().catch(() => []),
        api.getSystemSettings().catch(() => null),
        api.getAuditLogs({ limit: 50 }).catch(() => []),
        api.getFeedbackStats().catch(() => ({ categories: [] })),
        api.getSystemStatus().catch(() => null),
      ]);
      setUsers(uList);
      setSettings(sData);
      setAuditLogs(logs);
      setFeedbackStats(fb.categories);
      setSystemStatus(health);
    } catch (err: any) {
      showToast(err.message || "Failed to load admin console", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createUser({
        name: newUserName.trim(),
        email: newUserEmail.trim(),
        password: newUserPassword,
        role: newUserRole,
      });
      showToast(`User ${newUserName} created successfully`, "success");
      setShowUserModal(false);
      setNewUserName("");
      setNewUserEmail("");
      setNewUserPassword("");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Failed to create user", "error");
    }
  };

  const handleUpdateRole = async (userId: string, newRole: string) => {
    try {
      await api.updateUser(userId, { role: newRole });
      showToast("Role updated", "success");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Failed to update role", "error");
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    try {
      await api.updateUser(userId, { is_active: !currentActive });
      showToast(`User ${!currentActive ? "activated" : "deactivated"}`, "success");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Failed to update status", "error");
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetUserId) return;
    try {
      await api.resetUserPassword(resetUserId, resetPassword);
      showToast("Password reset successfully", "success");
      setResetUserId(null);
      setResetPassword("");
    } catch (err: any) {
      showToast(err.message || "Password reset failed", "error");
    }
  };

  const handleToggleLLM = async () => {
    if (!settings) return;
    try {
      const updated = await api.updateSystemSettings({ llm_enabled: !settings.llm_enabled });
      setSettings(updated);
      showToast(`LLM engine ${updated.llm_enabled ? "enabled" : "disabled (deterministic mock mode)"}`, "success");
    } catch (err: any) {
      showToast(err.message || "Settings update failed", "error");
    }
  };

  const handleResetFeedbackModel = async () => {
    if (!window.confirm("Are you sure you want to reset the SGD feedback preference model? This clears learned rewrite weights.")) {
      return;
    }
    try {
      await api.resetFeedbackModel();
      showToast("Feedback model weights reset successfully", "success");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Reset failed", "error");
    }
  };

  const downloadApprovalReport = async (format: "csv" | "pdf") => {
    try {
      await api.downloadApprovalReport(format);
      showToast(`Approval report downloaded as ${format.toUpperCase()}`, "success");
    } catch (err: any) {
      showToast(err.message || "Approval report download failed", "error");
    }
  };

  const downloadAuditCsv = async () => {
    try {
      await api.downloadAuditLogCsv();
      showToast("Audit log downloaded as CSV", "success");
    } catch (err: any) {
      showToast(err.message || "Audit log download failed", "error");
    }
  };

  if (loading) {
    return (
      <div className="dashboard-workspace dashboard-workspace--admin max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-workspace dashboard-workspace--admin max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <section className="dashboard-hero dashboard-hero--admin" aria-labelledby="admin-dashboard-title">
        <div className="dashboard-hero__copy">
          <div className="dashboard-hero__eyebrow"><Shield className="w-4 h-4" /> Workspace administration <span aria-hidden="true">·</span> Admin</div>
          <h1 id="admin-dashboard-title" className="text-2xl sm:text-3xl font-extrabold tracking-tight">System governance</h1>
          <p>Manage team access, runtime settings, audit history, and the feedback model from one place.</p>
        </div>
        <div className="dashboard-hero__actions">
          <button
            onClick={() => navigate("/sources")}
            className="dashboard-secondary-action"
          >
            <Database className="w-4 h-4" />
            Manage Approved Sources
          </button>
        </div>
      </section>

      {/* KPI Cards */}
      <div className="dashboard-kpis grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Active Users</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{users.filter((u) => u.is_active).length}</p>
            <p className="text-[11px] text-stone-400 mt-1">{users.length} total registered</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">System Health</p>
            <p className={`text-lg font-black mt-1 ${systemStatus?.database_connected ? "text-emerald-800" : "text-rose-800"}`}>
              {systemStatus?.database_connected ? "Operational" : "Degraded"}
            </p>
            <p className="text-[11px] text-stone-600 mt-1">DB {systemStatus?.database_connected ? "online" : "offline"} · Index {systemStatus?.chroma_indexed ? "ready" : "empty"}</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-800 flex items-center justify-center">
            <Database className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">LLM Engine</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{settings?.llm_enabled ? "Active" : "Offline"}</p>
            <p className="text-[11px] text-stone-400 mt-1">Configurable via toggle</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Cpu className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Audit Trail</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{auditLogs.length} events</p>
            <p className="text-[11px] text-stone-400 mt-1">Full immutable history</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
            <FileSpreadsheet className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Feedback Categories</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{feedbackStats.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Learned preference models</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <RotateCcw className="w-6 h-6" />
          </div>
        </div>
      </div>

      <section className="dashboard-overview-grid grid grid-cols-1 xl:grid-cols-2 gap-4" aria-label="Workspace overview">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <div className="dashboard-section-heading"><div><h2>Team role mix</h2><p>Active users by workspace responsibility.</p></div></div>
          <div className="dashboard-mini-breakdown mt-4">
            {(["admin", "manager", "reviewer", "creator"] as const).map((role) => {
              const count = users.filter((member) => member.is_active && member.role === role).length;
              const max = Math.max(1, ...(["admin", "manager", "reviewer", "creator"] as const).map((key) => users.filter((member) => member.is_active && member.role === key).length));
              return <div key={role} className="dashboard-mini-breakdown__row"><span>{role}<small>active accounts</small></span><b>{count}</b><div className="dashboard-mini-breakdown__track"><i style={{ width: `${(count / max) * 100}%` }} /></div></div>;
            })}
          </div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <div className="dashboard-section-heading"><div><h2>Latest audit activity</h2><p>Recent changes recorded in the immutable audit trail.</p></div><button type="button" className="dashboard-secondary-action" onClick={() => setActiveTab("audit")}>Open audit log</button></div>
          {auditLogs.length ? <ul className="dashboard-audit-feed mt-4">{auditLogs.slice(0, 4).map((log) => <li key={log.id}><span className="dashboard-audit-feed__mark" aria-hidden="true" /><div><b>{log.user?.name || "System"}</b><span>{log.action.replace(/_/g, " ")}{log.entity ? ` · ${log.entity}` : ""}</span></div><time dateTime={log.created_at}>{new Date(log.created_at).toLocaleDateString()}</time></li>)}</ul> : <EmptyState title="No audit events yet" description="Recorded account, submission, and approval activity will appear here." />}
        </div>
      </section>

      {/* Tabs Navigation */}
      <div className="dashboard-admin-tabs flex items-center gap-2 border-b border-stone-200" role="tablist" aria-label="Administration sections">
        {[
          { key: "users", label: "User Management", icon: Users },
          { key: "settings", label: "System Settings", icon: Settings },
          { key: "audit", label: "Audit Logs & Export", icon: FileSpreadsheet },
          { key: "feedback", label: "Feedback Model", icon: RotateCcw },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={active}
              id={`admin-tab-${tab.key}`}
              tabIndex={active ? 0 : -1}
              onClick={() => setActiveTab(tab.key as any)}
              onKeyDown={(event) => {
                const keys = ["users", "settings", "audit", "feedback"] as const;
                const current = keys.indexOf(activeTab);
                const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                if (event.key === "Home") { event.preventDefault(); setActiveTab(keys[0]); document.getElementById("admin-tab-users")?.focus(); }
                else if (event.key === "End") { event.preventDefault(); setActiveTab(keys[keys.length - 1]); document.getElementById("admin-tab-feedback")?.focus(); }
                else if (step) { event.preventDefault(); const next = keys[(current + step + keys.length) % keys.length]; setActiveTab(next); requestAnimationFrame(() => document.getElementById(`admin-tab-${next}`)?.focus()); }
              }}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
                active
                  ? "border-stone-900 text-stone-900"
                  : "border-transparent text-stone-500 hover:text-stone-800"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: User Management */}
      {activeTab === "users" && (
        <div id="admin-panel-users" role="tabpanel" aria-labelledby="admin-tab-users" className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-stone-900">User Management</h2>
              <p className="text-xs text-stone-500 mt-0.5">Manage team members, assign RBAC permissions, and reset credentials.</p>
            </div>
            <button
              onClick={() => setShowUserModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-bold shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Add User
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Name & Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-stone-50/70 transition-colors">
                    <td className="py-3.5 px-4">
                      <p className="font-bold text-stone-900">{u.name}</p>
                      <p className="text-[11px] text-stone-400">{u.email}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <select
                        aria-label={`Role for ${u.name}`}
                        value={u.role}
                        onChange={(e) => handleUpdateRole(u.id, e.target.value)}
                        className="text-xs border border-stone-300 rounded-lg px-2.5 py-1 bg-white text-stone-800 font-semibold focus:ring-2 focus:ring-stone-900 focus:outline-none"
                      >
                        <option value="creator">Creator</option>
                        <option value="manager">Brand Manager</option>
                        <option value="reviewer">Reviewer</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => handleToggleActive(u.id, u.is_active)}
                        className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${
                          u.is_active
                            ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                            : "bg-rose-50 text-rose-800 border-rose-200"
                        }`}
                      >
                        {u.is_active ? "Active" : "Deactivated"}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2">
                      <button
                        onClick={() => {
                          setResetUserId(u.id);
                          setResetPassword("");
                        }}
                        className="px-2.5 py-1 rounded border border-stone-300 hover:bg-stone-100 text-[11px] font-semibold text-stone-700 inline-flex items-center gap-1"
                      >
                        <Key className="w-3 h-3" />
                        Reset Pwd
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={4}><EmptyState title="No team members yet" description="Add a team member to begin assigning governance roles." action={<button type="button" className="dashboard-primary-action" onClick={() => setShowUserModal(true)}><Plus className="h-4 w-4" />Add a user</button>} /></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: System Settings */}
      {activeTab === "settings" && (
        <div id="admin-panel-settings" role="tabpanel" aria-labelledby="admin-tab-settings" className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
          <div>
            <h2 className="text-lg font-bold text-stone-900">Governance System Settings</h2>
            <p className="text-xs text-stone-500 mt-0.5">Control live LLM evaluation toggles, confidence routing thresholds, and vector similarity gates.</p>
          </div>

          <div className="space-y-4 max-w-xl">
            <div className="flex items-center justify-between p-4 rounded-xl border border-stone-200 bg-stone-50/60">
              <div>
                <p className="text-xs font-bold text-stone-900">LLM Provider Review</p>
                <p className="text-[11px] text-stone-500 mt-0.5">Toggle live generative model vs offline deterministic engine</p>
              </div>
              <button
                onClick={handleToggleLLM}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
                  settings?.llm_enabled
                    ? "bg-emerald-600 text-white hover:bg-emerald-700"
                    : "bg-stone-300 text-stone-700 hover:bg-stone-400"
                }`}
              >
                {settings?.llm_enabled ? "Enabled" : "Mock / Offline"}
              </button>
            </div>

            <div className="p-4 rounded-xl border border-stone-200 bg-stone-50/60 space-y-2">
              <label htmlFor="admin-min-confidence" className="block text-xs font-bold text-stone-900">Minimum Finding Confidence</label>
              <select
                id="admin-min-confidence"
                value={settings?.min_confidence || "medium"}
                onChange={async (e) => {
                  const updated = await api.updateSystemSettings({ min_confidence: e.target.value });
                  setSettings(updated);
                  showToast("Confidence threshold updated", "success");
                }}
                className="text-xs border border-stone-300 rounded-lg p-2 bg-white text-stone-800 font-semibold w-full"
              >
                <option value="low">Low (Emit all potential findings)</option>
                <option value="medium">Medium (Standard pre-publication bar)</option>
                <option value="high">High (Strict verified grounding only)</option>
              </select>
            </div>

            <div className="p-4 rounded-xl border border-stone-200 bg-stone-50/60 space-y-2">
              <label htmlFor="admin-similarity-threshold" className="block text-xs font-bold text-stone-900">Vector Retrieval Cosine Similarity Threshold</label>
              <input
                id="admin-similarity-threshold"
                type="number"
                step="0.05"
                min="0.5"
                max="0.95"
                value={settings?.similarity_threshold || 0.75}
                onChange={async (e) => {
                  const val = parseFloat(e.target.value);
                  if (!isNaN(val)) {
                    const updated = await api.updateSystemSettings({ similarity_threshold: val });
                    setSettings(updated);
                  }
                }}
                className="text-xs border border-stone-300 rounded-lg p-2 bg-white text-stone-800 font-semibold w-full"
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Audit Logs & Export */}
      {activeTab === "audit" && (
        <div id="admin-panel-audit" role="tabpanel" aria-labelledby="admin-tab-audit" className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-stone-900">Audit Logs & Export</h2>
              <p className="text-xs text-stone-500 mt-0.5">Immutable record of all submission checks, fix decisions, revisions, and approvals.</p>
            </div>
            <button
              type="button"
              onClick={downloadAuditCsv}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow-sm"
            >
              <Download className="w-4 h-4" />
              Export Audit CSV
            </button>
            <button type="button" onClick={() => downloadApprovalReport("csv")} className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-300 hover:bg-stone-50 text-stone-800 rounded-xl text-xs font-bold">
              <Download className="w-4 h-4" />Approval CSV
            </button>
            <button type="button" onClick={() => downloadApprovalReport("pdf")} className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-bold">
              <Download className="w-4 h-4" />Approval PDF
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Entity</th>
                  <th className="py-3 px-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 font-mono text-[11px]">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-stone-50">
                    <td className="py-3 px-4 text-stone-500">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-sans font-semibold text-stone-800">
                      {log.user?.name || "System"}
                    </td>
                    <td className="py-3 px-4 font-bold text-stone-900">
                      {log.action}
                    </td>
                    <td className="py-3 px-4 text-stone-600">
                      {log.entity} #{log.entity_id ? log.entity_id.slice(0, 8) : "-"}
                    </td>
                    <td className="py-3 px-4 text-stone-500 truncate max-w-xs font-sans">
                      {JSON.stringify(log.meta || {})}
                    </td>
                  </tr>
                ))}
                {auditLogs.length === 0 && <tr><td colSpan={5}><EmptyState title="No audit events yet" description="Recorded account, submission, and approval activity will appear here." /></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Feedback Model Control */}
      {activeTab === "feedback" && (
        <div id="admin-panel-feedback" role="tabpanel" aria-labelledby="admin-tab-feedback" className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-stone-900">Reinforcement Feedback Model Stats</h2>
              <p className="text-xs text-stone-500 mt-0.5">
                Online SGD logistic regression trained on human accept, edit, and dispute decisions.
              </p>
            </div>
            <button
              onClick={handleResetFeedbackModel}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-sm"
            >
              <RotateCcw className="w-4 h-4" />
              Reset Model State
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Total Decisions</th>
                  <th className="py-3 px-4">Acceptance Rate</th>
                  <th className="py-3 px-4">Edit Rate</th>
                  <th className="py-3 px-4">Suppressed Patterns</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {feedbackStats.map((stat) => (
                  <tr key={stat.category} className="hover:bg-stone-50">
                    <td className="py-3.5 px-4 font-bold text-stone-900 uppercase text-[11px]">
                      {stat.category}
                    </td>
                    <td className="py-3.5 px-4 text-stone-700 font-semibold">{stat.decisions_count}</td>
                    <td className="py-3.5 px-4">
                      <span className="font-bold text-emerald-700">{(stat.acceptance_rate * 100).toFixed(1)}%</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-bold text-amber-700">{(stat.edit_rate * 100).toFixed(1)}%</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-bold text-stone-600">{stat.suppression_count} patterns</span>
                    </td>
                  </tr>
                ))}
                {feedbackStats.length === 0 && <tr><td colSpan={5}><EmptyState title="No feedback decisions yet" description="Accepted, edited, or disputed findings will build category-level feedback statistics." /></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Create User */}
      {showUserModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in zoom-in-95">
            <h3 className="text-base font-bold text-stone-900">Add New Team Member</h3>
            <form onSubmit={handleCreateUser} className="space-y-3">
              <div>
                <label htmlFor="admin-new-user-name" className="block text-xs font-semibold text-stone-700">Full Name</label>
                <input
                  id="admin-new-user-name"
                  type="text"
                  required
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none"
                  placeholder="e.g. Alex Rivera"
                />
              </div>
              <div>
                <label htmlFor="admin-new-user-email" className="block text-xs font-semibold text-stone-700">Email Address</label>
                <input
                  id="admin-new-user-email"
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none"
                  placeholder="alex@nexora.dev"
                />
              </div>
              <div>
                <label htmlFor="admin-new-user-password" className="block text-xs font-semibold text-stone-700">Password</label>
                <input
                  id="admin-new-user-password"
                  type="password"
                  required
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none"
                  placeholder="Min 6 characters"
                />
              </div>
              <div>
                <label htmlFor="admin-new-user-role" className="block text-xs font-semibold text-stone-700">Role</label>
                <select
                  id="admin-new-user-role"
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  className="w-full text-xs p-2.5 border border-stone-300 rounded-lg bg-white focus:ring-2 focus:ring-stone-900 focus:outline-none font-semibold"
                >
                  <option value="creator">Creator (My Work)</option>
                  <option value="manager">Brand Manager (Command Center)</option>
                  <option value="reviewer">Reviewer (Compliance Desk)</option>
                  <option value="admin">Admin (System Control)</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowUserModal(false)}
                  className="px-3.5 py-2 text-xs font-semibold text-stone-600 hover:text-stone-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-bold shadow"
                >
                  Create Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Reset Password */}
      {resetUserId && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in zoom-in-95">
            <h3 className="text-base font-bold text-stone-900">Reset User Password</h3>
            <form onSubmit={handleResetPassword} className="space-y-3">
              <div>
                <label htmlFor="admin-reset-password" className="block text-xs font-semibold text-stone-700">New Password</label>
                <input
                  id="admin-reset-password"
                  type="password"
                  required
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none"
                  placeholder="Min 6 characters"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setResetUserId(null)}
                  className="px-3.5 py-2 text-xs font-semibold text-stone-600 hover:text-stone-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-bold shadow"
                >
                  Set Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
