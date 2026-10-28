import React, { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Finding } from "../types";
import { Badge, Button, EmptyState } from "./ui";

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
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [pdfPageCount, setPdfPageCount] = useState(0);
  const [pdfPageWidth, setPdfPageWidth] = useState(680);
  const pdfCanvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setDocumentError(null);
    setPdfPageCount(0);
    setImageDimensions({ width: sourceLayout?.width || 0, height: sourceLayout?.height || 0 });
  }, [mimeType, sourceUrl, sourceLayout?.width, sourceLayout?.height]);

  useEffect(() => {
    const container = pdfCanvasRef.current;
    if (!container || mimeType !== "application/pdf") return;
    const resize = () => setPdfPageWidth(Math.max(220, Math.min(680, container.clientWidth - 24)));
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    return () => observer.disconnect();
  }, [mimeType, sourceUrl]);

  const retryRender = () => {
    setDocumentError(null);
    setRenderAttempt((attempt) => attempt + 1);
  };

  const locatedFindings = findings.filter((finding) => boxFor(finding));
  const findingIndex = locatedFindings.length > 0 ? (
    <div className="source-media-viewer__finding-index" aria-label="Located findings">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-primary">Located findings</h3>
        <Badge tone="info">{locatedFindings.length}</Badge>
      </div>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {locatedFindings.map((finding, index) => <li key={finding.id}>
          <Button type="button" variant={finding.id === selectedFindingId ? "primary" : "quiet"} aria-pressed={finding.id === selectedFindingId} className="source-media-viewer__finding w-full justify-start text-left" onClick={() => onSelectFinding(finding.id)}>
            <span className="source-media-viewer__finding-number">{index + 1}</span>
            <span className="min-w-0"><strong className="block truncate">{finding.issue}</strong><span className="block text-xs opacity-80">{finding.category}{finding.location?.page ? ` · Page ${finding.location.page}` : ""}</span></span>
          </Button>
        </li>)}
      </ul>
    </div>
  ) : <EmptyState className="py-5" title="No located findings" description="Review findings are still available in the findings panel." />;

  if (mimeType === "application/pdf") {
    const pages = sourceLayout?.pages?.length ? sourceLayout.pages : Array.from({ length: pdfPageCount }, (_, index) => ({ page: index + 1, width: sourceLayout?.width || 0, height: sourceLayout?.height || 0 }));
    return (
      <section className="source-media-viewer ui-card overflow-hidden" aria-label="PDF page review">
        <header className="source-media-viewer__header">
          <div><h2>PDF page review</h2><p>Highlight overlays are linked to the findings list.</p></div>
          <Badge tone="info">{locatedFindings.length} located</Badge>
        </header>
        <div ref={pdfCanvasRef} className="source-media-viewer__canvas source-media-viewer__canvas--pdf">
          {documentError && <div role="alert" className="source-media-viewer__error"><span>{documentError}</span><Button variant="secondary" onClick={retryRender}>Retry preview</Button></div>}
          <Document
            key={`${sourceUrl}-${renderAttempt}`}
            file={sourceUrl}
            onLoadSuccess={(pdf) => { setPdfPageCount(pdf.numPages); setDocumentError(null); }}
            onLoadError={(error) => setDocumentError(error.message || "Unable to render this PDF.")}
            loading={<p role="status" className="source-media-viewer__loading">Rendering PDF pages…</p>}
          >
            {pages.length === 0 && <p className="source-media-viewer__loading">Waiting for PDF page details…</p>}
            {pages.map((page) => {
              const pageFindings = findings.filter((finding) => finding.location?.page === page.page && boxFor(finding));
              return (
                <div key={page.page} className="source-media-viewer__pdf-page">
                  <Page pageNumber={page.page} width={pdfPageWidth} renderTextLayer={false} renderAnnotationLayer={false} onRenderError={(error) => setDocumentError(error.message || `Unable to render PDF page ${page.page}.`)} />
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
          {documentError && <p className="sr-only" role="status">PDF preview unavailable. The extracted document text remains available for review.</p>}
        </div>
        <div className="source-media-viewer__footer">
          {locatedFindings.length > 0 && <p className="source-media-viewer__hint">Select a finding to focus its highlight. You can also select a finding below.</p>}
          {findingIndex}
        </div>
      </section>
    );
  }

  if (mimeType.startsWith("image/")) {
    const width = imageDimensions.width || 1;
    const height = imageDimensions.height || 1;
    const imageFindings = findings.filter((finding) => boxFor(finding));
    return (
      <section className="source-media-viewer ui-card overflow-hidden" aria-label="Image review">
        <header className="source-media-viewer__header">
          <div><h2>Image review</h2><p>Boxes show where a finding was detected in the image.</p></div>
          <Badge tone="info">{imageFindings.length} located</Badge>
        </header>
        <div className="source-media-viewer__canvas source-media-viewer__canvas--image">
          <div className="source-media-viewer__image-frame">
            <img
              key={`${sourceUrl}-${renderAttempt}`}
              src={sourceUrl}
              alt="Uploaded creative under review"
              className="source-media-viewer__image"
              onLoad={(event) => setImageDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })}
              onError={() => setDocumentError("Unable to render this image. The file may be corrupt or unavailable.")}
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
          {documentError && <div role="alert" className="source-media-viewer__error"><span>{documentError}</span><Button variant="secondary" onClick={retryRender}>Retry preview</Button></div>}
        </div>
        <div className="source-media-viewer__footer">
          {imageFindings.length > 0 && <p className="source-media-viewer__hint">Select a finding to focus its highlight. You can also select a finding below.</p>}
          {findingIndex}
        </div>
      </section>
    );
  }

  return null;
};
