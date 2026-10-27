import React, { useState } from "react";
import { Upload, FileText, ArrowLeft, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { api } from "../api";
interface NewSubmissionProps {
  navigate: (path: string) => void;
}

export const NewSubmission: React.FC<NewSubmissionProps> = ({ navigate }) => {
  const [tab, setTab] = useState<"paste" | "upload">("paste");
  const [title, setTitle] = useState("");
  const [intent, setIntent] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.size > 25 * 1024 * 1024) {
        setError("File size exceeds 25 MB limit. Please select a smaller document.");
        return;
      }
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
        });
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
        created = await api.uploadSubmission(formData, (progress, message) => {
          setProgressPercent(progress);
          setProgressMessage(message);
        });
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
    <div className="max-w-3xl mx-auto px-4 py-8">
      <button
        onClick={() => navigate("/")}
        className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-6 font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm p-6 sm:p-8">
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

        {error && (
          <div className="mb-6 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-xs text-rose-700">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1">
              Submission Title <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Holiday Season Sourdough Campaign"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full px-3.5 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Stated Intent */}
          <div>
            <label className="block text-xs font-semibold text-stone-700 mb-1">
              Creator Intent: What is this content trying to achieve?
            </label>
            <input
              type="text"
              placeholder="e.g. Announce our organic oat elixir and emphasize our certified regional farm sourcing"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              className="w-full px-3.5 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p className="text-[11px] text-stone-500 mt-1">
              BrandGuard uses this stated purpose to ensure suggested rewrites preserve your original intent.
            </p>
          </div>

          {/* Input Type Tabs */}
          <div className="pt-2">
            <div className="flex border-b border-stone-200 mb-4">
              <button
                type="button"
                onClick={() => setTab("paste")}
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
              <div>
                <textarea
                  rows={8}
                  maxLength={200_000}
                  placeholder="Paste marketing copy, press releases, product descriptions, or email drafts..."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="w-full p-3.5 text-sm font-sans border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 leading-relaxed"
                />
                <div className="flex justify-between items-center text-[11px] text-stone-400 mt-1">
                  <span>Cap: 20,000 words per check</span>
                  <span>{text.split(/\s+/).filter(Boolean).length} words</span>
                </div>
              </div>
            ) : (
              <div className="border-2 border-dashed border-stone-300 rounded-xl p-8 text-center hover:border-amber-500 transition-colors bg-stone-50/50">
                <input
                  type="file"
                  id="file-upload"
                  accept=".txt,.md,.html,.pdf,.docx,.png,.jpg,.jpeg,.svg"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label htmlFor="file-upload" className="cursor-pointer block">
                  <Upload className="w-8 h-8 text-stone-400 mx-auto mb-2" />
                  <p className="text-xs font-semibold text-stone-700">
                    {file ? file.name : "Click to select or drag and drop a document or image"}
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
              <div className="mr-auto min-w-40 flex-1" role="status" aria-live="polite">
                <div className="flex justify-between text-[11px] text-stone-600 mb-1">
                  <span>{progressMessage}</span><span>{progressPercent}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-stone-200 overflow-hidden">
                  <div className="h-full bg-amber-500 transition-all" style={{ width: `${progressPercent}%` }} />
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => navigate("/")}
              className="px-4 py-2 text-xs font-medium text-stone-600 hover:bg-stone-100 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow transition-all disabled:opacity-50"
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
