import React, { useRef, useState } from "react";
import { Upload, FileText, ArrowLeft, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { api } from "../api";
interface NewSubmissionProps {
  navigate: (path: string) => void;
}

const SAMPLE_SUBMISSIONS = [
  { id: "claims", title: "Unverified product launch claim", intent: "Introduce the new product and explain its benefits.", text: "Clinically proven to work for everyone. It is 100% safe and the number one choice for healthy skin." },
  { id: "pricing", title: "Retail promotion with wrong price", intent: "Announce a limited-time discount to returning customers.", text: "This week only: our daily care set is just $9.99. Shop now before this unbelievable offer disappears!" },
  { id: "expired-facts", title: "Campaign with outdated research", intent: "Share a research statistic to support our sustainability story.", text: "A 2021 report says 96% of customers already choose this packaging, and the figure is still current today." },
  { id: "typos", title: "Product page with spelling mistakes", intent: "Describe how to use the moisturizer in a clear, friendly way.", text: "Apply a small ammount to clean skn every morning. This increadible formula works instantly." },
  { id: "tone", title: "Social post with risky wording", intent: "Write an upbeat social post about a new collection.", text: "THIS IS THE BEST THING EVER!!! Grab yours now, don't be the last one without it lol." },
  { id: "accessibility", title: "Email with an accessibility gap", intent: "Encourage customers to browse the spring collection.", text: "Discover the spring collection today. Click here to learn more and see the new products." },
  { id: "writing-grammar", title: "Writing assistant: grammar and spelling", intent: "Share a brief note about our bakery and its patrons.", text: "Teh bakery accomodate every patron. Its a more faster way to enjoy fresh bread. We we welcome our neighbors" },
  { id: "writing-guidelines", title: "Writing assistant: guidelines and regulation", intent: "Describe a new seasonal drink and invite readers to learn more.", text: "Our new Golden Oat Elixir is guaranteed to cure tired mornings. We call our clients and consumers to click here for more details." },
];

export const NewSubmission: React.FC<NewSubmissionProps> = ({ navigate }) => {
  const [tab, setTab] = useState<"paste" | "upload">("paste");
  const [title, setTitle] = useState("");
  const [intent, setIntent] = useState("");
  const [text, setText] = useState("");
  const [confidential, setConfidential] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const submissionAttempt = useRef<{ signature: string; key: string } | null>(null);

  const applySample = (sampleId: string) => {
    const sample = SAMPLE_SUBMISSIONS.find((item) => item.id === sampleId);
    if (!sample) return;
    setTitle(sample.title);
    setIntent(sample.intent);
    setText(sample.text);
    setTab("paste");
    setFile(null);
    setError(null);
    submissionAttempt.current = null;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.size > 25 * 1024 * 1024) {
        setFile(null);
        submissionAttempt.current = null;
        setError("File size exceeds 25 MB limit. Please select a smaller document.");
        return;
      }
      submissionAttempt.current = null;
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " "));
      }
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Please provide a title for this submission.");
      return;
    }
    if (tab === "paste" && text.trim().split(/\s+/).length > 20_000) {
      setError("This check supports up to 20,000 words. Shorten the content and try again.");
      return;
    }

    setLoading(true);
    setProgressMessage("Preparing your submission.");
    setError(null);

    try {
      let created;
      const signature = JSON.stringify({
        tab,
        title: title.trim(),
        intent: intent.trim(),
        text: tab === "paste" ? text.trim() : undefined,
        file: tab === "upload" && file ? [file.name, file.size, file.lastModified, file.type] : undefined,
        confidential,
      });
      if (!submissionAttempt.current || submissionAttempt.current.signature !== signature) {
        submissionAttempt.current = { signature, key: crypto.randomUUID() };
      }
      const idempotencyKey = submissionAttempt.current.key;
      if (tab === "paste") {
        if (!text.trim()) {
          setError("Please paste or write content to check.");
          setLoading(false);
          return;
        }
        created = await api.createSubmission({
          title: title.trim(),
          intent: intent.trim(),
          text: text.trim(),
          content_type: "text",
          confidential,
        }, idempotencyKey);
      } else {
        if (!file) {
          setError("Please select a file to upload.");
          setLoading(false);
          return;
        }
        const formData = new FormData();
        formData.append("file", file);
        formData.append("title", title.trim());
        formData.append("intent", intent.trim());
        formData.append("confidential", String(confidential));
        created = await api.uploadSubmission(formData, (progress, message) => {
          setProgressPercent(progress);
          setProgressMessage(message);
        }, idempotencyKey);
      }

      // Automatically run governance check
      await api.checkSubmission(created.id, (progress, message) => {
        setProgressPercent(progress);
        setProgressMessage(message);
      });
      navigate(`/review/${created.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create and check submission.");
      setLoading(false);
      setProgressMessage("");
      setProgressPercent(0);
    }
  };

  return (
    <div className="new-submission-page max-w-3xl mx-auto px-4 py-8">
      <button
        onClick={() => navigate("/")}
        className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-6 font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      <div className="new-submission-card bg-white border border-stone-200 rounded-2xl shadow-sm p-6 sm:p-8">
        <div className="flex items-center justify-between pb-4 border-b border-stone-100 mb-6">
          <div>
            <h1 className="text-xl font-bold text-stone-900">New Pre-Publication Check</h1>
            <p className="text-xs text-stone-500 mt-1">
              Verify your copy against approved facts, guidelines, terminology, and accessibility rules.
            </p>
          </div>
          <div className="p-2.5 rounded-xl bg-amber-50 text-amber-700 border border-amber-200">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>

        <p className="mb-5 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950">
          AI-use disclosure: deterministic checks run locally. If an external language model is configured, non-confidential content may be sent to that provider. Mark a submission Confidential to block external model calls.
        </p>

        {error && (
          <div role="alert" className="mb-6 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-sm text-rose-700">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <section className="sample-picker" aria-labelledby="sample-picker-title">
            <div>
              <h2 id="sample-picker-title" className="text-sm font-semibold text-primary">Try a sample</h2>
              <p className="text-xs text-secondary">Load fictional copy with common brand-review issues into the form.</p>
            </div>
            <label className="ui-field text-sm font-medium" htmlFor="sample-submission">
              Choose a sample
              <select id="sample-submission" value="" onChange={(event) => applySample(event.target.value)} disabled={loading}>
                <option value="" disabled>Select a sample…</option>
                {SAMPLE_SUBMISSIONS.map((sample) => <option key={sample.id} value={sample.id}>{sample.title}</option>)}
              </select>
            </label>
          </section>

          {/* Title */}
          <div>
            <label htmlFor="submission-title" className="block text-sm font-semibold text-stone-700 mb-1">
              Submission Title <span className="text-rose-700">*</span>
            </label>
            <input
              id="submission-title"
              type="text"
              placeholder="e.g. Holiday Season Sourdough Campaign"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full px-3.5 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Stated Intent */}
          <div>
            <label htmlFor="submission-intent" className="block text-sm font-semibold text-stone-700 mb-1">
              Creator Intent: What is this content trying to achieve?
            </label>
            <input
              id="submission-intent"
              type="text"
              placeholder="e.g. Announce our organic oat elixir and emphasize our certified regional farm sourcing"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              className="w-full px-3.5 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p className="text-[11px] text-stone-500 mt-1">
              BrandGuard uses this stated purpose to ensure suggested rewrites preserve your original intent.
            </p>
          </div>

          <label className="flex min-h-11 items-start gap-3 rounded-xl bg-secondary p-3 text-sm text-primary">
            <input
              type="checkbox"
              checked={confidential}
              onChange={(event) => setConfidential(event.target.checked)}
              className="mt-1"
            />
            <span>
              <span className="block font-semibold">Confidential</span>
              <span className="text-xs text-secondary">Keep this submission out of external language-model checks. Local deterministic checks still run.</span>
            </span>
          </label>

          {/* Input Type Tabs */}
          <div className="pt-2">
            <div role="tablist" aria-label="Submission content source" className="ui-tabs mb-4">
              <button
                type="button"
                onClick={() => setTab("paste")}
                role="tab"
                aria-selected={tab === "paste"}
                disabled={loading}
                id="paste-tab"
                aria-controls="paste-panel"
                className={`py-2 px-4 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                  tab === "paste"
                    ? "border-stone-900 text-stone-900"
                    : "border-transparent text-stone-500 hover:text-stone-700"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                Paste Text / Markdown
              </button>
              <button
                type="button"
                onClick={() => setTab("upload")}
                role="tab"
                aria-selected={tab === "upload"}
                disabled={loading}
                id="upload-tab"
                aria-controls="upload-panel"
                className={`py-2 px-4 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                  tab === "upload"
                    ? "border-stone-900 text-stone-900"
                    : "border-transparent text-stone-500 hover:text-stone-700"
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
              Upload Document or Image
              </button>
            </div>

            {tab === "paste" ? (
              <div id="paste-panel" role="tabpanel" aria-labelledby="paste-tab">
                <label htmlFor="submission-text" className="sr-only">Submission text</label>
                <textarea
                  id="submission-text"
                  rows={8}
                  maxLength={200_000}
                  placeholder="Paste marketing copy, press releases, product descriptions, or email drafts..."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="w-full p-3.5 text-base font-sans border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 leading-relaxed"
                />
                <div className="flex justify-between items-center text-[11px] text-stone-400 mt-1">
                  <span>Cap: 20,000 words per check</span>
                  <span>{text.split(/\s+/).filter(Boolean).length} words</span>
                </div>
              </div>
            ) : (
              <div id="upload-panel" role="tabpanel" aria-labelledby="upload-tab" className="submission-upload border-2 border-dashed border-stone-300 rounded-xl p-8 text-center hover:border-amber-500 transition-colors bg-stone-50/50">
                <input
                  type="file"
                  id="file-upload"
                  accept=".txt,.md,.html,.pdf,.docx,.png,.jpg,.jpeg,.svg"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label htmlFor="file-upload" className="submission-upload__label cursor-pointer block">
                  <Upload className="w-8 h-8 text-stone-400 mx-auto mb-2" />
                  <p className="text-xs font-semibold text-stone-700">
                    {file ? file.name : "Click to select a document or image"}
                  </p>
                  <p className="text-[11px] text-stone-400 mt-1">
                    Supports text, Markdown, HTML, PDF, Word, PNG, JPEG, and SVG files up to 25 MB.
                  </p>
                </label>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="pt-4 flex items-center justify-end gap-3 border-t border-stone-100">
            {loading && (
              <div className="mr-auto min-w-40 flex-1" role="status" aria-live="polite" aria-label="Submission check progress">
                <div className="flex justify-between text-[11px] text-stone-600 mb-1">
                  <span>{progressMessage}</span><span>{progressPercent}%</span>
                </div>
                <div className="h-2 rounded-full bg-stone-200 overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent} aria-label="Review progress">
                  <div className="h-full bg-amber-500 transition-all" style={{ width: `${progressPercent}%` }} />
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => navigate("/")}
              className="ui-button ui-button--quiet"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="ui-button ui-button--primary"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                  {progressMessage || "Running Review Engine…"}
                </>
              ) : (
                "Run Brand Governance Check"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
