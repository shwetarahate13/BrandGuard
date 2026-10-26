import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  FileCheck,
  Check,
  X,
  Search,
  ArrowRight,
  BookOpen,
  MessageSquare,
} from "lucide-react";
import { api } from "../../api";
import { Submission, Finding, User } from "../../types";
import { Skeleton } from "../Skeleton";
import { useToast } from "../Toast";

interface ReviewerDashboardProps {
  user: User;
  navigate: (path: string) => void;
}

export const ReviewerDashboard: React.FC<ReviewerDashboardProps> = ({ user, navigate }) => {
  const [assignedSubmissions, setAssignedSubmissions] = useState<Submission[]>([]);
  const [escalatedFindings, setEscalatedFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [justification, setJustification] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const subs = await api.getSubmissions();
      // The API returns only work assigned to this reviewer or escalated submissions.
      setAssignedSubmissions(subs);

      // Collect escalated findings from assigned submissions
      const findingsList: Finding[] = [];
      for (const sub of subs.slice(0, 10)) {
        try {
          const fList = await api.getFindings(sub.id);
          const escalated = fList.filter((f) => f.needs_human || f.severity === "critical" || f.category === "unsupported_claim");
          findingsList.push(...escalated);
        } catch {
          // ignore individual finding load errors
        }
      }
      setEscalatedFindings(findingsList);
    } catch (err: any) {
      showToast(err.message || "Failed to load Compliance Desk data", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleEscalatedAction = async (action: "confirm" | "dismiss") => {
    if (!selectedFinding) return;
    if (!justification.trim() || justification.trim().length < 5) {
      showToast("A compliance justification note (minimum 5 characters) is required.", "error");
      return;
    }

    try {
      setSubmitting(true);
      await api.reviewEscalatedFinding(selectedFinding.id, action, justification.trim());
      showToast(
        action === "confirm"
          ? "Escalated finding confirmed with compliance record"
          : "Escalated finding dismissed with explanation",
        "success"
      );
      setSelectedFinding(null);
      setJustification("");
      loadData();
    } catch (err: any) {
      showToast(err.message || "Action failed", "error");
    } finally {
      setSubmitting(false);
    }
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
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-gradient-to-r from-emerald-950 via-stone-900 to-stone-900 text-white p-6 sm:p-8 rounded-3xl shadow-xl border border-emerald-900/40">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-400/20 border border-emerald-400/30 text-emerald-300 text-xs font-semibold mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            Compliance & Regulatory Sign-Off Desk
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">Compliance Desk</h1>
          <p className="text-stone-300 text-xs sm:text-sm mt-1 max-w-xl">
            Inspect escalated claims side by side against certified brand facts, verify citations, and issue regulatory sign-offs.
          </p>
        </div>
        <button
          onClick={() => navigate("/sources")}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-600 font-semibold text-xs transition-colors"
        >
          <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
          View Approved Sources (Read-Only)
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Assigned to Me</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{assignedSubmissions.filter((submission) => submission.assigned_to_id === user.id).length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Directly allocated submissions</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileCheck className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Escalated Findings</p>
            <p className="text-2xl font-black text-amber-600 mt-1">{escalatedFindings.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Needs human / high severity / claims</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Compliance Role</p>
            <p className="text-sm font-bold text-emerald-800 mt-1">Certified Compliance Authority</p>
            <p className="text-[11px] text-stone-400 mt-1">Sign-off on high-risk copy</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Side-by-Side Claim & Citation Inspection Panel */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
        <div>
          <h2 className="text-lg font-bold text-stone-900">Escalated Compliance Queue</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Inspect flagged health, sourcing, or factual claims side-by-side with approved brand facts. Provide written justification to confirm or dismiss.
          </p>
        </div>

        {escalatedFindings.length === 0 ? (
          <div className="py-8 text-center bg-stone-50 rounded-xl border border-dashed border-stone-200">
            <ShieldCheck className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-semibold text-stone-800">No Escalated Findings Currently Pending</p>
            <p className="text-xs text-stone-500 mt-0.5">All claims are either verified or have been resolved by authors.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {escalatedFindings.map((finding) => (
              <div
                key={finding.id}
                className="p-5 rounded-2xl border border-stone-200 hover:border-emerald-300 bg-stone-50/50 transition-all space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-stone-200/60 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-bold text-rose-800 bg-rose-100 px-2 py-0.5 rounded-full border border-rose-200">
                      {finding.category} • {finding.severity}
                    </span>
                    <span className="text-xs font-bold text-stone-900">{finding.issue}</span>
                  </div>
                  <span className="text-[11px] font-semibold text-stone-500">
                    Status: <strong className="text-stone-800">{finding.status}</strong>
                  </span>
                </div>

                {/* Side-by-side: Content Claim vs Cited Source Quote */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-white p-4 rounded-xl border border-stone-200 space-y-1">
                    <p className="text-[11px] font-bold text-stone-500 uppercase tracking-wider">Suggested Fix / Rewording</p>
                    <p className="text-xs font-mono text-stone-800 bg-stone-50 p-2.5 rounded border border-stone-200">
                      {finding.suggested_rewrite || "Flagged for manual compliance verification"}
                    </p>
                  </div>

                  <div className="bg-emerald-50/60 p-4 rounded-xl border border-emerald-200 space-y-1">
                    <p className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">Certified Grounded Truth (Source Quote)</p>
                    <p className="text-xs text-emerald-950 italic bg-white/80 p-2.5 rounded border border-emerald-200/80">
                      "{finding.source_quote || "Approved Brand Fact / Source Note"}"
                    </p>
                  </div>
                </div>

                {/* Justification & Action */}
                {selectedFinding?.id === finding.id ? (
                  <div className="p-4 bg-white rounded-xl border border-stone-300 space-y-3">
                    <label className="block text-xs font-bold text-stone-800">
                      Compliance Justification Note <span className="text-rose-600">*</span>
                    </label>
                    <textarea
                      value={justification}
                      onChange={(e) => setJustification(e.target.value)}
                      placeholder="Explain why this escalated claim is being confirmed or dismissed against regulatory guidelines..."
                      rows={2}
                      className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-emerald-600 focus:outline-none"
                    />
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setSelectedFinding(null)}
                        className="px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900"
                      >
                        Cancel
                      </button>
                      <button
                        disabled={submitting}
                        onClick={() => handleEscalatedAction("dismiss")}
                        className="px-3.5 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 font-bold text-xs flex items-center gap-1"
                      >
                        <X className="w-3.5 h-3.5" />
                        Dismiss Finding
                      </button>
                      <button
                        disabled={submitting}
                        onClick={() => handleEscalatedAction("confirm")}
                        className="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center gap-1 shadow-sm"
                      >
                        <Check className="w-3.5 h-3.5" />
                        Confirm Finding
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => navigate(`/review/${finding.submission_id}`)}
                      className="px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900 flex items-center gap-1"
                    >
                      Inspect Full Document
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setSelectedFinding(finding);
                        setJustification("");
                      }}
                      className="px-4 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-bold rounded-lg shadow-sm"
                    >
                      Provide Compliance Verdict
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Assigned and escalated submissions */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-stone-900">Assigned and Escalated Submissions</h2>
        <div className="divide-y divide-stone-100">
          {assignedSubmissions.map((sub) => (
            (() => {
              const canSignOff = sub.assigned_to_id === user.id && sub.status === "in_review" && escalatedFindings.some((finding) => finding.submission_id === sub.id);
              return (
            <div key={sub.id} className="py-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-bold text-stone-900">{sub.title}</p>
                <p className="text-xs text-stone-500 mt-0.5">
                  Author: {sub.creator?.name} • Status: <span className="uppercase font-bold">{sub.status}</span>
                </p>
              </div>
              <button
                onClick={() => navigate(canSignOff ? `/approval/${sub.id}` : `/review/${sub.id}`)}
                className={`px-3.5 py-1.5 rounded-lg ${canSignOff ? "bg-emerald-700 hover:bg-emerald-800 text-white" : "bg-stone-100 hover:bg-stone-200 text-stone-800"} text-xs font-bold inline-flex items-center gap-1.5`}
              >
                {canSignOff ? "Sign Off High-Risk Copy" : "Inspect Submission"}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
              );
            })()
          ))}
          {assignedSubmissions.length === 0 && <p className="py-6 text-center text-sm text-stone-600">No assigned or escalated submissions.</p>}
        </div>
      </div>
    </div>
  );
};
