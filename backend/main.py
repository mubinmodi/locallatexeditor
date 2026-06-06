import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from latex_converter import latex_to_html

# Prefer MacTeX bin on macOS; elsewhere rely on PATH from the environment.
if platform.system() == "Darwin":
    TEXBIN = "/Library/TeX/texbin"
    if TEXBIN not in os.environ.get("PATH", ""):
        os.environ["PATH"] = TEXBIN + os.pathsep + os.environ.get("PATH", "")

MAX_LATEX_BYTES = 500_000
COMPILE_TIMEOUT_SEC = 30
PDFLATEX_PASSES = 2
_PREVIEW_CACHE_MAX = 12
_pdf_cache: OrderedDict[str, bytes] = OrderedDict()

app = FastAPI(title="LaTeX Editor Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LatexInput(BaseModel):
    latex: str = Field(..., max_length=MAX_LATEX_BYTES)


@app.get("/health")
def health():
    pdflatex = shutil.which("pdflatex")
    return {"status": "ok", "pdflatex_available": pdflatex is not None}


@app.post("/preview")
def preview_html(body: LatexInput):
    """Fast approximate HTML preview when pdflatex is unavailable."""
    try:
        html = latex_to_html(body.latex)
        return {"html": html}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview conversion error: {str(e)}")


def _cache_key(latex: str) -> str:
    return hashlib.sha256(latex.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> bytes | None:
    if key not in _pdf_cache:
        return None
    _pdf_cache.move_to_end(key)
    return _pdf_cache[key]


def _cache_put(key: str, pdf_bytes: bytes) -> None:
    _pdf_cache[key] = pdf_bytes
    _pdf_cache.move_to_end(key)
    while len(_pdf_cache) > _PREVIEW_CACHE_MAX:
        _pdf_cache.popitem(last=False)


def _run_pdflatex(pdflatex: str, tmpdir: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            pdflatex,
            "-no-shell-escape",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "document.tex",
        ],
        cwd=tmpdir,
        capture_output=True,
        text=True,
        timeout=COMPILE_TIMEOUT_SEC,
    )


def _compile_to_pdf(latex: str, passes: int = PDFLATEX_PASSES) -> bytes:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        raise HTTPException(
            status_code=503,
            detail="pdflatex is not installed. Install TeX Live, MacTeX, or MiKTeX.",
        )

    tmpdir = tempfile.mkdtemp()
    try:
        tex_path = Path(tmpdir) / "document.tex"
        tex_path.write_text(latex, encoding="utf-8")

        last_result = None
        for _ in range(passes):
            last_result = _run_pdflatex(pdflatex, tmpdir)

        pdf_path = Path(tmpdir) / "document.pdf"
        if last_result and last_result.returncode != 0 and not pdf_path.exists():
            log_path = Path(tmpdir) / "document.log"
            log_content = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else (last_result.stdout or "") + (last_result.stderr or "")
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "Compilation failed", "log": log_content[-3000:]},
            )

        if not pdf_path.exists():
            log_path = Path(tmpdir) / "document.log"
            log_content = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.exists()
                else ""
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "Compilation failed", "log": log_content[-3000:]},
            )

        return pdf_path.read_bytes()
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Compilation timed out (30s limit)")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _compile_to_pdf_cached(latex: str) -> bytes:
    key = _cache_key(latex)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    pdf_bytes = _compile_to_pdf(latex)
    _cache_put(key, pdf_bytes)
    return pdf_bytes


@app.post("/preview/pdf")
def preview_pdf(body: LatexInput):
    """WYSIWYG preview: same pdflatex pipeline as /compile."""
    pdf_bytes = _compile_to_pdf_cached(body.latex)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=preview.pdf"},
    )


@app.post("/compile")
def compile_latex(body: LatexInput):
    pdf_bytes = _compile_to_pdf_cached(body.latex)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=document.pdf"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
