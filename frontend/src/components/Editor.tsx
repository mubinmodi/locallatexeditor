import MonacoEditor from "@monaco-editor/react";

interface EditorProps {
  value: string;
  onChange: (value: string) => void;
}

const DEFAULT_TEMPLATE = `\\documentclass{article}
\\usepackage{amsmath}
\\title{My Document}
\\author{Author}
\\date{\\today}

\\begin{document}
\\maketitle

\\section{Introduction}
Hello, this is a \\textbf{LaTeX} editor with \\textit{live preview}.

\\subsection{Math Example}
The quadratic formula is:
$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$

Inline math: $E = mc^2$

\\section{Lists}
\\begin{itemize}
\\item First item
\\item Second item
\\item Third item
\\end{itemize}

\\end{document}
`;

export { DEFAULT_TEMPLATE };

export default function Editor({ value, onChange }: EditorProps) {
  return (
    <MonacoEditor
      height="100%"
      width="100%"
      defaultLanguage="latex"
      theme="vs-dark"
      value={value}
      onChange={(v) => onChange(v || "")}
      options={{
        fontSize: 14,
        minimap: { enabled: false },
        wordWrap: "on",
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 2,
        padding: { top: 12 },
      }}
    />
  );
}
