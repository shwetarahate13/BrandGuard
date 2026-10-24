import React, { useEffect, useState } from "react";
import {
  PlusCircle,
  FileText,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Search,
  Filter,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { api } from "../api";
import { Submission, SubmissionStatus, User } from "../types";

interface DashboardProps {
  user: User;
  navigate: (path: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ user, navigate }) => {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadSubmissions = async () => {
    try {
      setLoading(true);
      const data = await api.getSubmissions();
      setSubmissions(data);
    } catch (err) {
      console.error("Failed to load submissions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSubmissions();
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
      draft: { label: "Draft", color: "bg-stone-100 text-stone-700 border-stone-300", icon: FileText },
      checked: { label: "Checked", color: "bg-blue-50 text-blue-700 border-blue-200", icon: CheckCircle },
      in_review: { label: "In Review", color: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock },
      changes_requested: { label: "Changes Requested", color: "bg-orange-50 text-orange-700 border-orange-200", icon: AlertTriangle },
      approved: { label: "Approved", color: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: ShieldCheck },
      rejected: { label: "Rejected", color: "bg-rose-50 text-rose-700 border-rose-200", icon: XCircle },
    };
    const conf = map[status] || map.draft;
    const Icon = conf.icon;
    return (
      <span className={`inline-flex items-center gap-1 text-[11px] font-semibold uppercase px-2 py-0.5 rounded-full border ${conf.color}`}>
        <Icon className="w-3 h-3" />
        {conf.label}
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Content Governance Dashboard</h1>
          <p className="text-xs text-stone-500 mt-1">
            Review submissions against approved brand guidelines, facts, and assets before publication.
          </p>
        </div>

        {["creator", "manager", "admin"].includes(user.role) && (
          <button
            onClick={() => navigate("/new")}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-all self-start sm:self-auto"
          >
            <PlusCircle className="w-4 h-4 text-amber-400" />
            New Brand Check
          </button>
        )}
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by title or intent..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
          {[
            { id: "all", label: "All" },
            { id: "checked", label: "Checked" },
            { id: "in_review", label: "In Review" },
            { id: "changes_requested", label: "Changes Requested" },
            { id: "approved", label: "Approved" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                statusFilter === tab.id
                  ? "bg-stone-900 text-white"
                  : "text-stone-600 hover:bg-stone-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Submissions List */}
      {loading ? (
        <div className="text-center py-16 text-stone-400 text-xs animate-pulse">
          Loading governance submissions...
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
          <FileText className="w-10 h-10 text-stone-300 mx-auto mb-3" />
          <h3 className="font-semibold text-stone-800 text-sm">No Submissions Found</h3>
          <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
            {search || statusFilter !== "all"
              ? "No submissions matched the selected filters."
              : "Create your first pre-publication check to test copy against brand guidelines."}
          </p>
          {["creator", "manager", "admin"].includes(user.role) && (
            <button
              onClick={() => navigate("/new")}
              className="mt-4 px-4 py-2 bg-stone-900 text-white rounded-lg text-xs font-semibold"
            >
              Start New Check
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4">
          {filtered.map((item) => (
            <div
              key={item.id}
              className="bg-white border border-stone-200 hover:border-amber-400/80 rounded-xl p-5 shadow-sm transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3
                    onClick={() => navigate(`/review/${item.id}`)}
                    className="font-bold text-stone-900 hover:text-amber-800 text-sm cursor-pointer transition-colors"
                  >
                    {item.title}
                  </h3>
                  {getStatusBadge(item.status)}
                  {item.finding_count !== undefined && item.finding_count > 0 && (
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                      {item.finding_count} issue{item.finding_count > 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {item.intent && (
                  <p className="text-xs text-stone-600 line-clamp-1">
                    <span className="font-semibold text-stone-700">Intent:</span> {item.intent}
                  </p>
                )}

                <div className="text-[11px] text-stone-400 flex items-center gap-3">
                  <span>Author: {item.creator?.name || "Team Member"}</span>
                  <span>•</span>
                  <span>Created: {new Date(item.created_at).toLocaleDateString()}</span>
                  <span>•</span>
                  <span className="uppercase text-[10px]">{item.content_type}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 md:pt-0 border-t md:border-t-0 border-stone-100 shrink-0">
                <button
                  onClick={() => navigate(`/review/${item.id}`)}
                  className="px-3.5 py-1.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center gap-1.5"
                >
                  Review Findings
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>

                {["manager", "reviewer", "admin"].includes(user.role) && (
                  <button
                    onClick={() => navigate(`/approval/${item.id}`)}
                    className="px-3 py-1.5 border border-stone-300 hover:bg-stone-50 text-stone-700 rounded-lg text-xs font-medium"
                  >
                    Approval View
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
