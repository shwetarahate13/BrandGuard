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
          Honest disclosures on Round 2 capabilities, security model, and out-of-scope boundaries.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Scope Boundaries */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <AlertCircle className="w-4 h-4 text-amber-600" />
            <span>Deliberately Out of Scope (Round 2 Build)</span>
          </div>
          <ul className="space-y-2 text-xs text-stone-600 list-disc list-inside">
            <li>
              <strong>No Auto-Publishing:</strong> BrandGuard will never publish directly to social media or CMS platforms. Human managers must sign off and take final publishing action.
            </li>
            <li>
              <strong>Document Review:</strong> Uploaded PDFs retain page and text bounding-box coordinates for visual review. DOCX files are checked as extracted text.
            </li>
            <li>
              <strong>Image Review:</strong> PNG, JPEG, and SVG uploads are checked for approved palette colors, approved logo clear space, and detected text contrast. OCR and logo matching depend on readable source assets and installed image-processing services.
            </li>
            <li>
              <strong>No Real-time Multi-Cursor Co-editing:</strong> Governance occurs via revision drafts, word-level diff suggestions, and structured comments.
            </li>
          </ul>
        </div>

        {/* Security & Data Integrity */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <Lock className="w-4 h-4 text-emerald-600" />
            <span>Honest Security & Encryption Model</span>
          </div>
          <ul className="space-y-2 text-xs text-stone-600 list-disc list-inside">
            <li>
              <strong>In-Transit Security:</strong> Encrypted via HTTPS/TLS 1.3 terminated at the host (Render).
            </li>
            <li>
              <strong>At-Rest Security:</strong> Storage at rest is managed and encrypted by Neon managed PostgreSQL and host volume providers.
            </li>
            <li>
              <strong>Authentication:</strong> Passwords hashed with standard bcrypt. Session access managed through expiring JWT tokens.
            </li>
            <li>
              <strong>Prompt Injection Defense:</strong> All user content passed to review models is delimited with strict unverified markers and prompt directives preventing execution of user instructions.
            </li>
            <li>
              <strong>Privacy Boundary:</strong> Complete brand source libraries are never submitted to external LLMs; only top-k retrieved source snippets are supplied per evaluation window.
            </li>
          </ul>
        </div>

        {/* Responsible AI Principles */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
            <CheckCircle2 className="w-4 h-4 text-brand-600" />
            <span>Responsible AI Principles</span>
          </div>
          <p className="text-xs text-stone-600 leading-relaxed">
            BrandGuard is architected on the hard principle of <strong>Grounded or Silent</strong>: every finding must cite a verified source in the brand kit with an exact quote. When confidence is low or ambiguous, findings are flagged for human reviewer resolution rather than asserting artificial claims.
          </p>
        </div>
      </div>
    </div>
  );
};
