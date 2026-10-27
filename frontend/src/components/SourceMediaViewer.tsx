import React, { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Finding } from "../types";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

interface SourceLayout {
  width?: number;
  height?: number;
  pages?: Array<{ page: number; width: number; height: number }>;
}

interface SourceMediaViewerProps {
  mimeType: string;
  sourceUrl: string;
  sourceLayout?: SourceLayout | null;
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

const boxFor = (finding: Finding) => finding.location?.bbox;

interface FindingCanvasOverlayProps {
  findings: Finding[];
  selectedFindingId: string | null;
  sourceWidth: number;
  sourceHeight: number;
  pdfCoordinates?: boolean;
  onSelectFinding: (findingId: string) => void;
}

const FindingCanvasOverlay: React.FC<FindingCanvasOverlayProps> = ({
  findings,
  selectedFindingId,
  sourceWidth,
  sourceHeight,
  pdfCoordinates = false,
  onSelectFinding,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const draw = () => {
      const rect = parent.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.height * ratio);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      findings.forEach((finding) => {
        const bbox = boxFor(finding);
        if (!bbox || sourceWidth <= 0 || sourceHeight <= 0) return;
        const [x0, y0, x1, y1] = bbox;
        const x = (x0 / sourceWidth) * rect.width;
        const top = pdfCoordinates ? ((sourceHeight - y1) / sourceHeight) * rect.height : (y0 / sourceHeight) * rect.height;
        const width = ((x1 - x0) / sourceWidth) * rect.width;
        const height = ((y1 - y0) / sourceHeight) * rect.height;
        const selected = finding.id === selectedFindingId;
        const tokens = getComputedStyle(document.documentElement);
        context.fillStyle = tokens.getPropertyValue(selected ? "--highlight-selected-fill" : "--highlight-fill").trim();
        context.strokeStyle = tokens.getPropertyValue(selected ? "--highlight-selected-stroke" : "--highlight-stroke").trim();
        context.lineWidth = selected ? 3 : 2;
        context.fillRect(x, top, width, height);
        context.strokeRect(x, top, width, height);
      });
    };
    const observer = new ResizeObserver(draw);
    observer.observe(parent);
    const themeObserver = new MutationObserver(draw);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    draw();
    return () => {
      observer.disconnect();
      themeObserver.disconnect();
    };
  }, [findings, pdfCoordinates, selectedFindingId, sourceHeight, sourceWidth]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    for (const finding of [...findings].reverse()) {
      const bbox = boxFor(finding);
      if (!bbox) continue;
      const [x0, y0, x1, y1] = bbox;
      const left = (x0 / sourceWidth) * rect.width;
      const top = pdfCoordinates ? ((sourceHeight - y1) / sourceHeight) * rect.height : (y0 / sourceHeight) * rect.height;
      const boxWidth = ((x1 - x0) / sourceWidth) * rect.width;
      const boxHeight = ((y1 - y0) / sourceHeight) * rect.height;
      if (x >= left && x <= left + boxWidth && y >= top && y <= top + boxHeight) {
        onSelectFinding(finding.id);
        return;
      }
    }
  };

  return <canvas ref={canvasRef} onClick={handleClick} className="absolute inset-0 pointer-events-auto cursor-pointer" aria-label="Located review findings" />;
};

export const SourceMediaViewer: React.FC<SourceMediaViewerProps> = ({
  mimeType,
  sourceUrl,
  sourceLayout,
  findings,
  selectedFindingId,
  onSelectFinding,
}) => {
  const [imageDimensions, setImageDimensions] = useState({
    width: sourceLayout?.width || 0,
    height: sourceLayout?.height || 0,
  });
  const [documentError, setDocumentError] = useState<string | null>(null);

  if (mimeType === "application/pdf") {
    const pages = sourceLayout?.pages || [];
    return (
      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b border-stone-200 text-xs font-semibold text-stone-700">
          PDF page review
        </div>
        <div className="p-4 max-h-[75vh] overflow-auto bg-stone-100 space-y-5">
          {documentError && <p role="alert" className="text-xs text-rose-700">{documentError}</p>}
          <Document
            file={sourceUrl}
            onLoadError={(error) => setDocumentError(error.message || "Unable to render this PDF.")}
            loading={<p className="text-xs text-stone-500">Rendering PDF pages…</p>}
          >
            {pages.map((page) => {
              const pageFindings = findings.filter((finding) => finding.location?.page === page.page && boxFor(finding));
              return (
                <div key={page.page} className="relative w-fit mx-auto shadow-md bg-white">
                  <Page pageNumber={page.page} width={680} renderTextLayer={false} renderAnnotationLayer={false} />
                  {pageFindings.length > 0 && (
                    <FindingCanvasOverlay
                      findings={pageFindings}
                      selectedFindingId={selectedFindingId}
                      sourceWidth={page.width}
                      sourceHeight={page.height}
                      pdfCoordinates
                      onSelectFinding={onSelectFinding}
                    />
                  )}
                </div>
              );
            })}
          </Document>
        </div>
      </div>
    );
  }

  if (mimeType.startsWith("image/")) {
    const width = imageDimensions.width || 1;
    const height = imageDimensions.height || 1;
    const imageFindings = findings.filter((finding) => boxFor(finding));
    return (
      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="px-5 py-3 bg-stone-50 border-b border-stone-200 text-xs font-semibold text-stone-700">
          Image review · {imageFindings.length} located finding{imageFindings.length === 1 ? "" : "s"}
        </div>
        <div className="p-4 max-h-[75vh] overflow-auto bg-stone-100">
          <div className="relative inline-block max-w-full mx-auto">
            <img
              src={sourceUrl}
              alt="Uploaded creative under review"
              className="block max-w-full max-h-[68vh] w-auto h-auto"
              onLoad={(event) => setImageDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })}
              onError={() => setDocumentError("Unable to render this image.")}
            />
            {imageFindings.length > 0 && (
              <FindingCanvasOverlay
                findings={imageFindings}
                selectedFindingId={selectedFindingId}
                sourceWidth={width}
                sourceHeight={height}
                onSelectFinding={onSelectFinding}
              />
            )}
          </div>
          {documentError && <p role="alert" className="mt-3 text-xs text-rose-700">{documentError}</p>}
        </div>
      </div>
    );
  }

  return null;
};
