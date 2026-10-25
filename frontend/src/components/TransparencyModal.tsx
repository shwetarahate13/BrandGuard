import React from "react";
import { ShieldCheck, X, ExternalLink, Cpu } from "lucide-react";

interface TransparencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  llmMode: string;
}

export const TransparencyModal: React.FC<TransparencyModalProps> = ({
  isOpen,
  onClose,
  llmMode,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-xl max-w-xl w-full border border-stone-200 shadow-2xl p-6 relative animate-in fade-in zoom-in-95 duration-150">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-stone-700 p-1 rounded-lg"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-200">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-semibold text-stone-900 text-lg">Responsible AI & System Transparency</h3>
            <p className="text-xs text-stone-500">How BrandGuard protects your data and sources</p>
          </div>
        </div>

        <div className="space-y-4 text-sm text-stone-600">
          <div className="p-3 bg-stone-50 rounded-lg border border-stone-200">
            <div className="flex items-center justify-between text-xs font-semibold text-stone-700 mb-1">
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-brand-600" />
                Active Review Engine
              </span>
              <span className="font-mono bg-stone-200/80 px-2 py-0.5 rounded text-stone-800">
                {llmMode}
              </span>
            </div>
            <p className="text-xs text-stone-500">
              {llmMode.includes("mock")
                ? "Running in deterministic offline mode (rules + TF-IDF embeddings + templated intent-aware fixes). No external API calls are made."
                : "External Claude API provider enabled. Excerpts are transmitted securely over TLS for reasoning checks."}
            </p>
          </div>

          <div className="space-y-2">
            <h4 className="font-medium text-stone-900 text-xs uppercase tracking-wider">
              Core Governance Principles
            </h4>
            <ul className="space-y-2 text-xs">
              <li className="flex items-start gap-2">
                <span className="font-bold text-amber-700">1. Grounded or Silent:</span>
                <span>
                  Every finding must cite an approved guideline, fact, or term. No ungrounded hallucinations are permitted.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-amber-700">2. Excerpt Privacy:</span>
                <span>
                  Whole document libraries are never shared. Only the specific span and top-k retrieved source snippets are evaluated.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-amber-700">3. AI Suggests, People Decide:</span>
                <span>
                  The AI never edits, approves, or publishes on its own. All fixes require explicit human review and acceptance.
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-stone-100 flex items-center justify-between text-xs text-stone-500">
          <a
            href="/limitations"
            className="text-brand-700 hover:text-brand-800 font-medium inline-flex items-center gap-1"
          >
            Read Known Limitations <ExternalLink className="w-3 h-3" />
          </a>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-stone-900 text-white rounded-lg text-xs font-medium hover:bg-stone-800"
          >
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  );
};
