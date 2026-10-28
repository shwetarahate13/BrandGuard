import React from "react";
import * as Diff from "diff";

interface DiffViewerProps {
  original: string;
  replacement: string;
  className?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  original,
  replacement,
  className = "",
}) => {
  const diffParts = Diff.diffWordsWithSpace(original, replacement);

  return (
    <div
      className={`diff-viewer font-mono text-sm leading-relaxed p-4 rounded-xl overflow-x-auto ${className}`}
      aria-label="Word-level suggested wording changes"
    >
      <div className="diff-viewer__heading text-xs font-sans mb-3 uppercase tracking-wider flex flex-wrap items-center justify-between gap-2">
        <span>Word-Level Fix Diff</span>
        <span className="text-[10px] lowercase">
          <span className="diff-viewer__removed line-through mr-2">removed</span>
          <span className="diff-viewer__added font-semibold">suggested</span>
        </span>
      </div>
      <div className="whitespace-pre-wrap">
        {diffParts.map((part, index) => {
          if (part.added) {
            return (
              <span
                key={index}
                className="diff-viewer__added font-semibold px-1 rounded border-b-2 inline-block"
              >
                {part.value}
              </span>
            );
          }
          if (part.removed) {
            return (
              <span
                key={index}
                className="diff-viewer__removed line-through px-1 rounded inline-block"
              >
                {part.value}
              </span>
            );
          }
          return <span key={index} className="diff-viewer__unchanged">{part.value}</span>;
        })}
      </div>
    </div>
  );
};
