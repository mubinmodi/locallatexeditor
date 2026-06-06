import { useEffect, useRef, useCallback, type RefObject } from "react";
import DOMPurify from "dompurify";
import katex from "katex";
import * as pdfjs from "pdfjs-dist";
import pdfjsWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "katex/dist/katex.min.css";
import "./Preview.css";

pdfjs.GlobalWorkerOptions.workerSrc = pdfjsWorker;

export type PreviewMode = "pdf" | "html";

interface PreviewProps {
  mode: PreviewMode;
  pdfBlob?: Blob | null;
  html?: string;
  pending?: boolean;
  showLoadingOverlay?: boolean;
  loadingLabel?: string;
  pdfRenderKey?: string;
  ready?: boolean;
}

const PAGE_WIDTH = 816;
const PAGE_MIN_HEIGHT = 1056;

const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    "h1", "h2", "h3", "h4", "h5", "p", "div", "span", "strong", "em", "u", "code",
    "a", "ul", "ol", "li", "table", "tr", "td", "th", "thead", "tbody",
    "pre", "blockquote", "br", "sup",
  ],
  ALLOWED_ATTR: ["class", "href", "rel"],
  ALLOW_DATA_ATTR: false,
};

function HtmlPreview({ html }: { html: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scalerRef = useRef<HTMLDivElement>(null);

  const updateScale = useCallback(() => {
    const scaler = scalerRef.current;
    const page = containerRef.current;
    const wrapper = scaler?.closest(".preview-wrapper");
    if (!scaler || !page || !wrapper) return;
    const available = wrapper.clientWidth - 32;
    const scale = Math.min(1, available / PAGE_WIDTH);
    scaler.style.transform = `scale(${scale})`;
    scaler.style.width = `${PAGE_WIDTH}px`;
    scaler.style.marginBottom = `${page.offsetHeight * (scale - 1)}px`;
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const safe = DOMPurify.sanitize(html, PURIFY_CONFIG);
    containerRef.current.innerHTML = safe;

    containerRef.current.querySelectorAll(".math-display").forEach((el) => {
      const latex = el.textContent || "";
      try {
        katex.render(latex, el as HTMLElement, {
          displayMode: true,
          throwOnError: false,
        });
      } catch {
        /* leave raw */
      }
    });

    containerRef.current.querySelectorAll(".math-inline").forEach((el) => {
      const latex = el.textContent || "";
      try {
        katex.render(latex, el as HTMLElement, {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        /* leave raw */
      }
    });

    updateScale();
  }, [html, updateScale]);

  useEffect(() => {
    const wrapper = scalerRef.current?.closest(".preview-wrapper");
    if (!wrapper) return;
    const obs = new ResizeObserver(updateScale);
    obs.observe(wrapper);
    return () => obs.disconnect();
  }, [updateScale]);

  return (
    <div className="preview-html-scaler" ref={scalerRef}>
      <div
        className="preview-page"
        ref={containerRef}
        style={{ minHeight: PAGE_MIN_HEIGHT }}
      />
    </div>
  );
}

function PdfPreview({
  pdfBlob,
  renderKey,
  wrapperRef,
}: {
  pdfBlob: Blob;
  renderKey: string;
  wrapperRef: RefObject<HTMLDivElement | null>;
}) {
  const pagesRef = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);
  const lastWidthRef = useRef(0);

  const measureWidth = useCallback(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return 0;
    return Math.max(wrapper.clientWidth - 32, 0);
  }, [wrapperRef]);

  useEffect(() => {
    const container = pagesRef.current;
    if (!container) return;

    const renderId = ++renderIdRef.current;
    let objectUrl: string | null = null;
    let cancelled = false;

    const render = async (targetWidth: number) => {
      objectUrl = URL.createObjectURL(pdfBlob);
      try {
        const pdf = await pdfjs.getDocument({ url: objectUrl }).promise;
        if (renderId !== renderIdRef.current || cancelled) return;

        container.innerHTML = "";
        const availableWidth = Math.max(targetWidth, 320);

        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          if (renderId !== renderIdRef.current || cancelled) return;
          const page = await pdf.getPage(pageNum);
          const base = page.getViewport({ scale: 1 });
          const scale = availableWidth / base.width;
          const viewport = page.getViewport({ scale });
          const dpr = window.devicePixelRatio || 1;
          const renderViewport = page.getViewport({ scale: scale * dpr });

          const canvas = document.createElement("canvas");
          canvas.className = "preview-pdf-page";
          const ctx = canvas.getContext("2d");
          if (!ctx) continue;

          canvas.width = renderViewport.width;
          canvas.height = renderViewport.height;
          canvas.style.width = `${viewport.width}px`;
          canvas.style.maxWidth = "100%";
          canvas.style.height = "auto";

          await page.render({
            canvas,
            canvasContext: ctx,
            viewport: renderViewport,
          }).promise;

          if (renderId !== renderIdRef.current || cancelled) return;
          container.appendChild(canvas);
        }
        lastWidthRef.current = availableWidth;
      } catch {
        if (renderId === renderIdRef.current && !cancelled) {
          container.innerHTML =
            '<p class="preview-pdf-error">Could not render PDF preview.</p>';
        }
      } finally {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      }
    };

    const scheduleRender = () => {
      const width = measureWidth();
      if (width < 80) return false;
      render(width);
      return true;
    };

    if (!scheduleRender()) {
      const waitForWidth = () => {
        if (renderId !== renderIdRef.current || cancelled) return;
        if (scheduleRender()) return;
        requestAnimationFrame(waitForWidth);
      };
      requestAnimationFrame(waitForWidth);
    }

    const wrapper = wrapperRef.current;
    if (!wrapper) {
      return () => {
        cancelled = true;
        renderIdRef.current++;
      };
    }

    let resizeTimer: ReturnType<typeof setTimeout>;
    const obs = new ResizeObserver(() => {
      const width = measureWidth();
      if (width < 80 || Math.abs(width - lastWidthRef.current) < 12) return;
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        renderIdRef.current++;
        render(width);
      }, 250);
    });
    obs.observe(wrapper);

    return () => {
      cancelled = true;
      clearTimeout(resizeTimer);
      obs.disconnect();
      renderIdRef.current++;
    };
  }, [pdfBlob, renderKey, measureWidth, wrapperRef]);

  return <div className="preview-pdf-pages" ref={pagesRef} />;
}

export default function Preview({
  mode,
  pdfBlob,
  html = "",
  pending = false,
  showLoadingOverlay = false,
  loadingLabel = "Updating preview…",
  pdfRenderKey = "",
  ready = true,
}: PreviewProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const hasPdf = mode === "pdf" && pdfBlob;
  const hasHtml = mode === "html" && html;

  return (
    <div
      ref={wrapperRef}
      className={`preview-wrapper${pending ? " preview-pending" : ""}`}
    >
      {(showLoadingOverlay || (pending && !hasPdf && !hasHtml)) && (
        <div className="preview-loading">{loadingLabel}</div>
      )}
      {pending && (hasPdf || hasHtml) && (
        <div className="preview-pending-badge">Updating…</div>
      )}
      <div
        className={`preview-content${pending ? " preview-content-dimmed" : ""}`}
      >
        {hasPdf ? (
          <PdfPreview
            pdfBlob={pdfBlob}
            renderKey={pdfRenderKey}
            wrapperRef={wrapperRef}
          />
        ) : hasHtml ? (
          <HtmlPreview html={html} />
        ) : (
          ready &&
          !pending && (
            <p className="preview-empty">
              {mode === "pdf"
                ? "PDF preview will appear here."
                : "Preview will appear here."}
            </p>
          )
        )}
      </div>
    </div>
  );
}
