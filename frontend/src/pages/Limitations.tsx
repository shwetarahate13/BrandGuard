import React from "react";
import { ArrowLeft, CheckCircle2, Lock, AlertCircle } from "lucide-react";

interface LimitationsProps {
  navigate: (path: string) => void;
}

export const Limitations: React.FC<LimitationsProps> = ({ navigate }) => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div>
        <button
          onClick={() => navigate("/")}
          className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-900 mb-4 font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Known Limitations & Disclosures</h1>
        <p className="text-xs text-stone-500 mt-1">
          Current review, security, and local-run boundaries.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Scope Boundaries */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <AlertCircle className="w-4 h-4 text-amber-600" />
            <span>Review Boundaries</span>
          </div>
          <ul className="space-y-2 text-xs text-stone-600 list-disc list-inside">
            <li>
              <strong>No auto-publishing:</strong> BrandGuard does not publish to a CMS, social network, or advertising platform. Publishing happens outside the app after human review.
            </li>
            <li>
              <strong>Document review:</strong> TXT, DOCX, and PDF uploads are reviewed as extracted text. PDF finding highlights use extracted page coordinates and may be approximate for complex, rotated, or decorative layouts. DOCX is not reviewed as rendered pages.
            </li>
            <li>
              <strong>Image review:</strong> Local setup enables PNG, JPEG, and sanitized SVG checks. OCR can miss stylized text; palette and logo checks depend on approved asset records, and clear-space checks need a measurable guideline.
            </li>
            <li>
              <strong>Input limits:</strong> Uploads are capped at 25 MB, raster images at 30 megapixels, and text checks at 20,000 words.
            </li>
          </ul>
        </div>

        {/* Security & Data Integrity */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <Lock className="w-4 h-4 text-emerald-600" />
            <span>Application Security</span>
          </div>
          <ul className="space-y-2 text-xs text-stone-600 list-disc list-inside">
            <li>
              <strong>Passwords:</strong> New passwords are hashed with bcrypt and must be at least 12 characters (maximum 72 UTF-8 bytes).
            </li>
            <li>
              <strong>Authentication:</strong> API sessions use bearer JWTs with an eight-hour default lifetime. Production requires a 32-byte-or-longer signing secret.
            </li>
            <li>
              <strong>Rate limits:</strong> Login lockout and endpoint limits are stored in process memory and are not shared across multiple workers or replicas.
            </li>
            <li>
              <strong>Transport and storage:</strong> The local app sets security headers. The local database, uploaded files, and backups remain under the computer user's control.
            </li>
            <li>
              <strong>External LLMs:</strong> When Anthropic is enabled, each reviewed text segment, the creator's stated intent, and retrieved source excerpts are sent to the provider. Guideline rewrite requests send the current clause and dispute examples. Mock/offline mode makes no external LLM request.
            </li>
          </ul>
        </div>

        {/* Responsible AI Principles */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <CheckCircle2 className="w-4 h-4 text-brand-600" />
            <span>Workspace and Feedback Boundaries</span>
          </div>
          <p className="text-xs text-stone-600 leading-relaxed">
            This local workspace has no team or tenant boundary. Dispute statistics and repeated-pattern suppression are shared across it. The persistent in-app inbox covers reviewer assignments and workflow approval/changes/rejection events; it does not notify on finding-level decisions, comments, or email. The Creator dashboard also shows derived activity messages from decisions and review comments. Human review is required before content is published.
          </p>
        </div>
      </div>
    </div>
  );
};
