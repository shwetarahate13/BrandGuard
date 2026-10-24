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
      className={`font-mono text-sm leading-relaxed bg-stone-900 text-stone-100 p-3 rounded-md overflow-x-auto border border-stone-800 ${className}`}
    >
      <div className="text-xs font-sans text-stone-400 mb-2 uppercase tracking-wider flex items-center justify-between">
        <span>Word-Level Fix Diff</span>
        <span className="text-[10px] lowercase text-stone-400">
          <span className="text-rose-400 line-through mr-2">removed</span>
          <span className="text-emerald-400 font-semibold">suggested</span>
        </span>
      </div>
      <div className="whitespace-pre-wrap">
        {diffParts.map((part, index) => {
          if (part.added) {
            return (
              <span
                key={index}
                className="bg-emerald-950/80 text-emerald-300 font-semibold px-1 rounded border-b-2 border-emerald-400 inline-block"
              >
                {part.value}
              </span>
            );
          }
          if (part.removed) {
            return (
              <span
                key={index}
                className="bg-rose-950/80 text-rose-300 line-through decoration-rose-400 px-1 rounded inline-block"
              >
                {part.value}
              </span>
            );
          }
          return <span key={index} className="text-stone-300">{part.value}</span>;
        })}
      </div>
    </div>
  );
};
