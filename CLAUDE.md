# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A local split-pane LaTeX editor with a React frontend (Monaco editor) and Python FastAPI backend. Supports live WYSIWYG PDF preview (via pdflatex) with an HTML/KaTeX fallback when no TeX distribution is installed.

## Development Commands

### Quick Start (runs both backend and frontend)
```bash
cd frontend
npm run start     # Runs both backend and frontend concurrently
```
Then open http://localhost:5173

### Backend (Python / FastAPI)
```bash
cd backend
pip3 install -r requirements.txt
python3 main.py                   # Starts API on http://127.0.0.1:8000
```

### Frontend (React / Vite / TypeScript)
```bash
cd frontend
npm install
npm run dev       # Dev server on http://localhost:5173
npm run build     # Type-check (tsc -b) then Vite build
npm run lint      # ESLint
```

No test framework is currently configured.

## Architecture

**Two-process dev setup:** The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000` (stripping the `/api` prefix). Both processes must be running during development.

### Backend (`backend/`)
- **`main.py`** — FastAPI app with four endpoints:
  - `GET /health` — reports whether `pdflatex` is on PATH
  - `POST /preview` — fast HTML preview via `latex_converter.py` (no TeX needed)
  - `POST /preview/pdf` — WYSIWYG preview: runs `pdflatex` and returns PDF bytes (cached by SHA-256 of source, LRU max 12)
  - `POST /compile` — same as `/preview/pdf` but sets `Content-Disposition: attachment`
- **`latex_converter.py`** — regex-based LaTeX→HTML converter. Extracts math blocks before processing (restored as `<span class="math-inline">` / `<div class="math-display">` for client-side KaTeX rendering). Handles `\newcommand` macro expansion, tabulars, lists, formatting, and links.
- PDF compilation runs `pdflatex` twice (`-no-shell-escape`, `-halt-on-error`) in an isolated temp directory. On macOS, `/Library/TeX/texbin` is auto-added to PATH.

### Frontend (`frontend/src/`)
- **`App.tsx`** — top-level state: editor content, preview mode selection (PDF vs HTML), compile/save workflow, resizable split pane, autosave to `localStorage`.
- **`api.ts`** — thin fetch wrappers for each backend endpoint. Uses `VITE_API_BASE` env var (defaults to `/api` in dev via proxy).
- **`components/Editor.tsx`** — Monaco editor wrapper with LaTeX syntax highlighting and a default template.
- **`components/Preview.tsx`** — renders either a pdf.js PDF viewer or KaTeX-rendered HTML depending on `pdflatex` availability.
- **`hooks/useDebounce.ts`** — debounce hook. PDF preview debounces at 1.2s, HTML at 0.5s.

### Preview flow
1. On startup, frontend calls `/health` to detect `pdflatex`.
2. As user types, debounced source is sent to `/preview/pdf` (or `/preview` for HTML fallback).
3. "Compile" button calls `/compile`; reuses cached preview PDF if source hasn't changed.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `/api` (dev) | API base URL; set before `npm run build` for production |
