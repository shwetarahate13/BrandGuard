import React, { useEffect, useState } from "react";
import {
  FileText,
  PlusCircle,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Search,
  ArrowRight,
  TrendingUp,
  Bell,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { api } from "../../api";
import { CreatorPersonalStats, Submission, SubmissionStatus, User } from "../../types";
import { Skeleton } from "../Skeleton";
import { useToast } from "../Toast";
import { SavedViews } from "../SavedViews";

interface CreatorDashboardProps {
  user: User;
  navigate: (path: string) => void;
}

export const CreatorDashboard: React.FC<CreatorDashboardProps> = ({ user, navigate }) => {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [personalStats, setPersonalStats] = useState<CreatorPersonalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const [subs, stats] = await Promise.all([
        api.getSubmissions(),
        api.getPersonalStats().catch(() => null),
      ]);
      setSubmissions(subs);
      setPersonalStats(stats);
    } catch (err: any) {
      showToast(err.message || "Failed to load My Work data", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filtered = submissions.filter((s) => {
    const matchesSearch =
      s.title.toLowerCase().includes(search.toLowerCase()) ||
      (s.intent && s.intent.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "all" || s.status === statusFilter;
    return matchesSearch && matchesStatus;
  });
  const statusOrder: SubmissionStatus[] = ["draft", "checked", "in_review", "changes_requested", "approved", "rejected"];
  const activityDays = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - (6 - index));
    const key = date.toISOString().slice(0, 10);
    return { key, count: submissions.filter((submission) => submission.created_at.slice(0, 10) === key).length };
  });
  const activityMax = Math.max(1, ...activityDays.map((day) => day.count));

  const getStatusBadge = (status: SubmissionStatus) => {
    const map: Record<SubmissionStatus, { label: string; color: string; icon: any }> = {
      draft: { label: "Draft", color: "bg-stone-100 text-stone-800 border-stone-300", icon: FileText },
      checked: { label: "Checked", color: "bg-sky-50 text-sky-800 border-sky-300", icon: CheckCircle },
      in_review: { label: "In Review", color: "bg-amber-50 text-amber-800 border-amber-300", icon: Clock },
      changes_requested: { label: "Changes Requested", color: "bg-orange-50 text-orange-800 border-orange-300", icon: AlertTriangle },
      approved: { label: "Approved", color: "bg-emerald-50 text-emerald-800 border-emerald-300", icon: CheckCircle },
      rejected: { label: "Rejected", color: "bg-rose-50 text-rose-800 border-rose-300", icon: XCircle },
    };
    const conf = map[status] || map.draft;
    const Icon = conf.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs font-semibold uppercase px-2.5 py-1 rounded-full border ${conf.color}`}>
        <Icon className="w-3.5 h-3.5" />
        {conf.label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="dashboard-workspace dashboard-workspace--creator max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
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
    <div className="dashboard-workspace dashboard-workspace--creator max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <section className="dashboard-hero dashboard-hero--creator" aria-labelledby="creator-dashboard-title">
        <div className="dashboard-hero__copy">
          <div className="dashboard-hero__eyebrow"><Sparkles className="w-4 h-4" /> Creator workspace <span aria-hidden="true">·</span> My work</div>
          <h1 id="creator-dashboard-title" className="text-2xl sm:text-3xl font-extrabold tracking-tight">Welcome, {user.name}</h1>
          <p>Shape a draft, check it against brand guidance, and follow each review decision through to approval.</p>
        </div>
        <div className="dashboard-hero__actions">
        <button
          onClick={() => navigate("/new")}
          className="dashboard-primary-action"
        >
          <PlusCircle className="w-4 h-4" />
          Start a content check
        </button>
        </div>
      </section>

      {/* Creator Personal KPI Cards */}
      <div className="dashboard-kpis grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">My Submissions</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{personalStats?.total_submissions ?? submissions.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Total pieces created</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Fix Acceptance Rate</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{personalStats?.acceptance_rate ?? 0}%</p>
            <p className="text-[11px] text-emerald-600 font-semibold mt-1">Intent-aligned suggestions</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Action Needed</p>
            <p className="text-2xl font-black text-orange-600 mt-1">
              {personalStats?.pending_action_count ?? submissions.filter((s) => s.status === "changes_requested" || s.status === "checked").length}
            </p>
            <p className="text-[11px] text-stone-400 mt-1">Checked or changes requested</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Approved Copies</p>
            <p className="text-2xl font-black text-emerald-600 mt-1">
              {submissions.filter((s) => s.status === "approved").length}
            </p>
            <p className="text-[11px] text-stone-400 mt-1">Cleared for publication</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>
      </div>

      <section className="dashboard-pipeline" aria-label="My submissions by status">
        <div className="dashboard-section-heading">
          <div><h2>My work by status</h2><p>Choose a stage to narrow your submissions.</p></div>
          <span className="dashboard-section-note">{submissions.length} total</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          {statusOrder.map((status) => (
            <button key={status} type="button" aria-pressed={statusFilter === status} onClick={() => setStatusFilter(status)} className={`dashboard-pipeline__item text-left p-4 rounded-xl border ${statusFilter === status ? "is-active" : ""}`}>
              <span className="text-[10px] uppercase font-bold tracking-wider">{status.replace("_", " ")}</span>
              <span className="block text-2xl font-black mt-1">{submissions.filter((submission) => submission.status === status).length}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="dashboard-overview-grid grid grid-cols-1 xl:grid-cols-2 gap-4" aria-label="Creator activity and guidance themes">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <div className="dashboard-section-heading"><div><h2>Submission activity</h2><p>New drafts created during the past seven days.</p></div></div>
          <div className="dashboard-activity-chart mt-4" role="img" aria-label="Daily submission counts for the last seven days">
            {activityDays.map(({ key, count }) => <div key={key} className="dashboard-activity-chart__day"><div className="dashboard-activity-chart__bar-wrap"><span className="dashboard-activity-chart__bar" style={{ height: `${Math.max(count ? 8 : 0, (count / activityMax) * 100)}%` }} title={`${count} submissions`} /></div><span>{new Date(`${key}T00:00:00Z`).toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" })}</span><b>{count}</b></div>)}
          </div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <div className="dashboard-section-heading"><div><h2>Recurring guidance themes</h2><p>Patterns from your previous review decisions.</p></div></div>
          {personalStats?.recurring_mistakes?.length ? <div className="dashboard-mini-breakdown mt-4">
            {personalStats.recurring_mistakes.slice(0, 4).map((issue, index) => <div key={`${issue.category}-${index}`} className="dashboard-mini-breakdown__row"><span>{issue.category.replace(/_/g, " ")} <small>{issue.severity}</small></span><b>{issue.count}</b><div className="dashboard-mini-breakdown__track"><i style={{ width: `${Math.min(100, issue.count / Math.max(1, ...personalStats.recurring_mistakes.map((item) => item.count)) * 100)}%` }} /></div></div>)}
          </div> : <p className="mt-4 text-sm text-secondary">No recurring patterns yet. Review decisions will appear here as trends form.</p>}
        </div>
      </section>

      {/* Main 2-column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: My Submissions Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-stone-200">
              <div>
                <h2 className="text-lg font-bold text-stone-900">My Submissions Pipeline</h2>
                <p className="text-xs text-stone-500 mt-0.5">Track the status of your copy across pre-publication governance stages.</p>
              </div>

              {/* Filters */}
              <div className="dashboard-filters flex items-center gap-3">
                <div className="dashboard-search relative">
                  <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    aria-label="Search my submissions"
                    placeholder="Search my copy..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none w-44"
                  />
                </div>
                <select
                  aria-label="Filter my submissions by status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-xs border border-stone-300 rounded-lg px-2.5 py-1.5 bg-white text-stone-700 focus:ring-2 focus:ring-stone-900 focus:outline-none"
                >
                  <option value="all">All Statuses</option>
                  <option value="draft">Draft</option>
                  <option value="checked">Checked</option>
                  <option value="in_review">In Review</option>
                  <option value="changes_requested">Changes Requested</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>

            <SavedViews
              userId={user.id}
              role="creator"
              search={search}
              setSearch={setSearch}
              statusFilter={statusFilter}
              setStatusFilter={setStatusFilter}
            />

            {/* Submissions List */}
            {filtered.length === 0 ? (
              <div className="py-12 text-center">
                <FileText className="w-10 h-10 text-stone-300 mx-auto mb-3" />
                <p className="text-sm font-semibold text-stone-700">No submissions found</p>
                <p className="text-xs text-stone-400 mt-1">Start a new check to governance-verify your copy before publishing.</p>
                <button
                  onClick={() => navigate("/new")}
                  className="mt-4 px-4 py-2 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800"
                >
                  Create New Submission
                </button>
              </div>
            ) : (
              <div className="divide-y divide-stone-100 mt-2">
                {filtered.map((sub) => (
                  <div
                    key={sub.id}
                    className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-stone-50/60 p-2 rounded-xl transition-colors"
                  >
                    <div className="space-y-1 max-w-md">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-stone-900">{sub.title}</span>
                        <span className="text-[10px] uppercase font-bold text-stone-500 bg-stone-100 px-1.5 py-0.5 rounded border border-stone-200">
                          {sub.content_type}
                        </span>
                      </div>
                      {sub.intent && (
                        <p className="text-xs text-stone-500 line-clamp-1 italic">
                          Intent: "{sub.intent}"
                        </p>
                      )}
                      <div className="flex items-center gap-3 text-[11px] text-stone-400">
                        <span>Created {new Date(sub.created_at).toLocaleDateString()}</span>
                        <span>•</span>
                        <span className={sub.finding_count ? "text-amber-700 font-semibold" : "text-stone-400"}>
                          {sub.finding_count ? `${sub.finding_count} findings flagged` : "Clean check"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {getStatusBadge(sub.status)}

                      {sub.status === "draft" && (
                        <button
                          onClick={() => navigate(`/review/${sub.id}`)}
                          className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-semibold hover:bg-stone-800 flex items-center gap-1.5"
                        >
                          Run Check
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}

                      {(sub.status === "checked" || sub.status === "changes_requested") && (
                        <button
                          onClick={() => navigate(`/review/${sub.id}`)}
                          className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700 flex items-center gap-1.5 shadow-sm"
                        >
                          Fix Findings
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}

                      {sub.status === "in_review" && (
                        <button
                          onClick={() => navigate(`/review/${sub.id}`)}
                          className="px-3 py-1.5 rounded-lg border border-stone-300 text-stone-700 text-xs font-semibold hover:bg-stone-100"
                        >
                          View Status
                        </button>
                      )}

                      {sub.status === "approved" && (
                        <button
                          onClick={() => navigate(`/approval/${sub.id}`)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 flex items-center gap-1.5"
                        >
                          View Sign-off
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Personal Stats & Notifications */}
        <div className="space-y-6">
          {/* Notifications Feed */}
          <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
            <div className="flex items-center gap-2 pb-3 border-b border-stone-200 mb-4">
              <Bell className="w-4 h-4 text-amber-600" />
              <h3 className="text-sm font-bold text-stone-900">Notifications & Activity</h3>
            </div>
            <div className="space-y-3">
              {(personalStats?.notifications || []).map((notif, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-2.5 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-700">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                  <p className="leading-relaxed">{notif}</p>
                </div>
              ))}
              {(!personalStats?.notifications || personalStats.notifications.length === 0) && (
                <p className="text-xs text-stone-600 py-2">No new review notes or decisions.</p>
              )}
            </div>
          </div>

          {/* Recurring Mistakes & Coaching */}
          <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
            <div className="flex items-center gap-2 pb-3 border-b border-stone-200 mb-4">
              <AlertCircle className="w-4 h-4 text-orange-600" />
              <h3 className="text-sm font-bold text-stone-900">My Recurring Mistakes</h3>
            </div>
            {personalStats?.recurring_mistakes && personalStats.recurring_mistakes.length > 0 ? (
              <div className="space-y-3">
                {personalStats.recurring_mistakes.map((issue, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-orange-50/60 border border-orange-200">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold text-orange-700 bg-orange-100 px-1.5 py-0.5 rounded">
                        {issue.category} • {issue.severity}
                      </span>
                      <span className="text-xs font-bold text-orange-900">{issue.count} occurrences</span>
                    </div>
                    <p className="text-xs font-semibold text-stone-800 mt-2">{issue.issue_pattern}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-500 italic">No recurring mistakes detected. Your copy adheres closely to approved guidelines!</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
