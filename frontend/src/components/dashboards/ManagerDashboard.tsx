import React, { useEffect, useState } from "react";
import {
  ShieldAlert,
  Clock,
  CheckCircle,
  AlertTriangle,
  UserCheck,
  Search,
  ArrowRight,
  BarChart3,
  Flame,
  ExternalLink,
  Download,
} from "lucide-react";
import { api } from "../../api";
import { Submission, SubmissionStatus, User, InsightsSummary, GuidelineHealthClause, ActivityEvent, FeedbackCategoryStats, ApprovedFact } from "../../types";
import { findActiveFactConflicts } from "../../utils/approvedFacts";
import { Skeleton } from "../Skeleton";
import { useToast } from "../Toast";
import { SavedViews } from "../SavedViews";
import { EmptyState } from "../ui";

interface ManagerDashboardProps {
  user: User;
  navigate: (path: string) => void;
}

const toLocalDateTimeInput = (value: string) => {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export const ManagerDashboard: React.FC<ManagerDashboardProps> = ({ user, navigate }) => {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [reviewers, setReviewers] = useState<User[]>([]);
  const [insights, setInsights] = useState<InsightsSummary | null>(null);
  const [highRiskClauses, setHighRiskClauses] = useState<GuidelineHealthClause[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackCategoryStats[]>([]);
  const [sourceConflicts, setSourceConflicts] = useState<ApprovedFact[][]>([]);
  const [dueDateDrafts, setDueDateDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("in_review");
  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const [subs, ins, health, activeReviewers, recentActivity, feedback, facts] = await Promise.all([
        api.getSubmissions(),
        api.getInsightsSummary().catch(() => null),
        api.getGuidelineHealth().catch(() => []),
        api.getReviewers(),
        api.getRecentActivity().catch(() => []),
        api.getFeedbackStats().catch(() => ({ categories: [] })),
        api.getFacts(),
      ]);
      setSubmissions(subs);
      setInsights(ins);
      setHighRiskClauses(health.filter((c) => c.dispute_friction_index > 30));
      setReviewers(activeReviewers);
      setActivity(recentActivity);
      setFeedbackStats(feedback.categories);
      setSourceConflicts(findActiveFactConflicts(facts));
    } catch (err: any) {
      showToast(err.message || "Failed to load command center data", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAssign = async (submissionId: string, reviewerId: string) => {
    try {
      await api.assignSubmission(submissionId, reviewerId);
      showToast("Submission successfully assigned to compliance reviewer", "success");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Assignment failed", "error");
    }
  };

  const handleDueDateSave = async (submissionId: string, value: string) => {
    try {
      await api.updateAssignmentDueDate(submissionId, value ? new Date(value).toISOString() : null);
      setDueDateDrafts((current) => {
        const next = { ...current };
        delete next[submissionId];
        return next;
      });
      showToast(value ? "Assignment due date updated" : "Assignment due date cleared", "success");
      await loadData();
    } catch (err: any) {
      showToast(err.message || "Due date update failed", "error");
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

  const filtered = submissions.filter((s) => {
    const matchesSearch =
      s.title.toLowerCase().includes(search.toLowerCase()) ||
      (s.creator?.name && s.creator.name.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "all" || s.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getSlaBadge = (ageHours?: number) => {
    if (ageHours === undefined || ageHours === null) return null;
    if (ageHours < 4) {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
          <Clock className="w-3 h-3 text-emerald-600" />
          {ageHours}h (On Target)
        </span>
      );
    }
    if (ageHours < 12) {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
          <Clock className="w-3 h-3 text-amber-600" />
          {ageHours}h (Approaching SLA)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-800 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">
        <AlertTriangle className="w-3 h-3 text-rose-600" />
        {ageHours}h (SLA Breached)
      </span>
    );
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  const pendingApprovalsCount = submissions.filter((s) => s.status === "in_review").length;
  const pipelineStatuses: SubmissionStatus[] = ["draft", "checked", "in_review", "changes_requested", "approved", "rejected"];
  const chartDays = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - (6 - index));
    return date.toISOString().slice(0, 10);
  });
  const categoryEntries = Object.entries(insights?.findings_by_category ?? {}).sort((a, b) => b[1] - a[1]);
  const severityEntries = Object.entries(insights?.findings_by_severity ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="dashboard-workspace dashboard-workspace--manager max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <section className="dashboard-hero dashboard-hero--manager" aria-labelledby="manager-dashboard-title">
        <div className="dashboard-hero__copy">
          <div className="dashboard-hero__eyebrow"><ShieldAlert className="w-4 h-4" /> Brand governance <span aria-hidden="true">·</span> Manager</div>
          <h1 id="manager-dashboard-title" className="text-2xl sm:text-3xl font-extrabold tracking-tight">Team approval queue</h1>
          <p>Prioritize decisions, route high-risk copy to reviewers, and spot guidance that needs clarification.</p>
        </div>
        <div className="dashboard-hero__actions">
          <button
            onClick={() => navigate("/dashboard/guideline-health")}
            className="dashboard-secondary-action"
          >
            <Flame className="w-4 h-4" />
            Guideline Health
          </button>
          <button
            onClick={() => navigate("/insights")}
            className="dashboard-secondary-action"
          >
            <BarChart3 className="w-4 h-4" />
            Org Insights
          </button>
        </div>
      </section>

      {/* KPI Cards */}
      <div className="dashboard-kpis grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Pending Approvals</p>
            <p className="text-2xl font-black text-amber-600 mt-1">{pendingApprovalsCount}</p>
            <p className="text-[11px] text-stone-400 mt-1">Requires manager sign-off</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Avg Turnaround</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{insights?.avg_turnaround_hours ?? 0} hrs</p>
            <p className="text-[11px] text-emerald-600 font-semibold mt-1">SLA target &lt; 4.0 hrs</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Total Submissions</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{insights?.total_submissions ?? submissions.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Company-wide copy items</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <BarChart3 className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">High-Friction Clauses</p>
            <p className="text-2xl font-black text-rose-600 mt-1">{highRiskClauses.length}</p>
            <p className="text-[11px] text-stone-600 mt-1">DFI &gt; 30% (clarification proposals)</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
            <Flame className="w-6 h-6" />
          </div>
        </div>
      </div>

      {sourceConflicts.length > 0 && (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-4" aria-labelledby="manager-source-conflicts-title">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 id="manager-source-conflicts-title" className="text-sm font-bold text-amber-950">Source conflicts</h2>
              <p className="mt-1 text-xs text-amber-900">Resolve disagreements between active approved facts before approving affected copy.</p>
            </div>
            <button type="button" onClick={() => navigate("/sources")} className="dashboard-secondary-action">Review sources</button>
          </div>
          <ul className="mt-3 space-y-2">
            {sourceConflicts.map((group) => (
              <li key={group[0].subject} className="text-xs text-amber-950">
                <strong>{group[0].subject}:</strong>{" "}
                {group.map((fact) => `${fact.value}${fact.unit ? ` ${fact.unit}` : ""} (${fact.source_note || "source not recorded"})`).join(" · ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Submission status pipeline" className="dashboard-pipeline grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        {pipelineStatuses.map((status) => (
          <button key={status} onClick={() => setStatusFilter(status)} aria-pressed={statusFilter === status} className={`text-left p-4 rounded-xl border transition-colors ${statusFilter === status ? "dashboard-pipeline__item is-active" : "dashboard-pipeline__item"}`}>
            <span className="text-[10px] uppercase font-bold tracking-wider text-stone-600">{status.replace("_", " ")}</span>
            <span className="block text-2xl font-black text-stone-900 mt-1">{submissions.filter((submission) => submission.status === status).length}</span>
          </button>
        ))}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4" aria-label="Organization trends">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <h2 className="text-sm font-bold text-stone-900">Activity Trends · 7 Days</h2>
          <div className="mt-4 space-y-3">
            {chartDays.map((day) => {
              const submissionsToday = insights?.submissions_by_day?.[day] ?? 0;
              const findingsToday = insights?.findings_by_day?.[day] ?? 0;
              const max = Math.max(1, ...Object.values(insights?.submissions_by_day ?? {}), ...Object.values(insights?.findings_by_day ?? {}));
              return <div key={day} className="grid grid-cols-[4.5rem_1fr] gap-3 items-center text-[11px]">
                <span className="text-stone-600">{new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" })}</span>
                <div className="space-y-1">
                  <div className="dashboard-chart-track"><div className="dashboard-chart-bar" style={{ width: `${(submissionsToday / max) * 100}%` }} title={`${submissionsToday} submissions`} /></div>
                  <div className="dashboard-chart-track dashboard-chart-track--warm"><div className="dashboard-chart-bar dashboard-chart-bar--warm" style={{ width: `${(findingsToday / max) * 100}%` }} title={`${findingsToday} findings`} /></div>
                </div>
              </div>;
            })}
          </div>
          <p className="mt-3 text-[11px] text-stone-600">Green: submissions · Amber: findings</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          {[{ title: "Findings by Category", entries: categoryEntries, color: "dashboard-chart-bar" }, { title: "Findings by Severity", entries: severityEntries, color: "dashboard-chart-bar dashboard-chart-bar--danger" }].map((chart) => {
            const max = Math.max(1, ...chart.entries.map(([, count]) => count));
            return <div key={chart.title} className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
              <h2 className="text-sm font-bold text-stone-900">{chart.title}</h2>
              {chart.entries.length === 0 ? <p className="mt-4 text-xs text-stone-600">No findings recorded.</p> : <div className="mt-4 space-y-3">
                {chart.entries.map(([label, count]) => <div key={label}>
                  <div className="flex justify-between gap-2 text-[11px] mb-1"><span className="capitalize text-stone-700">{label.replace(/_/g, " ")}</span><span className="font-bold text-stone-900">{count}</span></div>
                  <div className="dashboard-chart-track"><div className={chart.color} style={{ width: `${(count / max) * 100}%` }} /></div>
                </div>)}
              </div>}
            </div>;
          })}
        </div>
      </section>

      <section aria-label="Feedback model statistics" className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-stone-900">Reviewer Feedback</h2>
            <p className="mt-1 text-[11px] text-stone-600">Decision outcomes and recurring suppressed patterns by guideline category.</p>
          </div>
          <span className="text-[10px] uppercase tracking-wider font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-1">Adaptive ranking</span>
        </div>
        {feedbackStats.length ? <div className="mt-4 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
          {feedbackStats.map((stat) => <div key={stat.category} className="rounded-xl bg-stone-50 border border-stone-200 p-3">
            <h3 className="text-[10px] font-bold uppercase tracking-wide text-stone-700">{stat.category.replace(/_/g, " ")}</h3>
            <div className="mt-2 flex justify-between gap-2 text-[11px]"><span className="text-stone-600">Accepted</span><strong className="text-emerald-800">{Math.round(stat.acceptance_rate * 100)}%</strong></div>
            <div className="mt-1 flex justify-between gap-2 text-[11px]"><span className="text-stone-600">Edited</span><strong className="text-amber-800">{Math.round(stat.edit_rate * 100)}%</strong></div>
            <div className="mt-1 flex justify-between gap-2 text-[11px]"><span className="text-stone-600">Suppressed</span><strong className="text-rose-800">{stat.suppression_count}</strong></div>
          </div>)}
        </div> : <p className="mt-3 text-xs text-stone-600">No reviewer decisions recorded yet.</p>}
      </section>

      <section aria-label="Recent organization activity" className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
        <h2 className="text-sm font-bold text-stone-900">Recent Activity</h2>
        {activity.length ? <ul className="mt-3 divide-y divide-stone-100">
          {activity.slice(0, 6).map((event) => <li key={event.id} className="py-2.5 flex flex-wrap justify-between gap-2 text-xs">
            <span className="text-stone-800"><strong>{event.actor_name}</strong> {event.action.replace(/_/g, " ")}{event.entity ? ` · ${event.entity}` : ""}</span>
            <time className="text-stone-600" dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
          </li>)}
        </ul> : <p className="mt-3 text-xs text-stone-600">No organization activity recorded yet.</p>}
      </section>

      {/* Approval Queue with Filters and SLA Indicator */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-stone-200">
          <div>
            <h2 className="text-lg font-bold text-stone-900">Governance Approval Queue</h2>
            <p className="text-xs text-stone-500 mt-0.5">Filter by review status, inspect SLA age, and assign compliance specialists.</p>
          </div>

          <div className="dashboard-filters flex items-center gap-3">
            <div className="dashboard-search relative">
              <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                aria-label="Search submissions or authors"
                placeholder="Search submission or author..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:ring-2 focus:ring-emerald-600 focus:outline-none w-52"
              />
            </div>
            <select
              aria-label="Filter approval queue by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-stone-300 rounded-lg px-2.5 py-1.5 bg-white text-stone-700 font-semibold focus:ring-2 focus:ring-emerald-600 focus:outline-none"
            >
              <option value="all">All Content</option>
              <option value="in_review">In Review (Action Required)</option>
              <option value="changes_requested">Changes Requested</option>
              <option value="approved">Approved</option>
              <option value="checked">Checked Drafts</option>
            </select>
          </div>
        </div>

        <SavedViews
          userId={user.id}
          role="manager"
          search={search}
          setSearch={setSearch}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
        />
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" onClick={() => downloadApprovalReport("csv")} className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-50">
            <Download className="h-3.5 w-3.5" />Export CSV
          </button>
          <button type="button" onClick={() => downloadApprovalReport("pdf")} className="inline-flex items-center gap-1.5 rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-stone-800">
            <Download className="h-3.5 w-3.5" />Export PDF
          </button>
        </div>

        {/* Submissions Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-stone-200 text-stone-500 font-semibold uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Content Title</th>
                <th className="py-3 px-4">Author</th>
                <th className="py-3 px-4">Status & SLA</th>
                <th className="py-3 px-4">Assigned Reviewer</th>
                <th className="py-3 px-4">Due Date / SLA</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {filtered.map((sub) => {
                const isOwn = sub.creator_id === user.id;
                return (
                  <tr key={sub.id} className="hover:bg-stone-50/70 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-stone-900">
                      <div>
                        <span className="font-bold">{sub.title}</span>
                        <span className="ml-2 text-[10px] uppercase font-bold text-stone-500 bg-stone-100 px-1.5 py-0.5 rounded border">
                          {sub.content_type}
                        </span>
                      </div>
                      {sub.intent && <p className="text-[11px] text-stone-400 font-normal truncate max-w-xs mt-0.5">"{sub.intent}"</p>}
                    </td>
                    <td className="py-3.5 px-4 text-stone-700 font-medium">
                      {sub.creator?.name || "Unknown Author"}
                      {isOwn && <span className="ml-1 text-[10px] text-amber-700 font-bold bg-amber-50 px-1 rounded">(You)</span>}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-1 items-start">
                        <span className="text-[11px] uppercase font-bold text-stone-700">{sub.status.replace("_", " ")}</span>
                        {getSlaBadge(sub.age_hours)}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <select
                        aria-label={`Assign reviewer for ${sub.title}`}
                        value={sub.assigned_to_id || ""}
                        onChange={(e) => handleAssign(sub.id, e.target.value)}
                        className="text-xs border border-stone-300 rounded-lg px-2 py-1 bg-white text-stone-800 focus:ring-2 focus:ring-emerald-600 focus:outline-none"
                      >
                        <option value="">Unassigned</option>
                        {reviewers.map((rev) => (
                          <option key={rev.id} value={rev.id}>
                            {rev.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3.5 px-4 min-w-56">
                      {sub.assigned_to_id && sub.status === "in_review" ? (
                        <div className="flex flex-col items-start gap-1.5">
                          <div className="flex items-center gap-1.5">
                            <input
                              aria-label={`Due date for ${sub.title}`}
                              type="datetime-local"
                              value={dueDateDrafts[sub.id] ?? (sub.assignment_due_at ? toLocalDateTimeInput(sub.assignment_due_at) : "")}
                              onChange={(event) => setDueDateDrafts((current) => ({ ...current, [sub.id]: event.target.value }))}
                              className="text-[11px] border border-stone-300 rounded-md px-1.5 py-1 bg-white"
                            />
                            <button
                              type="button"
                              onClick={() => handleDueDateSave(sub.id, dueDateDrafts[sub.id] ?? (sub.assignment_due_at ? toLocalDateTimeInput(sub.assignment_due_at) : ""))}
                              className="text-[10px] font-bold rounded-md px-2 py-1 bg-emerald-700 hover:bg-emerald-800 text-white"
                            >Save</button>
                          </div>
                          <span className={`text-[10px] font-semibold ${sub.is_overdue ? "text-red-700" : "text-stone-500"}`}>
                            {sub.is_overdue ? "Overdue" : sub.assignment_due_at ? `Due ${new Date(sub.assignment_due_at).toLocaleString()}` : "No due date"}
                          </span>
                          {sub.assignment_due_at && (
                            <button
                              type="button"
                              onClick={() => handleDueDateSave(sub.id, "")}
                              className="text-[10px] text-stone-500 underline hover:text-stone-800"
                            >Clear due date</button>
                          )}
                        </div>
                      ) : <span className="text-stone-400">—</span>}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2">
                      <button
                        onClick={() => navigate(`/approval/${sub.id}`)}
                        className="px-3 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 text-white font-semibold text-xs inline-flex items-center gap-1 shadow-sm"
                      >
                        {isOwn ? "View" : sub.status === "in_review" ? "Sign-Off" : "Review"}
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && <tr><td colSpan={6}><EmptyState title="No submissions match this view" description="Adjust the search or status filter to find work in the approval queue." action={<button type="button" className="dashboard-secondary-action" onClick={() => { setSearch(""); setStatusFilter("all"); }}>Clear filters</button>} /></td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
