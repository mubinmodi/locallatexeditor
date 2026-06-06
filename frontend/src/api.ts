const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type ApiDetail = string | { error?: string; log?: string };

async function parseErrorMessage(res: Response, fallback: string): Promise<string> {
  const text = await res.text();
  try {
    const err = JSON.parse(text) as { detail?: ApiDetail };
    const detail = err.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      return detail.log || detail.error || fallback;
    }
  } catch {
    if (text) return text.slice(0, 500);
  }
  return fallback;
}

/** Real WYSIWYG preview via pdflatex (same output as Compile). */
export async function previewPdfLatex(
  latex: string,
  signal?: AbortSignal
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/preview/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latex }),
    signal,
  });
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res, "PDF preview failed"));
  }
  return res.blob();
}

/** Fast approximate HTML preview when pdflatex is not installed. */
export async function previewHtmlLatex(
  latex: string,
  signal?: AbortSignal
): Promise<string> {
  const res = await fetch(`${API_BASE}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latex }),
    signal,
  });
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res, "Preview failed"));
  }
  const data = await res.json();
  return data.html;
}

export async function compileLatex(latex: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latex }),
  });
  if (!res.ok) {
    throw new Error(await parseErrorMessage(res, "Compilation failed"));
  }
  return res.blob();
}

export async function checkHealth(): Promise<{
  status: string;
  pdflatex_available: boolean;
}> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error("Backend unavailable");
  }
  return res.json();
}

export function formatErrorTail(message: string, maxLen = 500): string {
  if (message.length <= maxLen) return message;
  return "…" + message.slice(-maxLen);
}
