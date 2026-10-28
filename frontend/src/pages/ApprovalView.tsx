import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { api } from "../api";
import { Submission, Finding, User } from "../types";

interface ApprovalViewProps {
  submissionId: string;
  user: User;
  navigate: (path: string) => void;
}

export const ApprovalView: React.FC<ApprovalViewProps> = ({
  submissionId,
  user,
  navigate,
}) => {
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [history, setHistory] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reviewerSignoff, setReviewerSignoff] = useState<any>(null);
  const [evidenceNotes, setEvidenceNotes] = useState("");
  const [signoffJustification, setSignoffJustification] = useState("");
  const [checklist, setChecklist] = useState({ claims_verified: false, facts_current: false, accessibility_reviewed: false, legal_wording_reviewed: false });

  // Approval modal
  const [decisionModal, setDecisionModal] = useState<"approved" | "changes_requested" | "rejected" | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const sub = await api.getSubmission(submissionId);
      setSubmission(sub);
      const fList = await api.getFindings(submissionId);
      setFindings(fList);
      const hist = await api.getHistory(submissionId);
      setHistory(hist);
      setReviewerSignoff(await api.getReviewerSignoff(submissionId));
    } catch (err) {
      console.error("Failed to load approval view:", err);
      setLoadError(err instanceof Error ? err.message : "Unable to load approval details.");
      setSubmission(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [submissionId]);

  const handleDecision = async () => {
    if (!decisionModal) return;
    setSubmitting(true);
    try {
      if (decisionModal === "approved") {
        await api.approveSubmission(submissionId, decisionNote);
      } else {
        await api.rejectSubmission(submissionId, decisionModal, decisionNote);
      }
      setDecisionModal(null);
      setDecisionNote("");
      await loadData();
    } catch (err: any) {
      alert(`Error submitting decision: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReviewerSignoff = async () => {
    setSubmitting(true);
    try {
      await api.submitReviewerSignoff(submissionId, checklist, evidenceNotes, signoffJustification);
      await loadData();
      alert("Reviewer compliance sign-off recorded. A different manager must issue final approval.");
    } catch (err: any) { alert(`Unable to record sign-off: ${err.message}`); }
    finally { setSubmitting(false); }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-stone-400 text-xs animate-pulse">
        Loading approval dossier...
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center text-xs text-stone-600">
        <p role={loadError ? "alert" : undefined}>{loadError || "Submission not found."}</p>
        {loadError && <button onClick={loadData} className="mt-3 underline font-semibold">Try again</button>}
      </div>
    );
  }

  const openFindings = findings.filter((f) => f.status === "open");
  const highRisk = findings.some((finding) =>
    finding.needs_human || finding.severity === "critical" || finding.severity === "major" || finding.category === "unsupported_claim"
  );
  const isInReview = submission.status === "in_review";
  const canManagerAct = user.role === "manager" && isInReview && (!highRisk || reviewerSignoff?.signed_off) && reviewerSignoff?.reviewer_id !== user.id;
  const canReviewerSignOff = user.role === "reviewer" && user.id === submission.assigned_to_id && isInReview && highRisk;
  const latestVersion = submission.versions?.length
    ? submission.versions[submission.versions.length - 1]
    : null;
  const initialVersion = submission.versions?.length
    ? submission.versions[0]
    : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-stone-200">
        <div>
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-2 font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-stone-900">Governance Review & Sign-Off</h1>
            <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-300">
              {submission.status}
            </span>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            Submission: <span className="font-semibold text-stone-800">{submission.title}</span> • Creator: {submission.creator?.name}
          </p>
        </div>

        {/* Manager/Reviewer Action Buttons */}
        <div className="flex items-center gap-2">
          {canManagerAct && <button
            onClick={() => setDecisionModal("approved")}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center gap-1.5"
          >
            <ShieldCheck className="w-4 h-4" />
            Final Manager Approval
          </button>}
          {canManagerAct && <>
          <button
            onClick={() => setDecisionModal("changes_requested")}
            className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center gap-1.5"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            Request Changes
          </button>
          <button
            onClick={() => setDecisionModal("rejected")}
            className="px-3.5 py-2 border border-rose-300 text-rose-700 hover:bg-rose-50 rounded-lg text-xs font-semibold"
          >
            Reject
          </button>
          </>}
        </div>
      </div>

      {canReviewerSignOff && !reviewerSignoff?.signed_off && <section className="bg-white border border-emerald-200 rounded-2xl p-5 space-y-4">
        <div><h2 className="font-bold text-sm">Reviewer sign-off checklist</h2><p className="text-xs text-stone-500">Complete each item after reviewing the cited source and retrieved evidence. A manager will make the final decision.</p></div>
        <div className="grid sm:grid-cols-2 gap-2 text-xs">{([["claims_verified", "Claims verified"], ["facts_current", "Facts are current"], ["accessibility_reviewed", "Accessibility reviewed"], ["legal_wording_reviewed", "Legal wording reviewed"]] as const).map(([key, label]) => <label key={key} className="flex gap-2 items-center p-2 bg-stone-50 rounded"><input type="checkbox" checked={checklist[key]} onChange={e => setChecklist({...checklist, [key]: e.target.checked})}/>{label}</label>)}</div>
        <label className="block text-xs font-semibold">Evidence notes<textarea className="mt-1 w-full border rounded-lg p-2" rows={3} value={evidenceNotes} onChange={e => setEvidenceNotes(e.target.value)} placeholder="Record source evidence reviewed and any relevant context." /></label>
        <label className="block text-xs font-semibold">Sign-off justification<textarea className="mt-1 w-full border rounded-lg p-2" rows={2} value={signoffJustification} onChange={e => setSignoffJustification(e.target.value)} placeholder="Explain the compliance review outcome." /></label>
        <button disabled={submitting || !Object.values(checklist).every(Boolean) || evidenceNotes.trim().length < 5 || signoffJustification.trim().length < 5} onClick={handleReviewerSignoff} className="px-4 py-2 bg-emerald-700 text-white rounded-lg text-xs font-semibold disabled:opacity-40">Record reviewer sign-off</button>
      </section>}
      {highRisk && reviewerSignoff?.signed_off && <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900">Reviewer sign-off recorded. Final approval is available to a different manager. <span className="block mt-1">Evidence: {reviewerSignoff.evidence_notes}</span></div>}

      {/* Unresolved findings alert */}
      {openFindings.length > 0 && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900">
            <p className="font-bold">
              There are {openFindings.length} open finding{openFindings.length > 1 ? "s" : ""} on this submission.
            </p>
            <p className="mt-0.5 text-amber-800">
              Reviewers are advised to verify that all promotional claims and factual figures are grounded in approved brand kit sources before issuing final sign-off.
            </p>
          </div>
        </div>
      )}

      {/* Content Versions Comparison */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Version 1 (Original Draft) */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-stone-100">
            <span className="font-bold text-xs uppercase tracking-wider text-stone-700">
              Original Draft (v1)
            </span>
            <span className="text-[11px] text-stone-400">
              {initialVersion ? new Date(initialVersion.created_at).toLocaleString() : ""}
            </span>
          </div>
          <div className="whitespace-pre-wrap font-serif text-xs leading-relaxed text-stone-600 bg-stone-50 p-4 rounded-xl min-h-[220px]">
            {initialVersion?.text || "No draft content"}
          </div>
        </div>

        {/* Latest Version (Post-Fixes) */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-stone-100">
            <span className="font-bold text-xs uppercase tracking-wider text-stone-700 flex items-center gap-1.5">
              <span>Current Revision (v{latestVersion?.version_no})</span>
              <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-semibold">
                Latest
              </span>
            </span>
            <span className="text-[11px] text-stone-400">
              {latestVersion ? new Date(latestVersion.created_at).toLocaleString() : ""}
            </span>
          </div>
          <div className="whitespace-pre-wrap font-serif text-xs leading-relaxed text-stone-900 bg-stone-50 p-4 rounded-xl min-h-[220px]">
            {latestVersion?.text || "No revision content"}
          </div>
        </div>
      </div>

      {/* Revision & Approval History Timeline */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
        <h3 className="font-bold text-stone-900 text-sm flex items-center gap-2">
          <Clock className="w-4 h-4 text-stone-500" />
          Audit Trail & Governance Approvals
        </h3>

        <div className="space-y-3">
          {history?.approvals?.length === 0 && history?.audit_logs?.length === 0 ? (
            <p className="text-xs text-stone-400 italic">No governance events logged yet.</p>
          ) : (
            <div className="divide-y divide-stone-100">
              {history?.approvals?.map((a: any) => (
                <div key={a.id} className="py-3 flex items-start justify-between text-xs">
                  <div>
                    <span className="font-semibold text-stone-900">
                      {a.user_name} ({a.user_role}):
                    </span>{" "}
                    <span className="font-bold uppercase text-[11px] px-1.5 py-0.2 rounded bg-stone-100 text-stone-800">
                      {a.decision}
                    </span>
                    {a.note && <p className="text-stone-600 mt-1 italic">"{a.note}"</p>}
                  </div>
                  <span className="text-[11px] text-stone-400">
                    {new Date(a.created_at).toLocaleString()}
                  </span>
                </div>
              ))}

              {history?.audit_logs?.map((al: any) => (
                <div key={al.id} className="py-2.5 flex items-center justify-between text-[11px] text-stone-500">
                  <span>
                    <span className="font-medium text-stone-700">{al.user_name || "System"}</span>: {al.action}
                  </span>
                  <span>{new Date(al.created_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Decision Modal */}
      {decisionModal && (
        <div className="fixed inset-0 z-50 bg-stone-950/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-stone-200 shadow-xl space-y-4">
            <h3 className="font-bold text-stone-900 text-sm capitalize">
              {decisionModal.replace("_", " ")} Submission
            </h3>
            <p className="text-xs text-stone-500">
              Provide a compliance note or feedback for the creator team:
            </p>

            <textarea
              rows={4}
              placeholder="e.g. Sourcing claims verified against 2024 organic certificates. Approved for regional distribution."
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              className="w-full p-3 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setDecisionModal(null)}
                className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleDecision}
                disabled={submitting}
                className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Confirm Decision"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
