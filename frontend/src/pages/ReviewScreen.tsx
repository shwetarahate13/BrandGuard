import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  Edit2,
  ShieldCheck,
  Send,
  MessageSquare,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  FileText,
} from "lucide-react";
import { api } from "../api";
import { Submission, Finding, User } from "../types";
import { DiffViewer } from "../components/DiffViewer";

const SourceMediaViewer = React.lazy(() =>
  import("../components/SourceMediaViewer").then((module) => ({ default: module.SourceMediaViewer })),
);

interface ReviewScreenProps {
  submissionId: string;
  user: User;
  navigate: (path: string) => void;
}

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  submissionId,
  user,
  navigate,
}) => {
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);

  // Edit modal state
  const [editingFinding, setEditingFinding] = useState<Finding | null>(null);
  const [editText, setEditText] = useState("");

  // Dispute modal state
  const [disputingFinding, setDisputingFinding] = useState<Finding | null>(null);
  const [disputeReason, setDisputeReason] = useState("");

  // Comment input
  const [newComment, setNewComment] = useState("");
  const [comments, setComments] = useState<any[]>([]);

  // Expanded sources state
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [sourceRetry, setSourceRetry] = useState(0);

  const loadData = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const sub = await api.getSubmission(submissionId);
      setSubmission(sub);
      const fList = await api.getFindings(submissionId);
      setFindings(fList);

      const hist = await api.getHistory(submissionId);
      setComments(hist.comments || []);

      if (fList.length > 0 && !selectedFindingId) {
        setSelectedFindingId(fList[0].id);
      }
    } catch (err) {
      console.error("Failed to load review data:", err);
      setLoadError(err instanceof Error ? err.message : "Unable to load review data.");
      setSubmission(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [submissionId]);

  const latestVersion = submission?.versions?.length
    ? submission.versions[submission.versions.length - 1]
    : null;

  const currentText = latestVersion?.text || "";
  const sourceMimeType = latestVersion?.source_mime_type;
  const canPreviewSource = sourceMimeType === "application/pdf" || !!sourceMimeType?.startsWith("image/");

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    if (!canPreviewSource || !latestVersion?.source_mime_type || !latestVersion.id) {
      setSourceUrl(null);
      setSourceError(null);
      return;
    }
    setSourceUrl(null);
    setSourceError(null);
    api.getSubmissionSource(submissionId, latestVersion.id)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSourceUrl(objectUrl);
      })
      .catch((err: unknown) => {
        if (active) setSourceError(err instanceof Error ? err.message : "Unable to load the original document.");
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [submissionId, latestVersion?.id, latestVersion?.source_mime_type, sourceRetry, canPreviewSource]);

  const handleAccept = async (finding: Finding) => {
    try {
      await api.submitDecision(finding.id, "accept");
      await api.checkSubmission(submissionId);
      await loadData();
    } catch (err: any) {
      alert(`The decision was saved, but the latest version could not be rechecked: ${err.message}`);
    }
  };

  const handleEditSubmit = async () => {
    if (!editingFinding) return;
    try {
      await api.submitDecision(editingFinding.id, "edit", editText);
      setEditingFinding(null);
      setEditText("");
      await api.checkSubmission(submissionId);
      await loadData();
    } catch (err: any) {
      alert(`The edit was saved, but the latest version could not be rechecked: ${err.message}`);
    }
  };

  const handleDisputeSubmit = async () => {
    if (!disputingFinding) return;
    try {
      await api.submitDecision(disputingFinding.id, "dispute", undefined, disputeReason);
      setDisputingFinding(null);
      setDisputeReason("");
      await loadData();
    } catch (err: any) {
      alert(`Error disputing finding: ${err.message}`);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    try {
      await api.addComment(submissionId, newComment.trim(), selectedFindingId || undefined);
      setNewComment("");
      const hist = await api.getHistory(submissionId);
      setComments(hist.comments || []);
    } catch (err: any) {
      alert(`Error adding comment: ${err.message}`);
    }
  };

  const handleRequestReview = async () => {
    try {
      await api.requestReview(submissionId);
      await loadData();
      alert("Submission successfully routed to Manager / Reviewer for sign-off.");
    } catch (err: any) {
      alert(`Error requesting review: ${err.message}`);
    }
  };

  const toggleSource = (fId: string) => {
    setExpandedSources((prev) => ({ ...prev, [fId]: !prev[fId] }));
  };

  const getSeverityBadge = (sev: string) => {
    const map: Record<string, string> = {
      critical: "bg-rose-100 text-rose-800 border-rose-300",
      major: "bg-amber-100 text-amber-800 border-amber-300",
      minor: "bg-blue-50 text-blue-700 border-blue-200",
      info: "bg-stone-100 text-stone-600 border-stone-200",
    };
    return (
      <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${map[sev] || map.info}`}>
        {sev}
      </span>
    );
  };

  const getConfidenceBadge = (conf: string, needsHuman: boolean) => {
    if (needsHuman) {
      return (
        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-300 flex items-center gap-1">
          <HelpCircle className="w-2.5 h-2.5" />
          Needs Reviewer
        </span>
      );
    }
    const map: Record<string, string> = {
      high: "bg-emerald-50 text-emerald-700 border-emerald-200",
      medium: "bg-stone-100 text-stone-700 border-stone-200",
      low: "bg-amber-50 text-amber-700 border-amber-200",
    };
    return (
      <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${map[conf] || map.medium}`}>
        {conf} Conf.
      </span>
    );
  };

  // Render text with clickable highlights
  const renderHighlightedText = () => {
    if (!currentText) return <p className="text-stone-400 italic">No text content available.</p>;

    // Sort findings by start offset
    const sorted = [...findings]
      .filter((f) => f.span_start !== null && f.span_end !== null && f.status === "open")
      .sort((a, b) => (a.span_start || 0) - (b.span_start || 0));

    if (sorted.length === 0) {
      return <div className="whitespace-pre-wrap font-serif text-base leading-relaxed text-stone-800">{currentText}</div>;
    }

    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    sorted.forEach((f, idx) => {
      const start = f.span_start || 0;
      const end = f.span_end || 0;

      // Unhighlighted text before this finding
      if (start > lastIndex) {
        elements.push(
          <span key={`text-${idx}`}>{currentText.substring(lastIndex, start)}</span>
        );
      }

      // Highlighted span
      const isSelected = selectedFindingId === f.id;
      const spanText = currentText.substring(start, end);

      const sevColor =
        f.severity === "critical" || f.severity === "major"
          ? isSelected
            ? "bg-rose-300 text-rose-950 font-medium underline decoration-rose-600 decoration-2"
            : "bg-rose-100/90 text-rose-900 border-b-2 border-rose-500 cursor-pointer"
          : isSelected
          ? "bg-amber-300 text-amber-950 font-medium underline decoration-amber-600 decoration-2"
          : "bg-amber-100/90 text-amber-900 border-b-2 border-amber-500 cursor-pointer";

      elements.push(
        <mark
          key={`mark-${f.id}`}
          onClick={() => setSelectedFindingId(f.id)}
          className={`px-1 py-0.5 rounded transition-all ${sevColor}`}
          title={`${f.category}: ${f.issue}`}
        >
          {spanText}
        </mark>
      );

      lastIndex = Math.max(lastIndex, end);
    });

    if (lastIndex < currentText.length) {
      elements.push(<span key="text-end">{currentText.substring(lastIndex)}</span>);
    }

    return (
      <div className="whitespace-pre-wrap font-serif text-base leading-relaxed text-stone-800 selection:bg-amber-200">
        {elements}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-stone-400 text-xs animate-pulse">
        Loading governance review session...
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center">
        <p role={loadError ? "alert" : undefined} className="text-sm text-stone-600">{loadError || "Submission not found."}</p>
        {loadError && <button onClick={loadData} className="mt-4 text-xs font-semibold text-brand-700 underline">Try again</button>}
        <button onClick={() => navigate("/")} className="mt-4 text-xs font-semibold text-brand-700">
          Back to Dashboard
        </button>
      </div>
    );
  }

  const openFindings = findings.filter((f) => f.status === "open");
  const resolvedFindings = findings.filter((f) => f.status !== "open");

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner & Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-stone-200 mb-6">
        <div>
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-2 font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-stone-900">{submission.title}</h1>
            <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-300">
              {submission.status}
            </span>
            <span className="text-xs text-stone-400">
              Version {latestVersion?.version_no || 1}
            </span>
          </div>
          {submission.intent && (
            <p className="text-xs text-stone-600 mt-1 max-w-2xl">
              <span className="font-semibold text-stone-800">Creator Intent:</span> {submission.intent}
            </p>
          )}
        </div>

        {/* Workflow Action */}
        <div className="flex items-center gap-3">
          {user.role === "creator" && submission.creator_id === user.id && submission.status === "checked" && (
            <button
              onClick={handleRequestReview}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow transition-all"
            >
              <Send className="w-3.5 h-3.5 text-amber-400" />
              Request Manager Review
            </button>
          )}

          {["manager", "reviewer"].includes(user.role) && (
            <button
              onClick={() => navigate(`/approval/${submission.id}`)}
              className="px-3.5 py-2 border border-stone-300 hover:bg-stone-50 text-stone-700 rounded-lg text-xs font-semibold"
            >
              Approval Sign-Off View
            </button>
          )}
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Content with Span Highlights (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {canPreviewSource && latestVersion?.source_mime_type && (
            sourceUrl ? (
              <React.Suspense fallback={<div className="bg-white border border-stone-200 rounded-2xl p-5 text-xs text-stone-500">Loading document renderer…</div>}>
                <SourceMediaViewer
                  mimeType={latestVersion.source_mime_type}
                  sourceUrl={sourceUrl}
                  sourceLayout={latestVersion.source_layout}
                  findings={findings}
                  selectedFindingId={selectedFindingId}
                  onSelectFinding={setSelectedFindingId}
                />
              </React.Suspense>
            ) : (
              <div role={sourceError ? "alert" : undefined} className="bg-white border border-stone-200 rounded-2xl p-5 text-xs text-stone-500">
                {sourceError || "Loading original document preview…"}
                {sourceError && <button type="button" onClick={() => setSourceRetry((value) => value + 1)} className="ml-2 underline text-brand-700">Retry</button>}
              </div>
            )
          )}
          <div className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">
            <div className="px-6 py-3.5 bg-stone-50/80 border-b border-stone-200 flex items-center justify-between text-xs text-stone-500">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-stone-400" />
                <span className="font-semibold text-stone-700">Document Text</span>
                <span className="text-[11px] bg-stone-200 text-stone-700 px-1.5 rounded">
                  v{latestVersion?.version_no}
                </span>
              </div>
              <span className="text-[11px] text-stone-400">
                Click any highlighted span to jump to its cited finding
              </span>
            </div>

            <div className="p-6 min-h-[360px] bg-white">
              {renderHighlightedText()}
            </div>
          </div>

          {/* Submission Comment Thread */}
          <div className="bg-white border border-stone-200 rounded-2xl shadow-sm p-5 space-y-4">
            <div className="flex items-center gap-2 pb-2 border-b border-stone-100">
              <MessageSquare className="w-4 h-4 text-stone-400" />
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">
                Audit & Review Comments ({comments.length})
              </h3>
            </div>

            <div className="space-y-3 max-h-56 overflow-y-auto pr-1">
              {comments.length === 0 ? (
                <p className="text-xs text-stone-400 italic">No comments yet.</p>
              ) : (
                comments.map((c) => (
                  <div key={c.id} className="p-3 bg-stone-50 rounded-xl border border-stone-200/80 text-xs">
                    <div className="flex items-center justify-between font-semibold text-stone-800 mb-1">
                      <span>{c.user_name || "Team Member"}</span>
                      <span className="text-[10px] text-stone-400 font-normal">
                        {new Date(c.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-stone-600 leading-relaxed">{c.body}</p>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handleAddComment} className="flex gap-2 pt-2">
              <input
                type="text"
                placeholder="Add compliance note or question..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="submit"
                className="px-3.5 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800"
              >
                Send
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Findings Panel (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-stone-200">
            <h2 className="text-sm font-bold text-stone-900 flex items-center gap-2">
              <span>Governance Findings</span>
              <span className="text-xs bg-rose-100 text-rose-800 px-2 py-0.5 rounded-full font-bold">
                {openFindings.length}
              </span>
            </h2>
            <span className="text-xs text-stone-400">
              {resolvedFindings.length} resolved
            </span>
          </div>

          {findings.length === 0 ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-8 text-center">
              <ShieldCheck className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
              <h3 className="font-bold text-emerald-900 text-sm">No Compliance Issues Detected</h3>
              <p className="text-xs text-emerald-700 mt-1">
                Content is fully compliant with all active brand voice guidelines, terms, and verified facts.
              </p>
            </div>
          ) : (
            <div className="space-y-4 max-h-[calc(100vh-14rem)] overflow-y-auto pr-1">
              {findings.map((f) => {
                const isSelected = selectedFindingId === f.id;
                const isExpanded = !!expandedSources[f.id];

                // Extract span from text
                const originalSpan =
                  f.span_start !== null && f.span_end !== null
                    ? currentText.substring(f.span_start, f.span_end)
                    : "";

                return (
                  <div
                    key={f.id}
                    onClick={() => setSelectedFindingId(f.id)}
                    className={`bg-white border rounded-2xl p-5 shadow-sm transition-all cursor-pointer ${
                      isSelected
                        ? "border-amber-500 ring-2 ring-amber-100"
                        : "border-stone-200 hover:border-stone-300"
                    } ${f.status !== "open" ? "opacity-75 bg-stone-50/60" : ""}`}
                  >
                    {/* Header Chips */}
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-stone-900 uppercase tracking-tight">
                          {f.category.replace("_", " ")}
                        </span>
                        {getSeverityBadge(f.severity)}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {getConfidenceBadge(f.confidence, f.needs_human)}
                        {f.status !== "open" && (
                          <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-stone-200 text-stone-800">
                            {f.status}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Issue Explanation */}
                    <p className="text-xs font-medium text-stone-800 mb-3 leading-snug">
                      {f.issue}
                    </p>

                    {/* Cited Source Section (Non-negotiable requirement) */}
                    {f.source_quote && (
                      <div className="mb-3 p-3 bg-stone-50 rounded-xl border border-stone-200 text-xs">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSource(f.id);
                          }}
                          className="w-full flex items-center justify-between text-stone-700 font-semibold text-[11px] hover:text-amber-800"
                        >
                          <span className="flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5 text-amber-700" />
                            Cited Source ({f.source_type || "Guideline"})
                          </span>
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        <div className={`mt-2 font-mono text-[11px] text-stone-600 bg-white p-2 rounded border border-stone-200/80 ${isExpanded ? "" : "line-clamp-2"}`}>
                          "{f.source_quote}"
                        </div>
                      </div>
                    )}

                    {/* Word-Level Diff Fix (Improvement 1) */}
                    {f.suggested_rewrite && (
                      <div className="mb-4">
                        <DiffViewer
                          original={originalSpan || "original text"}
                          replacement={f.suggested_rewrite}
                        />
                      </div>
                    )}

                    {/* Action Buttons: Accept / Edit / Dispute */}
                    {f.status === "open" && user.role === "creator" && submission.creator_id === user.id && (
                      <div className="flex items-center gap-2 pt-2 border-t border-stone-100">
                        {f.suggested_rewrite && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAccept(f);
                            }}
                            className="flex-1 py-1.5 px-3 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center justify-center gap-1 transition-colors"
                          >
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            Accept Fix
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingFinding(f);
                            setEditText(f.suggested_rewrite || originalSpan);
                          }}
                          className="py-1.5 px-3 border border-stone-300 hover:bg-stone-50 text-stone-700 rounded-lg text-xs font-medium inline-flex items-center gap-1"
                        >
                          <Edit2 className="w-3 h-3 text-stone-500" />
                          Edit
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDisputingFinding(f);
                          }}
                          className="py-1.5 px-3 border border-rose-200 text-rose-700 hover:bg-rose-50 rounded-lg text-xs font-medium"
                        >
                          Dispute
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Edit Custom Replacement Modal */}
      {editingFinding && (
        <div className="fixed inset-0 z-50 bg-stone-950/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-stone-200 shadow-xl space-y-4">
            <h3 className="font-bold text-stone-900 text-sm">Edit Custom Replacement</h3>
            <p className="text-xs text-stone-500">
              Provide your own wording to replace: <span className="font-semibold text-stone-700">"{editingFinding.issue}"</span>
            </p>

            <textarea
              rows={4}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full p-3 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setEditingFinding(null)}
                className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleEditSubmit}
                className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800"
              >
                Apply Edit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dispute Modal */}
      {disputingFinding && (
        <div className="fixed inset-0 z-50 bg-stone-950/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-stone-200 shadow-xl space-y-4">
            <h3 className="font-bold text-stone-900 text-sm">Dispute Finding</h3>
            <p className="text-xs text-stone-500">
              Explain why this finding should be overruled or where the brand guideline requires clarification:
            </p>

            <textarea
              rows={4}
              placeholder="e.g. This claim has verified clinical documentation in batch assay report #882."
              value={disputeReason}
              onChange={(e) => setDisputeReason(e.target.value)}
              className="w-full p-3 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setDisputingFinding(null)}
                className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleDisputeSubmit}
                className="px-4 py-1.5 bg-rose-700 text-white rounded-lg text-xs font-semibold hover:bg-rose-800"
              >
                Submit Dispute
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
