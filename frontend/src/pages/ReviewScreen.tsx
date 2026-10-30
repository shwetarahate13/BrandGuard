import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Diff from "diff";
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
  Eye,
  Undo2,
  Wand2,
} from "lucide-react";
import { api } from "../api";
import { Submission, Finding, User } from "../types";
import { DiffViewer } from "../components/DiffViewer";
import { Modal, Stepper } from "../components/ui";

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
  const commentAttempt = useRef<{ signature: string; key: string } | null>(null);

  // A creator must be able to revise a submission after a manager requests
  // changes, including when the check found no individual finding to edit.
  const [revisionText, setRevisionText] = useState("");
  const [revisionError, setRevisionError] = useState<string | null>(null);
  const [savingRevision, setSavingRevision] = useState(false);
  const [editingDraft, setEditingDraft] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [autoRecheck, setAutoRecheck] = useState(false);
  const [draftUndoText, setDraftUndoText] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [batchApplying, setBatchApplying] = useState(false);
  const liveSaveText = useRef<string | null>(null);
  const reviewInFlight = useRef(false);
  const revisionSaveInFlight = useRef(false);
  const revisionTextarea = useRef<HTMLTextAreaElement | null>(null);
  const pendingCaret = useRef<{ start: number; end: number } | null>(null);
  const draftStorageKey = `brandguard:review-draft:${user.id}:${submissionId}`;
  const [reviewing, setReviewing] = useState(false);
  const [reviewProgress, setReviewProgress] = useState({ percent: 0, message: "" });
  const [decisionPendingId, setDecisionPendingId] = useState<string | null>(null);
  const [workflowPending, setWorkflowPending] = useState(false);
  const [commentPending, setCommentPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Expanded sources state
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [sourceRetry, setSourceRetry] = useState(0);

  const persistDraft = (text: string, versionId: string, start: number, end: number, checked: boolean) => {
    window.localStorage.setItem(draftStorageKey, JSON.stringify({
      text,
      versionId,
      selectionStart: start,
      selectionEnd: end,
      checked,
    }));
    pendingCaret.current = { start, end };
  };

  const handleRevisionChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const { value, selectionStart, selectionEnd } = event.target;
    setRevisionText(value);
    setDraftDirty(value !== currentText);
    if (latestVersion?.id) persistDraft(value, latestVersion.id, selectionStart, selectionEnd, false);
  };

  const loadData = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const [sub, fList, hist] = await Promise.all([
        api.getSubmission(submissionId),
        api.getFindings(submissionId),
        api.getHistory(submissionId),
      ]);
      const currentVersion = sub.versions?.[sub.versions.length - 1];
      const currentVersionText = currentVersion?.text || "";
      const isOwnDraft = user.role === "creator" && sub.creator_id === user.id;
      const savedDraftText = isOwnDraft ? window.localStorage.getItem(draftStorageKey) : null;
      let restoredText = currentVersionText;
      let restoredDirty = false;
      let restoredEditing = false;
      let restoredCaret: { start: number; end: number } | null = null;
      if (savedDraftText && currentVersion) {
        try {
          const savedDraft = JSON.parse(savedDraftText) as {
            text?: unknown;
            versionId?: unknown;
            selectionStart?: unknown;
            selectionEnd?: unknown;
            checked?: unknown;
          };
          if (typeof savedDraft.text === "string" && savedDraft.versionId === currentVersion.id) {
            restoredText = savedDraft.text;
            restoredDirty = savedDraft.text !== currentVersionText || savedDraft.checked !== true;
            restoredEditing = true;
            restoredCaret = {
              start: typeof savedDraft.selectionStart === "number" ? savedDraft.selectionStart : savedDraft.text.length,
              end: typeof savedDraft.selectionEnd === "number" ? savedDraft.selectionEnd : savedDraft.text.length,
            };
          } else {
            window.localStorage.removeItem(draftStorageKey);
          }
        } catch (error) {
          console.error("Unable to restore the saved draft:", error);
          window.localStorage.removeItem(draftStorageKey);
        }
      }
      setSubmission(sub);
      setRevisionText(restoredText);
      setDraftDirty(restoredDirty);
      setEditingDraft(restoredEditing);
      pendingCaret.current = restoredCaret;
      setFindings(fList);
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
    setAutoRecheck(false);
    setEditingDraft(false);
    loadData();
  }, [submissionId]);

  useEffect(() => {
    if (!editingDraft || !pendingCaret.current || !revisionTextarea.current) return;
    const { start, end } = pendingCaret.current;
    const length = revisionTextarea.current.value.length;
    revisionTextarea.current.setSelectionRange(Math.min(start, length), Math.min(end, length));
    pendingCaret.current = null;
  }, [editingDraft, submissionId]);

  const latestVersion = submission?.versions?.length
    ? submission.versions[submission.versions.length - 1]
    : null;

  const currentText = latestVersion?.text || "";
  const previousVersion = submission?.versions?.length && submission.versions.length > 1
    ? submission.versions[submission.versions.length - 2]
    : null;
  const versionDiff = useMemo(
    () => previousVersion ? Diff.diffWordsWithSpace(previousVersion.text, currentText) : [],
    [previousVersion?.id, currentText],
  );
  const workflowStep = submission?.status === "draft" ? 0 : submission?.status === "approved" ? 3 : 1;
  const currentFindings = findings.filter((finding) => !finding.historical && finding.version_id === latestVersion?.id);
  const openFindings = currentFindings.filter((finding) => finding.status === "open");
  const resolvedFindings = findings.filter((finding) => finding.status !== "open" || finding.version_change === "resolved");
  const sourceMimeType = latestVersion?.source_mime_type;
  const canPreviewSource = sourceMimeType === "application/pdf" || !!sourceMimeType?.startsWith("image/");

  const runBackgroundCheck = async (id: string) => {
    if (reviewInFlight.current) return null;
    reviewInFlight.current = true;
    setReviewing(true);
    setReviewProgress({ percent: 0, message: "Starting review." });
    try {
      return await api.checkSubmission(id, (percent, message) => setReviewProgress({ percent, message }));
    } finally {
      reviewInFlight.current = false;
      setReviewing(false);
    }
  };

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
    if (decisionPendingId || reviewing || reviewInFlight.current || revisionSaveInFlight.current) return;
    setDecisionPendingId(finding.id);
    setActionError(null);
    try {
      await api.submitDecision(finding.id, "accept");
      await runBackgroundCheck(submissionId);
      await loadData();
    } catch (err: any) {
      setActionError(`Could not finish accepting this finding. ${err.message}`);
    } finally {
      setDecisionPendingId(null);
    }
  };

  const handleEditSubmit = async () => {
    if (!editingFinding || decisionPendingId || reviewing || reviewInFlight.current || revisionSaveInFlight.current) return;
    setDecisionPendingId(editingFinding.id);
    setActionError(null);
    try {
      await api.submitDecision(editingFinding.id, "edit", editText);
      setEditingFinding(null);
      setEditText("");
      await runBackgroundCheck(submissionId);
      await loadData();
    } catch (err: any) {
      setActionError(`Could not finish applying this edit. ${err.message}`);
    } finally {
      setDecisionPendingId(null);
    }
  };

  const handleDisputeSubmit = async () => {
    if (!disputingFinding || decisionPendingId || reviewing) return;
    setDecisionPendingId(disputingFinding.id);
    setActionError(null);
    try {
      await api.submitDecision(disputingFinding.id, "dispute", undefined, disputeReason);
      setDisputingFinding(null);
      setDisputeReason("");
      await loadData();
    } catch (err: any) {
      setActionError(`Could not submit this dispute. ${err.message}`);
    } finally {
      setDecisionPendingId(null);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim() || commentPending) return;
    const body = newComment.trim();
    const signature = JSON.stringify({ body, findingId: selectedFindingId || undefined });
    if (!commentAttempt.current || commentAttempt.current.signature !== signature) {
      commentAttempt.current = { signature, key: crypto.randomUUID() };
    }
    setCommentPending(true);
    setActionError(null);
    try {
      await api.addComment(submissionId, body, selectedFindingId || undefined, commentAttempt.current.key);
      commentAttempt.current = null;
      setNewComment("");
      const hist = await api.getHistory(submissionId);
      setComments(hist.comments || []);
    } catch (err: any) {
      setActionError(`Could not add the comment. ${err.message}`);
    } finally {
      setCommentPending(false);
    }
  };

  const handleRequestReview = async () => {
    if (workflowPending) return;
    setWorkflowPending(true);
    setActionError(null);
    try {
      await api.requestReview(submissionId);
      await loadData();
    } catch (err: any) {
      setActionError(`Could not request review. ${err.message}`);
    } finally {
      setWorkflowPending(false);
    }
  };

  const saveAndCheckRevision = async () => {
    if (revisionSaveInFlight.current || savingRevision || reviewInFlight.current || reviewing) return;
    const text = revisionText;
    if (!submission || !text.trim()) {
      setRevisionError("Add the revised content before saving this version.");
      return;
    }
    if (text === currentText) {
      setDraftDirty(false);
      setRevisionError(null);
      return;
    }
    revisionSaveInFlight.current = true;
    setSavingRevision(true);
    setRevisionError(null);
    try {
      const version = await api.addVersion(submission.id, text);
      if (!version?.id) throw new Error("The revised version could not be confirmed.");
      const caret = pendingCaret.current || { start: text.length, end: text.length };
      persistDraft(text, version.id, caret.start, caret.end, false);
      await runBackgroundCheck(submission.id);
      persistDraft(text, version.id, caret.start, caret.end, true);
      await loadData();
    } catch (err) {
      setDraftDirty(true);
      setRevisionError(err instanceof Error ? err.message : "Unable to save and check the revised version.");
    } finally {
      revisionSaveInFlight.current = false;
      setSavingRevision(false);
    }
  };

  const handleResubmitRevision = (event: React.FormEvent) => {
    event.preventDefault();
    void saveAndCheckRevision();
  };

  const handleRevisionKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void saveAndCheckRevision();
    }
  };

  useEffect(() => {
    if (!autoRecheck || !draftDirty || !revisionText.trim() || revisionText === currentText || savingRevision || reviewing) return;
    if (liveSaveText.current === revisionText) return;
    const timer = window.setTimeout(async () => {
      if (revisionSaveInFlight.current || reviewInFlight.current) return;
      revisionSaveInFlight.current = true;
      const text = revisionText;
      liveSaveText.current = text;
      setSavingRevision(true);
      setRevisionError(null);
      try {
        const version = await api.addVersion(submissionId, text);
        if (!version?.id) throw new Error("The revised version could not be confirmed.");
        const caret = pendingCaret.current || { start: text.length, end: text.length };
        persistDraft(text, version.id, caret.start, caret.end, false);
        await runBackgroundCheck(submissionId);
        persistDraft(text, version.id, caret.start, caret.end, true);
        await loadData();
      } catch (error) {
        setDraftDirty(true);
        liveSaveText.current = null;
        setRevisionError(error instanceof Error ? error.message : "Live re-check failed.");
      } finally {
        revisionSaveInFlight.current = false;
        setSavingRevision(false);
      }
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [autoRecheck, editingDraft, draftDirty, revisionText, currentText, savingRevision, reviewing, submissionId]);

  const handleBatchApply = async (mode: "grammar" | "safe") => {
    if (batchApplying || decisionPendingId || reviewing || reviewInFlight.current || revisionSaveInFlight.current) return;
    const eligible = openFindings.filter((finding) =>
      mode === "grammar"
        ? ["grammar", "spelling"].includes(finding.category)
        : ["grammar", "spelling", "terminology", "accessibility"].includes(finding.category),
    ).filter((finding) => finding.suggested_rewrite && finding.confidence === "high" && !finding.needs_human);
    if (!eligible.length) return;
    setBatchApplying(true);
    setActionError(null);
    try {
      await api.applySafeFixes(submissionId, eligible.map((finding) => finding.id), mode);
      await runBackgroundCheck(submissionId);
      await loadData();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to apply safe fixes.");
    } finally {
      setBatchApplying(false);
    }
  };

  const previewEdits = openFindings
    .filter((finding) => finding.suggested_rewrite && finding.span_start !== null && finding.span_end !== null)
    .sort((a, b) => (a.span_start || 0) - (b.span_start || 0))
    .filter((finding, index, list) => index === 0 || (finding.span_start || 0) >= (list[index - 1].span_end || 0));
  const previewText = [...previewEdits].reverse().reduce((draft, finding) => {
    const start = finding.span_start || 0;
    const end = finding.span_end || 0;
    return draft.slice(0, start) + (finding.suggested_rewrite || "") + draft.slice(end);
  }, currentText);
  const renderPreviewChanges = () => {
    const parts: React.ReactNode[] = [];
    let offset = 0;
    previewEdits.forEach((finding) => {
      const start = finding.span_start || 0;
      const end = finding.span_end || 0;
      if (start < offset) return;
      parts.push(currentText.slice(offset, start));
      parts.push(<mark key={finding.id} className="rounded bg-emerald-200 px-0.5 text-emerald-950">{finding.suggested_rewrite}</mark>);
      offset = end;
    });
    parts.push(currentText.slice(offset));
    return parts;
  };
  const findingGroups = [
    { title: "Grammar and spelling", categories: ["grammar", "spelling"] },
    { title: "Terminology", categories: ["terminology"] },
    { title: "Tone", categories: ["tone"] },
    { title: "Claims and facts", categories: ["unsupported_claim", "factual_accuracy", "messaging"] },
    { title: "Accessibility", categories: ["accessibility"] },
  ].map((group) => ({ ...group, items: findings.filter((finding) => group.categories.includes(finding.category)) })).filter((group) => group.items.length);

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
    const sorted = [...currentFindings]
      .filter((f) => f.span_start !== null && f.span_end !== null && f.status === "open")
      .sort((a, b) => (a.span_start || 0) - (b.span_start || 0));

    if (sorted.length === 0) {
      return <div className={`whitespace-pre-wrap font-serif text-base leading-relaxed text-stone-800 ${draftDirty ? "opacity-50" : ""}`}>{currentText}</div>;
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
          role="button"
          tabIndex={0}
          aria-label={`${f.category.replace("_", " ")} finding: ${f.issue}`}
          onClick={() => setSelectedFindingId(f.id)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setSelectedFindingId(f.id);
            }
          }}
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
      <div className={`whitespace-pre-wrap font-serif text-base leading-relaxed text-stone-800 selection:bg-amber-200 ${draftDirty ? "opacity-50" : ""}`}>
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

  return (
    <div className="review-page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner & Navigation */}
      <div className="review-page__header flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-stone-200 mb-6">
        <div className="min-w-0">
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-2 font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
          <div className="review-page__title-row flex items-center gap-3">
            <h1 className="text-xl font-bold text-stone-900">{submission.title}</h1>
            <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-300">
              {submission.status}
            </span>
            {submission.is_demo && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300">Demo data</span>}
            {submission.confidential && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-purple-100 text-purple-900 border border-purple-300">Confidential · local checks only</span>}
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
              disabled={workflowPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5 text-amber-400" />
              {workflowPending ? "Requesting review…" : "Request Manager Review"}
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

      <Stepper steps={["Draft", "Review", "Sign-off", "Approved"]} current={workflowStep} className="review-page__stepper mb-6" />

      {reviewing && (
        <div className="mb-6 rounded-xl border border-brand-200 bg-brand-50 p-3" role="status" aria-live="polite">
          <div className="flex justify-between gap-4 text-xs text-brand-900 mb-1">
            <span>{reviewProgress.message}</span><span>{reviewProgress.percent}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-brand-100 overflow-hidden">
            <div className="h-full bg-brand-600 transition-all" style={{ width: `${reviewProgress.percent}%` }} />
          </div>
        </div>
      )}
      {actionError && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800" role="alert">
          {actionError} You can retry after checking the current status.
        </div>
      )}

      {user.role === "creator" && submission.creator_id === user.id &&
        editingDraft && (
          <form onSubmit={handleResubmitRevision} className="mb-6 rounded-xl border border-brand-200 bg-white p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-stone-900">Edit draft</h2>
                <p className="mt-1 text-xs text-stone-600">Edits are not checked until you choose Re-check. Automatic re-checking is optional.</p>
              </div>
              <button type="button" onClick={() => setEditingDraft(false)} className="min-h-11 px-2 text-xs text-stone-500 underline">Close editor</button>
            </div>
            {revisionError && <p role="alert" className="text-xs text-rose-700">{revisionError}</p>}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p role="status" className={draftDirty ? "text-xs font-medium text-amber-800" : "text-xs text-stone-600"}>
                {draftDirty ? "Edited, not checked. Findings below are from the previous version." : "No draft edits pending."}
              </p>
              <label className="inline-flex min-h-11 items-center gap-2 text-xs text-stone-700">
                <input type="checkbox" checked={autoRecheck} onChange={(event) => setAutoRecheck(event.target.checked)} />
                Auto re-check after 3 s idle
              </label>
            </div>
            <div className="flex items-center justify-between gap-2">
              <button type="button" disabled={savingRevision || reviewing || !draftUndoText} onClick={() => { liveSaveText.current = null; setRevisionText(draftUndoText); setDraftDirty(draftUndoText !== currentText); const position = draftUndoText.length; if (latestVersion?.id) persistDraft(draftUndoText, latestVersion.id, position, position, draftUndoText === currentText); }} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-3 py-2 text-xs text-stone-700 disabled:opacity-50"><Undo2 className="h-3.5 w-3.5" />Undo edits</button>
              <div className="flex items-center gap-3">
                {savingRevision && <span role="status" className="text-xs text-stone-500">Saving and re-checking…</span>}
                <button type="submit" disabled={savingRevision || reviewing || !revisionText.trim() || revisionText === currentText} className="rounded-lg bg-stone-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">Re-check</button>
              </div>
            </div>
          </form>
        )}

      {user.role === "creator" && submission.creator_id === user.id && !editingDraft &&
        (submission.status === "changes_requested" || submission.status === "rejected") && (
          <form
            onSubmit={handleResubmitRevision}
            className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-3"
          >
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Create a revised version</h2>
              <p className="mt-1 text-xs text-stone-600">
                Update the content using the manager’s feedback. Choose Re-check to save and run the brand check.
              </p>
            </div>
            {revisionError && <p role="alert" className="text-xs text-rose-700">{revisionError}</p>}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p role="status" className={draftDirty ? "text-xs font-medium text-amber-800" : "text-xs text-stone-600"}>
                {draftDirty ? "Edited, not checked. Findings below are from the previous version." : "No draft edits pending."}
              </p>
              <label className="inline-flex min-h-11 items-center gap-2 text-xs text-stone-700">
                <input type="checkbox" checked={autoRecheck} onChange={(event) => setAutoRecheck(event.target.checked)} />
                Auto re-check after 3 s idle
              </label>
            </div>
            <textarea
              aria-label="Revised submission content"
              value={revisionText}
              ref={revisionTextarea}
              onChange={handleRevisionChange}
              onKeyDown={handleRevisionKeyDown}
              rows={6}
              required
              maxLength={50000}
              className="w-full rounded-lg border border-stone-300 bg-white p-3 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={savingRevision || reviewing || !revisionText.trim() || revisionText === currentText}
                className="rounded-lg bg-stone-900 px-4 py-2 text-xs font-semibold text-white hover:bg-stone-800 disabled:opacity-50"
              >
                {savingRevision ? "Saving and checking…" : "Re-check"}
              </button>
            </div>
          </form>
        )}

      {/* Main Two-Column Layout */}
      <div className="review-page__layout grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Content with Span Highlights (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {canPreviewSource && latestVersion?.source_mime_type && (
            <div className={draftDirty ? "opacity-50" : ""}>
              {sourceUrl ? (
                <React.Suspense fallback={<div className="bg-white border border-stone-200 rounded-2xl p-5 text-xs text-stone-500">Loading document renderer…</div>}>
                  <SourceMediaViewer
                    mimeType={latestVersion.source_mime_type}
                    sourceUrl={sourceUrl}
                    sourceLayout={latestVersion.source_layout}
                    findings={currentFindings}
                    selectedFindingId={selectedFindingId}
                    onSelectFinding={setSelectedFindingId}
                  />
                </React.Suspense>
              ) : (
                <div role={sourceError ? "alert" : undefined} className="bg-white border border-stone-200 rounded-2xl p-5 text-xs text-stone-500">
                  {sourceError || "Loading original document preview…"}
                  {sourceError && <button type="button" onClick={() => setSourceRetry((value) => value + 1)} className="ml-2 underline text-brand-700">Retry</button>}
                </div>
              )}
            </div>
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
                {draftDirty ? "Previous-version findings are dimmed until re-check" : "Click any highlighted span to jump to its cited finding"}
              </span>
            </div>

            {previousVersion && (
              <details className="border-b border-stone-200 px-6 py-3">
                <summary className="cursor-pointer text-xs font-semibold text-stone-700">
                  Changes from version {previousVersion.version_no}
                </summary>
                <div className="mt-3 whitespace-pre-wrap break-words text-xs leading-relaxed text-stone-700">
                  {versionDiff.map((part, index) => part.added
                    ? <ins key={index} className="rounded bg-emerald-100 px-0.5 text-emerald-950 no-underline">{part.value}</ins>
                    : part.removed
                      ? <del key={index} className="rounded bg-rose-100 px-0.5 text-rose-900">{part.value}</del>
                      : <span key={index}>{part.value}</span>)}
                </div>
              </details>
            )}

            <div className="p-6 min-h-[360px] bg-white">
              {editingDraft ? (
                <textarea aria-label="Edit draft content" ref={revisionTextarea} value={revisionText} onChange={handleRevisionChange} onKeyDown={handleRevisionKeyDown} rows={18} maxLength={200000} className="min-h-[360px] w-full resize-y whitespace-pre-wrap font-serif text-base leading-relaxed text-stone-800 outline-none" />
              ) : renderHighlightedText()}
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
                aria-label="Add a review comment"
                placeholder="Add compliance note or question..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="submit"
                disabled={commentPending || !newComment.trim()}
                className="px-3.5 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 disabled:opacity-50"
              >
                {commentPending ? "Sending…" : "Send"}
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

          {user.role === "creator" && submission.creator_id === user.id && (
            <div className="flex flex-wrap gap-2">
              {!editingDraft && <button type="button" onClick={() => { setDraftUndoText(currentText); setRevisionText(currentText); setDraftDirty(false); liveSaveText.current = null; setEditingDraft(true); if (latestVersion?.id) persistDraft(currentText, latestVersion.id, currentText.length, currentText.length, true); }} className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700">Edit draft</button>}
              <button type="button" onClick={() => handleBatchApply("grammar")} disabled={batchApplying || reviewing || !openFindings.some((finding) => ["grammar", "spelling"].includes(finding.category) && finding.suggested_rewrite && finding.confidence === "high" && !finding.needs_human)} className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700 disabled:opacity-50">{batchApplying ? "Applying…" : "Fix all grammar and spelling"}</button>
              <button type="button" onClick={() => handleBatchApply("safe")} disabled={batchApplying || reviewing || !openFindings.some((finding) => ["grammar", "spelling", "terminology", "accessibility"].includes(finding.category) && finding.suggested_rewrite && finding.confidence === "high" && !finding.needs_human)} className="inline-flex items-center gap-1 rounded-lg bg-stone-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><Wand2 className="h-3.5 w-3.5 text-amber-300" />Apply all safe fixes</button>
              <button type="button" onClick={() => setPreviewOpen(true)} disabled={!previewEdits.length} className="inline-flex items-center gap-1 rounded-lg border border-brand-300 px-3 py-2 text-xs font-semibold text-brand-800 disabled:opacity-50"><Eye className="h-3.5 w-3.5" />Preview corrected draft</button>
            </div>
          )}

          {findings.length === 0 ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-8 text-center">
              <ShieldCheck className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
              <h3 className="font-bold text-emerald-900 text-sm">No issues found</h3>
              <p className="text-xs text-emerald-700 mt-1">
                Checked spelling and grammar, terminology, tone, claims and facts, and accessibility against available approved sources.
              </p>
            </div>
          ) : (
            <div className={`space-y-4 max-h-[calc(100vh-14rem)] overflow-y-auto pr-1 ${draftDirty ? "opacity-50" : ""}`}>
              {findingGroups.map((group) => (
                <section key={group.title} className="space-y-3">
                  <h3 className="sticky top-0 z-10 rounded-lg bg-stone-100 px-3 py-2 text-xs font-bold uppercase tracking-wide text-stone-700">{group.title}</h3>
                  {group.items.map((f) => {
                const isSelected = selectedFindingId === f.id;
                const isExpanded = !!expandedSources[f.id];

                // Extract span from text
                const findingText = submission.versions?.find((version) => version.id === f.version_id)?.text || currentText;
                const originalSpan =
                  f.span_start !== null && f.span_end !== null
                    ? findingText.substring(f.span_start, f.span_end)
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
                        {f.version_change && (
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                            f.version_change === "resolved" ? "bg-emerald-100 text-emerald-900" :
                              f.version_change === "regressed" ? "bg-rose-100 text-rose-900" :
                                f.version_change === "new" ? "bg-blue-100 text-blue-900" :
                                  "bg-amber-100 text-amber-900"
                          }`}>
                            {f.version_change === "still_open" ? "Still open" : f.version_change[0].toUpperCase() + f.version_change.slice(1)}
                            {f.finding_version_no ? ` · v${f.finding_version_no}` : ""}
                          </span>
                        )}
                        {getConfidenceBadge(f.confidence, f.needs_human)}
                        {!f.historical && f.status !== "open" && (
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
                            How was this decided? · Cited source ({f.source_type || "Guideline"})
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
                    {!f.historical && f.version_id === latestVersion?.id && f.status === "open" && user.role === "creator" && submission.creator_id === user.id && (
                      <div className="flex items-center gap-2 pt-2 border-t border-stone-100">
                        {f.suggested_rewrite && (
                          <button
                            type="button"
                            disabled={!!decisionPendingId || reviewing}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAccept(f);
                            }}
                            className="flex-1 py-1.5 px-3 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow-sm inline-flex items-center justify-center gap-1 transition-colors"
                          >
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            {decisionPendingId === f.id ? "Applying…" : "Accept Fix"}
                          </button>
                        )}

                        <button
                          type="button"
                          disabled={!!decisionPendingId || reviewing}
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
                          disabled={!!decisionPendingId || reviewing}
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
                </section>
              ))}
            </div>
          )}
        </div>
      </div>

      <Modal open={previewOpen} title="Preview corrected draft" onClose={() => setPreviewOpen(false)} className="ui-dialog--wide">
        <p className="mb-4 text-sm text-secondary">Highlighted wording is proposed. Nothing has been applied.</p>
        <div className="grid min-h-0 max-h-[60vh] gap-4 overflow-auto md:grid-cols-2">
          <section className="min-w-0 rounded-xl border border-stone-200 p-4"><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-stone-600">Original</h3><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-stone-800">{currentText}</pre></section>
          <section className="min-w-0 rounded-xl border border-emerald-200 bg-emerald-50/30 p-4"><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-stone-600">Corrected draft</h3><pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-stone-800">{renderPreviewChanges()}</pre></section>
        </div>
        <div className="mt-4 flex justify-end"><button type="button" onClick={() => { setRevisionText(previewText); setDraftUndoText(currentText); setDraftDirty(previewText !== currentText); const position = previewText.length; if (latestVersion?.id) persistDraft(previewText, latestVersion.id, position, position, false); setEditingDraft(true); setPreviewOpen(false); liveSaveText.current = null; }} className="rounded-lg bg-stone-900 px-4 py-2 text-xs font-semibold text-white">Open in Edit Draft</button></div>
      </Modal>

      <Modal open={!!editingFinding} title="Edit custom replacement" onClose={() => setEditingFinding(null)}>
        {editingFinding && <div className="space-y-4">
          <p className="text-sm text-secondary">Provide your own wording to replace: <span className="font-semibold text-primary">“{editingFinding.issue}”</span></p>
          <label className="ui-field text-sm font-semibold" htmlFor="finding-edit-text">Replacement wording<textarea id="finding-edit-text" rows={4} value={editText} onChange={(e) => setEditText(e.target.value)} className="w-full p-3 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" /></label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setEditingFinding(null)} disabled={!!decisionPendingId} className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg font-medium">Cancel</button>
            <button type="button" onClick={handleEditSubmit} disabled={!!decisionPendingId || !editText.trim()} className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 disabled:opacity-50">{decisionPendingId ? "Applying…" : "Apply Edit"}</button>
          </div>
        </div>}
      </Modal>

      <Modal open={!!disputingFinding} title="Dispute finding" onClose={() => setDisputingFinding(null)}>
        {disputingFinding && <div className="space-y-4">
          <p className="text-sm text-secondary">Explain why this finding should be overruled or where the brand guideline requires clarification.</p>
          <label className="ui-field text-sm font-semibold" htmlFor="finding-dispute-reason">Dispute reason<textarea id="finding-dispute-reason" rows={4} placeholder="Explain the evidence or guideline context for this dispute." value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} className="w-full p-3 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" /></label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setDisputingFinding(null)} disabled={!!decisionPendingId} className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg font-medium">Cancel</button>
            <button type="button" onClick={handleDisputeSubmit} disabled={!!decisionPendingId || !disputeReason.trim()} className="px-4 py-1.5 bg-rose-700 text-white rounded-lg text-xs font-semibold hover:bg-rose-800 disabled:opacity-50">{decisionPendingId ? "Submitting…" : "Submit Dispute"}</button>
          </div>
        </div>}
      </Modal>
    </div>
  );
};
