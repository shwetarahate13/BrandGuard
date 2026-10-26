import React from "react";
import { X } from "lucide-react";
import { UserRole } from "../types";

interface OnboardingTipsProps {
  role: UserRole;
  onClose: () => void;
}

const tips: Record<UserRole, { title: string; steps: string[] }> = {
  creator: {
    title: "Start with a content check",
    steps: [
      "Create a text or file submission from New Submission, then run the review check.",
      "Open findings to accept a suggested fix, edit it, or dispute it with a reason.",
      "Submit checked content for review. If changes are requested, revise, check again, and resubmit.",
    ],
  },
  manager: {
    title: "Manage the approval queue",
    steps: [
      "Use the queue to search, filter, and open submissions waiting for review.",
      "Assign a reviewer when needed; assignments include a due date you can change.",
      "Approve standard-risk content, request changes, or reject it. High-risk content needs an assigned reviewer to sign off.",
      "Use Guideline Health to inspect dispute trends and recompute the latest health metrics.",
    ],
  },
  reviewer: {
    title: "Review assigned content",
    steps: [
      "Your Compliance Desk lists submissions assigned to you and their due dates.",
      "Inspect findings and their source evidence, then add a compliance note when making a decision.",
      "High-risk content requires reviewer sign-off. You can only decide submissions assigned to you.",
    ],
  },
  admin: {
    title: "Set up and monitor the workspace",
    steps: [
      "Create and manage user accounts and roles from the Admin Console.",
      "Maintain approved sources and runtime settings, and review the audit log for recorded activity.",
      "Admins can manage the system but do not approve submissions; managers and assigned reviewers handle those decisions.",
    ],
  },
};

export const OnboardingTips: React.FC<OnboardingTipsProps> = ({ role, onClose }) => {
  const content = tips[role];
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-stone-950/60 p-4" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        className="w-full max-w-lg rounded-2xl border border-stone-200 bg-white p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-brand-700">{role} quick start</p>
            <h2 id="onboarding-title" className="mt-1 text-xl font-extrabold text-stone-900">{content.title}</h2>
          </div>
          <button type="button" aria-label="Close tips" onClick={onClose} className="rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-900">
            <X className="h-4 w-4" />
          </button>
        </div>
        <ol className="mt-5 space-y-3">
          {content.steps.map((step, index) => (
            <li key={step} className="flex gap-3 text-sm leading-relaxed text-stone-700">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-extrabold text-amber-800">{index + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <div className="mt-6 flex justify-end">
          <button type="button" onClick={onClose} className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-bold text-white hover:bg-stone-800">
            Got it
          </button>
        </div>
      </section>
    </div>
  );
};
