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
import { Submission, Finding, SubmissionStatus, User } from "../../types";
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
  const [followupAction, setFollowupAction] = useState<"request_evidence" | "propose_fact" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [needsSignoff, setNeedsSignoff] = useState<Submission[]>([]);
  const [metrics, setMetrics] = useState<{ average_turnaround_hours: number | null; confirmed: number; dismissed: number; overturned_rate: number } | null>(null);
  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const subs = await api.getSubmissions();
      // The API returns only work assigned to this reviewer or escalated submissions.
      setAssignedSubmissions(subs);
      setMetrics(await api.getReviewerMetrics());

      // Collect escalated findings from assigned submissions
      const findingsList: Finding[] = [];
      for (const sub of subs.filter((item) => item.assigned_to_id === user.id || item.status === "in_review").slice(0, 50)) {
        try {
          const fList = await api.getFindings(sub.id);
          const escalated = fList.filter((f) => f.needs_human || f.severity === "critical" || f.severity === "major" || f.category === "unsupported_claim" || /expired|outdated/i.test(f.issue));
          findingsList.push(...escalated);
        } catch {
          // ignore individual finding load errors
        }
      }
      setEscalatedFindings(findingsList);
      const inReviewAssignments = subs.filter((sub) => sub.assigned_to_id === user.id && sub.status === "in_review");
      const signoffs = await Promise.all(inReviewAssignments.map((sub) => api.getReviewerSignoff(sub.id)));
      setNeedsSignoff(inReviewAssignments.filter((_, index) => !signoffs[index]?.signed_off));
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
      setFollowupAction(null);
      loadData();
    } catch (err: any) {
      showToast(err.message || "Action failed", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFollowupAction = async () => {
    if (!selectedFinding || !followupAction) return;
    if (justification.trim().length < 5) {
      showToast("Add at least five characters describing the requested evidence or proposed fact.", "error");
      return;
    }
    try {
      setSubmitting(true);
      await api.createReviewerFollowup(selectedFinding.submission_id, selectedFinding.id, followupAction, justification.trim());
      showToast(followupAction === "request_evidence" ? "Evidence request sent to the creator." : "Fact proposal sent to the admin queue.", "success");
      setSelectedFinding(null);
      setJustification("");
      setFollowupAction(null);
      await loadData();
    } catch (err: any) {
      showToast(err.message || "Could not create the reviewer follow-up.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const pipelineStatuses: SubmissionStatus[] = ["draft", "checked", "in_review", "changes_requested", "approved", "rejected"];
  const pendingFindings = escalatedFindings.filter((finding) => finding.status === "open" && !finding.historical);
  const claimQueue = pendingFindings.filter((finding) => finding.category === "unsupported_claim");
  const factQueue = pendingFindings.filter((finding) => finding.category === "factual_accuracy");

  if (loading) {
    return (
      <div className="dashboard-workspace dashboard-workspace--reviewer max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
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
    <div className="dashboard-workspace dashboard-workspace--reviewer max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <section className="dashboard-hero dashboard-hero--reviewer" aria-labelledby="reviewer-dashboard-title">
        <div className="dashboard-hero__copy">
          <div className="dashboard-hero__eyebrow"><ShieldCheck className="w-4 h-4" /> Compliance review <span aria-hidden="true">·</span> Reviewer</div>
          <h1 id="reviewer-dashboard-title" className="text-2xl sm:text-3xl font-extrabold tracking-tight">Compliance Desk</h1>
          <p>Verify risky claims and facts against approved evidence, then sign off assigned compliance work.</p>
        </div>
        <div className="dashboard-hero__actions">
        <button
          onClick={() => navigate("/sources")}
          className="dashboard-secondary-action"
        >
          <BookOpen className="w-4 h-4" />
          View Approved Sources (Read-Only)
        </button>
        </div>
      </section>

      {/* KPI Cards */}
      <div className="dashboard-kpis dashboard-kpis--reviewer grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Needs your sign-off</p>
            <p className="text-2xl font-black text-stone-900 mt-1">{needsSignoff.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Assigned high-risk work awaiting review</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileCheck className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">My review metrics</p>
          <div className="dashboard-reviewer-metrics mt-3 text-xs">
            <span><small>Turnaround</small><b>{metrics?.average_turnaround_hours == null ? "—" : `${metrics.average_turnaround_hours}h`}</b></span>
            <span><small>Confirmed</small><b>{metrics?.confirmed ?? 0}</b></span><span><small>Dismissed</small><b>{metrics?.dismissed ?? 0}</b></span>
            <span><small>Overturned</small><b>{metrics?.overturned_rate ?? 0}%</b></span>
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Escalated claims</p>
            <p className="text-2xl font-black text-amber-600 mt-1">{claimQueue.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Claims awaiting compliance review</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="dashboard-kpi bg-white p-5 rounded-2xl border border-stone-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Facts and prices to verify</p>
            <p className="text-2xl font-black text-amber-600 mt-1">{factQueue.length}</p>
            <p className="text-[11px] text-stone-400 mt-1">Approved values need verification</p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 space-y-3" aria-labelledby="reviewer-signoff-queue">
        <div><h2 id="reviewer-signoff-queue" className="text-sm font-bold text-emerald-950">Needs your sign-off ({needsSignoff.length})</h2><p className="text-xs text-emerald-900">Assigned high-risk submissions need your completed compliance checklist before a manager can approve.</p></div>
        {needsSignoff.length ? needsSignoff.map((submission) => (
          <div key={submission.id} className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-white p-3">
            <div className="min-w-0"><p className="truncate text-sm font-semibold text-stone-900">{submission.title}</p><p className="text-xs text-stone-600">Why: assigned high-risk copy is awaiting your version-specific sign-off.</p></div>
            <button type="button" onClick={() => navigate(`/approval/${submission.id}`)} className="dashboard-secondary-action">Review</button>
          </div>
        )) : <p className="text-xs text-emerald-900">No assigned submissions currently need sign-off.</p>}
      </section>

      <section className="dashboard-pipeline" aria-label="Assigned submissions by status">
        <div className="dashboard-section-heading">
          <div><h2>Assigned work by stage</h2><p>See where your assigned and escalated work sits in the review process.</p></div>
          <span className="dashboard-section-note">{assignedSubmissions.length} submissions</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          {pipelineStatuses.map((status) => <div key={status} className="dashboard-pipeline__item p-4 rounded-xl border" aria-label={`${status.replace("_", " ")}: ${assignedSubmissions.filter((submission) => submission.status === status).length}`}>
            <span className="text-[10px] uppercase font-bold tracking-wider">{status.replace("_", " ")}</span>
            <span className="block text-2xl font-black mt-1">{assignedSubmissions.filter((submission) => submission.status === status).length}</span>
          </div>)}
        </div>
      </section>

      {/* Side-by-Side Claim & Citation Inspection Panel */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-6">
        <div>
          <h2 className="text-lg font-bold text-stone-900">Escalated claims ({claimQueue.length})</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            Inspect flagged health, sourcing, or factual claims side-by-side with approved brand facts. Provide written justification to confirm or dismiss.
          </p>
        </div>

        {claimQueue.length === 0 ? (
          <div className="py-8 text-center bg-stone-50 rounded-xl border border-dashed border-stone-200">
            <ShieldCheck className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-semibold text-stone-800">No Escalated Findings Currently Pending</p>
            <p className="text-xs text-stone-500 mt-0.5">All claims are either verified or have been resolved by authors.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {claimQueue.map((finding) => (
              (() => {
                const version = assignedSubmissions.find((submission) => submission.id === finding.submission_id)?.versions?.slice(-1)[0];
                const claimExcerpt = version?.text?.slice(Math.max(0, finding.span_start || 0), Math.min(version.text.length, finding.span_end || (finding.span_start || 0) + 300));
                return (
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
                    <p className="text-[11px] font-bold text-stone-500 uppercase tracking-wider">Cited claim excerpt</p>
                    <p className="break-words text-sm text-stone-800 bg-stone-50 p-2.5 rounded border border-stone-200">
                      {claimExcerpt || finding.issue}
                    </p>
                  </div>

                  <div className="bg-emerald-50/60 p-4 rounded-xl border border-emerald-200 space-y-1">
                    <p className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">Retrieved evidence / approved source</p>
                    <p className="text-xs text-emerald-900 italic bg-white/80 p-2.5 rounded border border-emerald-200/80">
                      "{finding.source_quote || "Approved Brand Fact / Source Note"}"
                    </p>
                  </div>
                </div>

                {/* Justification & Action */}
                {selectedFinding?.id === finding.id ? (
                  <div className="p-4 bg-white rounded-xl border border-stone-300 space-y-3">
                    <label htmlFor="reviewer-escalation-justification" className="block text-xs font-bold text-stone-800">
                      {followupAction === "request_evidence" ? "Evidence request for creator" : followupAction === "propose_fact" ? "Proposed fact and source for admin" : "Compliance justification note"} <span className="text-rose-600">*</span>
                    </label>
                    <textarea
                      id="reviewer-escalation-justification"
                      value={justification}
                      onChange={(e) => setJustification(e.target.value)}
                      placeholder={followupAction === "request_evidence" ? "Specify the evidence the creator must provide…" : followupAction === "propose_fact" ? "Describe the approved value, unit, expiry, and supporting source…" : "Explain why this escalated claim is being confirmed or dismissed against approved evidence…"}
                      rows={2}
                      className="w-full text-xs p-2.5 border border-stone-300 rounded-lg focus:ring-2 focus:ring-emerald-600 focus:outline-none"
                    />
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => { setSelectedFinding(null); setFollowupAction(null); }}
                        className="px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900"
                      >
                        Cancel
                      </button>
                      {followupAction ? (
                        <button type="button" disabled={submitting} onClick={handleFollowupAction} className="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs disabled:opacity-50">
                          {submitting ? "Sending…" : followupAction === "request_evidence" ? "Send evidence request" : "Send fact proposal"}
                        </button>
                      ) : (
                        <>
                          <button
                            disabled={submitting}
                            onClick={() => handleEscalatedAction("dismiss")}
                            className="px-3.5 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 font-bold text-xs flex items-center gap-1"
                          >
                            <X className="w-3.5 h-3.5" />
                            Dismiss finding
                          </button>
                          <button
                            disabled={submitting}
                            onClick={() => handleEscalatedAction("confirm")}
                            className="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs flex items-center gap-1 shadow-sm"
                          >
                            <Check className="w-3.5 h-3.5" />
                            Confirm violation
                          </button>
                        </>
                      )}
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
                        setFollowupAction(null);
                      }}
                      className="px-4 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-bold rounded-lg shadow-sm"
                    >
                      Provide Compliance Verdict
                    </button>
                    <button type="button" onClick={() => { setSelectedFinding(finding); setJustification(""); setFollowupAction("request_evidence"); }} className="px-3 py-1.5 text-xs font-semibold text-stone-700 hover:text-stone-950">Request evidence</button>
                    <button type="button" onClick={() => { setSelectedFinding(finding); setJustification(""); setFollowupAction("propose_fact"); }} className="px-3 py-1.5 text-xs font-semibold text-stone-700 hover:text-stone-950">Propose approved fact</button>
                  </div>
                )}
              </div>
                );
              })()
            ))}
          </div>
        )}
      </div>

      <section className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-4" aria-labelledby="reviewer-facts-queue">
        <div><h2 id="reviewer-facts-queue" className="text-lg font-bold text-stone-900">Facts and prices to verify ({factQueue.length})</h2><p className="text-xs text-stone-500">Each item is escalated because a factual value may be wrong, expired, or unsupported.</p></div>
        {factQueue.length ? factQueue.map((finding) => {
          const submission = assignedSubmissions.find((item) => item.id === finding.submission_id);
          const version = submission?.versions?.find((item) => item.id === finding.version_id);
          const yourText = version && finding.span_start != null && finding.span_end != null
            ? version.text.slice(finding.span_start, finding.span_end)
            : null;
          return (
            <div key={finding.id} className="rounded-xl border border-stone-200 p-4">
              <p className="text-xs font-semibold text-stone-900">{finding.issue}</p>
              <dl className="mt-3 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                <div className="min-w-0"><dt className="font-semibold text-stone-600">Your text</dt><dd className="mt-1 break-words text-stone-800">{yourText || "Exact text span unavailable; inspect the source."}</dd></div>
                <div className="min-w-0"><dt className="font-semibold text-stone-600">Approved fact / source</dt><dd className="mt-1 break-words text-stone-800">{finding.source_quote || "No approved fact is cited; verify with the creator or Admin."}</dd></div>
                {finding.suggested_rewrite && <div className="min-w-0 sm:col-span-2"><dt className="font-semibold text-emerald-800">Proposed correction</dt><dd className="mt-1 break-words text-emerald-950">{finding.suggested_rewrite}</dd></div>}
              </dl>
              <button type="button" onClick={() => navigate(`/review/${finding.submission_id}`)} className="mt-3 dashboard-secondary-action">Inspect item and evidence</button>
            </div>
          );
        }) : <p className="text-sm text-stone-600">No facts or prices are waiting for verification.</p>}
      </section>

      {/* Assigned and escalated submissions */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-stone-900">Assigned and Escalated Submissions</h2>
        <div className="divide-y divide-stone-100">
          {assignedSubmissions.map((sub) => (
            (() => {
              const canSignOff = needsSignoff.some((submission) => submission.id === sub.id);
              return (
            <div key={sub.id} className="py-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-bold text-stone-900">{sub.title}</p>
                {sub.confidential && <p className="text-xs font-semibold text-purple-800">Confidential · external AI blocked</p>}
                <p className="text-xs text-stone-500 mt-0.5">
                  Author: {sub.creator?.name} • Status: <span className="uppercase font-bold">{sub.status}</span>
                </p>
                {sub.status === "in_review" && sub.assigned_to_id === user.id && (
                  <p className={`text-xs font-semibold mt-1 ${sub.is_overdue ? "text-red-700" : "text-stone-500"}`}>
                    {sub.is_overdue ? "Overdue • " : sub.assignment_due_at ? `Due ${new Date(sub.assignment_due_at).toLocaleString()}` : "No due date set"}
                  </p>
                )}
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
