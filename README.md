# LaTeX Editor

A local split-pane LaTeX editor with live HTML preview and PDF export.

## Requirements

- **Node.js** 20+ (for the frontend)
- **Python** 3.10+ (for the backend)
- **TeX distribution** with `pdflatex` (TeX Live, MacTeX, or MiKTeX) — optional, only needed for PDF compile

## Quick start

### Single command (recommended)

```bash
cd frontend
npm install
npm run start
```

This runs both backend and frontend. Open `http://localhost:5173`.

### Manual startup (two terminals)

**Terminal 1 - Backend:**
```bash
cd backend
pip3 install -r requirements.txt
python3 main.py
```

The API listens on `http://127.0.0.1:8000`.

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies API requests from `/api` to the backend.

## Features

- Monaco editor with LaTeX syntax highlighting
- **WYSIWYG live preview** — when `pdflatex` is installed, preview runs the same engine as **Compile** and renders the PDF in the browser (pdf.js)
- PDF compile via `pdflatex` (two passes, `-no-shell-escape`)
- Server-side PDF cache for identical source (faster re-preview)
- Autosave to `localStorage`
- Resizable editor/preview split

## Preview modes

| Mode | When | Accuracy |
|------|------|----------|
| **PDF** | `pdflatex` found on the system | Same output as **Compile** / **Save PDF** |
| **HTML fallback** | No TeX install | Fast approximate preview (regex + KaTeX); not identical to PDF |

PDF preview is debounced (~1.2s) because each update runs `pdflatex`. **Compile** reuses the cached preview PDF when the source has not changed.

### Remaining TeX limitations

Preview and compile both use a single `document.tex` in an isolated temp directory. Projects that rely on multiple files (`\input`, `\include`), BibTeX/Biber bibliographies, or custom build steps may still need extra tooling beyond this editor.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `/api` (dev) | API base URL for the frontend |

For production, set `VITE_API_BASE` to your backend URL before `npm run build`.

## Project layout

```
latex-editor/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── latex_converter.py   # Preview HTML conversion
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.tsx
        ├── api.ts
        └── components/
```
