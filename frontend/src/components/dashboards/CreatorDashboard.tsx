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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-gradient-to-r from-stone-900 to-stone-800 text-white p-6 sm:p-8 rounded-3xl shadow-xl border border-stone-700">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-400/10 border border-amber-400/30 text-amber-300 text-xs font-semibold mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            Creator Workspace • My Work
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">Welcome, {user.name}</h1>
          <p className="text-stone-300 text-xs sm:text-sm mt-1 max-w-xl">
            Pre-publication governance workspace. Review your draft copy, fix flagged guideline findings, and resubmit for brand manager sign-off.
          </p>
        </div>
        <button
          onClick={() => navigate("/new")}
          className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-sm shadow-lg hover:shadow-amber-500/20 transition-all focus:ring-2 focus:ring-amber-300 focus:outline-none"
        >
          <PlusCircle className="w-4 h-4" />
          New Content Check
        </button>
      </div>

      {/* Creator Personal KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">My Submissions</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{personalStats?.total_submissions ?? submissions.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Total pieces created</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Fix Acceptance Rate</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{personalStats?.acceptance_rate ?? 0}%</p>
            <p className="text-[11px] text-emerald-600 font-semibold mt-1">Intent-aligned suggestions</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
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

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
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
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search my copy..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:ring-2 focus:ring-stone-900 focus:outline-none w-44"
                  />
                </div>
                <select
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
