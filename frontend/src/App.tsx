import { useState, useEffect, useCallback, useRef } from "react";
import Editor, { DEFAULT_TEMPLATE } from "./components/Editor";
import Preview, { type PreviewMode } from "./components/Preview";
import {
  previewPdfLatex,
  previewHtmlLatex,
  compileLatex,
  checkHealth,
  formatErrorTail,
} from "./api";
import { useDebounce } from "./hooks/useDebounce";
import "./App.css";

const STORAGE_KEY = "latex-editor-content";
const PDF_PREVIEW_DEBOUNCE_MS = 1200;
const HTML_PREVIEW_DEBOUNCE_MS = 500;

type CompileStatus = "idle" | "compiling" | "success" | "error";

function loadStoredLatex(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ?? DEFAULT_TEMPLATE;
  } catch {
    return DEFAULT_TEMPLATE;
  }
}

export default function App() {
  const [latex, setLatex] = useState(loadStoredLatex);
  const [html, setHtml] = useState("");
  const [previewPdf, setPreviewPdf] = useState<Blob | null>(null);
  const [previewForLatex, setPreviewForLatex] = useState<string | null>(null);
  const [status, setStatus] = useState<CompileStatus>("idle");
  const [pdflatexAvailable, setPdflatexAvailable] = useState(false);
  const [backendOk, setBackendOk] = useState(true);
  const [healthReady, setHealthReady] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [compileError, setCompileError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const pdfBlobRef = useRef<Blob | null>(null);
  const [hasPdf, setHasPdf] = useState(false);
  const [editorWidth, setEditorWidth] = useState(50);
  const dragging = useRef(false);
  const layoutRef = useRef<HTMLDivElement>(null);
  const previewSeqRef = useRef(0);
  const compiledLatexRef = useRef<string | null>(null);
  const cachedPreviewRef = useRef<{ latex: string; blob: Blob } | null>(null);

  const previewMode: PreviewMode = pdflatexAvailable ? "pdf" : "html";
  const debouncedLatex = useDebounce(
    latex,
    previewMode === "pdf" ? PDF_PREVIEW_DEBOUNCE_MS : HTML_PREVIEW_DEBOUNCE_MS
  );

  const previewMatchesEditor =
    previewForLatex !== null && previewForLatex === latex;
  const previewPending =
    latex !== debouncedLatex || (previewLoading && previewForLatex !== debouncedLatex);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, latex);
    } catch {
      /* storage full or disabled */
    }
  }, [latex]);

  useEffect(() => {
    checkHealth()
      .then((h) => {
        setBackendOk(true);
        setPdflatexAvailable(h.pdflatex_available);
      })
      .catch(() => {
        setBackendOk(false);
        setPdflatexAvailable(false);
      })
      .finally(() => setHealthReady(true));
  }, []);

  useEffect(() => {
    if (
      compiledLatexRef.current !== null &&
      latex !== compiledLatexRef.current
    ) {
      pdfBlobRef.current = null;
      setHasPdf(false);
      setStatus((s) => (s === "success" ? "idle" : s));
    }
  }, [latex]);

  useEffect(() => {
    if (!backendOk || !healthReady) return;

    const controller = new AbortController();
    const seq = ++previewSeqRef.current;
    const sourceAtRequest = debouncedLatex;
    setPreviewLoading(true);

    const runPreview =
      previewMode === "pdf" ? previewPdfLatex : previewHtmlLatex;

    runPreview(sourceAtRequest, controller.signal)
      .then((result) => {
        if (seq !== previewSeqRef.current) return;

        if (previewMode === "pdf") {
          const blob = result as Blob;
          setPreviewPdf(blob);
          setHtml("");
          cachedPreviewRef.current = { latex: sourceAtRequest, blob };
        } else {
          setHtml(result as string);
          setPreviewPdf(null);
        }
        setPreviewForLatex(sourceAtRequest);
        setPreviewError("");
        setPreviewLoading(false);
      })
      .catch((e) => {
        if (seq !== previewSeqRef.current) return;
        if (e instanceof Error && e.name === "AbortError") return;
        setPreviewLoading(false);
        setPreviewError(
          "Preview: " + (e instanceof Error ? e.message : "failed")
        );
      });

    return () => {
      controller.abort();
    };
  }, [debouncedLatex, backendOk, healthReady, previewMode]);

  const applyPreviewFromCompile = useCallback((blob: Blob, source: string) => {
    setPreviewPdf(blob);
    setHtml("");
    setPreviewForLatex(source);
    cachedPreviewRef.current = { latex: source, blob };
    setPreviewLoading(false);
    setPreviewError("");
  }, []);

  const handleCompile = useCallback(async () => {
    setStatus("compiling");
    setCompileError("");

    const cached = cachedPreviewRef.current;
    if (cached && cached.latex === latex) {
      pdfBlobRef.current = cached.blob;
      compiledLatexRef.current = latex;
      setHasPdf(true);
      setStatus("success");
      applyPreviewFromCompile(cached.blob, latex);
      return;
    }

    pdfBlobRef.current = null;
    compiledLatexRef.current = null;
    setHasPdf(false);
    try {
      const blob = await compileLatex(latex);
      pdfBlobRef.current = blob;
      compiledLatexRef.current = latex;
      setHasPdf(true);
      setStatus("success");
      applyPreviewFromCompile(blob, latex);
    } catch (e: unknown) {
      setStatus("error");
      setCompileError(
        e instanceof Error ? e.message : "Compilation failed"
      );
    }
  }, [latex, applyPreviewFromCompile]);

  const handleSavePdf = useCallback(() => {
    if (!pdfBlobRef.current) return;
    const url = URL.createObjectURL(pdfBlobRef.current);
    const a = document.createElement("a");
    a.href = url;
    a.download = "document.pdf";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, []);

  const onDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !layoutRef.current) return;
      const rect = layoutRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setEditorWidth(Math.max(20, Math.min(80, pct)));
    };

    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  const errorMsg = compileError || previewError;
  const dismissError = () => {
    setCompileError("");
    setPreviewError("");
  };

  const previewHeader = !healthReady
    ? "Preview"
    : previewMode === "pdf"
      ? "Preview (PDF)"
      : "Preview (HTML fallback)";

  const statusLabel = previewPending
    ? latex !== debouncedLatex
      ? "Paused typing to update"
      : "Compiling…"
    : previewMatchesEditor
      ? "Up to date"
      : null;

  return (
    <div className="app">
      <header className="toolbar">
        <div className="toolbar-left">
          <span className="logo">LaTeX Editor</span>
        </div>
        <div className="toolbar-center">
          <button
            className="btn btn-compile"
            onClick={handleCompile}
            disabled={status === "compiling" || !pdflatexAvailable || !backendOk}
            title={
              !backendOk
                ? "Start the backend server"
                : pdflatexAvailable
                  ? "Compile LaTeX to PDF (updates preview to match)"
                  : "pdflatex not installed"
            }
          >
            {status === "compiling" ? "Compiling..." : "Compile"}
          </button>
          <button
            className="btn btn-save"
            onClick={handleSavePdf}
            disabled={!hasPdf}
            title={hasPdf ? "Download compiled PDF" : "Compile first"}
          >
            Save PDF
          </button>
          <span className={`status-dot status-${status}`} />
          {!backendOk && (
            <span className="hint">Backend offline — run python backend/main.py</span>
          )}
          {backendOk && !pdflatexAvailable && (
            <span className="hint">
              PDF preview needs pdflatex — HTML preview is approximate only
            </span>
          )}
        </div>
        <div className="toolbar-right" />
      </header>

      {errorMsg && (
        <div className="error-bar">
          <span title={errorMsg}>{formatErrorTail(errorMsg)}</span>
          <button type="button" onClick={dismissError} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      <main className="editor-layout" ref={layoutRef}>
        <div
          className="pane pane-editor"
          style={{ width: `calc(${editorWidth}% - 3px)` }}
        >
          <div className="pane-header">Editor</div>
          <div className="editor-container">
            <Editor value={latex} onChange={setLatex} />
          </div>
        </div>
        <div className="divider" onMouseDown={onDividerMouseDown} />
        <div
          className="pane pane-preview"
          style={{ width: `calc(${100 - editorWidth}% - 3px)` }}
        >
          <div className="pane-header">
            {previewHeader}
            {statusLabel && (
              <span className="pane-header-status">{statusLabel}</span>
            )}
          </div>
          <Preview
            mode={previewMode}
            pdfBlob={previewPdf}
            html={html}
            pending={previewPending}
            showLoadingOverlay={previewLoading && !!previewPdf}
            loadingLabel={
              previewMode === "pdf" ? "Compiling preview…" : "Updating preview…"
            }
            pdfRenderKey={previewForLatex ?? ""}
            ready={healthReady}
          />
        </div>
      </main>
    </div>
  );
}
