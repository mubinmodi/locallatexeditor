import html
import re
from datetime import date


def latex_to_html(latex):
    text = latex

    body_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
    if body_match:
        preamble = text[: body_match.start()]
        text = body_match.group(1)
    else:
        preamble = ""

    text = _expand_latex_specials(text)
    preamble = _expand_latex_specials(preamble)

    macros = _parse_newcommands(preamble)
    text = _expand_macros(text, macros)

    text = text.replace("\\%", "XESCPCTX")

    title = _extract_command_braced(preamble, "title") or _extract_command_braced(text, "title")
    author = _extract_command_braced(preamble, "author") or _extract_command_braced(text, "author")
    doc_date = _extract_command_braced(preamble, "date") or _extract_command_braced(text, "date")

    text = re.sub(r"\\maketitle", "", text)
    text = re.sub(r"%[^\n]*", "", text)
    text = text.replace("XESCPCTX", "%")  # restore escaped percent signs
    text = re.sub(
        r"\\(usepackage|documentclass|pagestyle|setlength|addtolength|urlstyle"
        r"|raggedbottom|raggedright|pdfgentounicode|input|fancyhf|fancyfoot"
        r"|titleformat|bibliography|bibliographystyle)\b[^\n]*",
        "",
        text,
    )
    text = re.sub(r"\\renewcommand[^\n]*", "", text)
    text = re.sub(r"\\newcommand[^\n]*", "", text)

    title_html = ""
    if title:
        title_html += f'<h1 class="doc-title">{_inline_format(title)}</h1>'
    if author:
        title_html += f'<p class="doc-author">{_inline_format(author)}</p>'
    if doc_date:
        title_html += f'<p class="doc-date">{_inline_format(doc_date)}</p>'

    text = re.sub(r"\\vspace\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\hspace\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\(scshape|Large|large|small|tiny|normalsize|footnotesize)\s*", "", text)

    text = _convert_includegraphics(text)
    text = _convert_all_tabulars(text)
    text = re.sub(r"\$\s*\|\s*\$", " | ", text)

    text, math_blocks = _extract_math_blocks(text)

    text = _convert_center(text)
    text = _convert_heading_commands(text)
    text = _convert_text_formatting(text)
    text = _convert_special_chars(text)
    text = _convert_links(text)
    text = _convert_list_environments(text)
    text = _convert_misc_environments(text)
    text = _convert_line_breaks(text)

    for _ in range(8):
        text = re.sub(r"(?<!\\)\{([^{}]*)\}", r"\1", text)

    text = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^}]*\})*", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    text = _restore_math_blocks(text, math_blocks)

    return title_html + text


def _escape_html(text):
    return html.escape(text, quote=True)


def _escape_attr(text):
    return html.escape(text, quote=True)


def _safe_href(url):
    url = url.strip()
    lower = url.lower()
    if lower.startswith(("http://", "https://", "mailto:")):
        return _escape_attr(url)
    if url.startswith(("/", "#", "./", "../")):
        return _escape_attr(url)
    return "#"


def _expand_latex_specials(text):
    today = date.today().strftime("%B %d, %Y")
    text = re.sub(r"\\today\b", today, text)
    return text


def _extract_command_braced(text, command):
    pattern = rf"\\{command}\s*"
    m = re.search(pattern, text)
    if not m:
        return None
    pos = m.end()
    while pos < len(text) and text[pos] in " \t\n":
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        return None
    end = _match_brace(text, pos)
    if end == -1:
        return None
    return text[pos + 1 : end]


def _convert_includegraphics(text):
    result = []
    i = 0
    while i < len(text):
        m = re.search(r"\\includegraphics", text[i:])
        if not m:
            result.append(text[i:])
            break
        result.append(text[i : i + m.start()])
        pos = i + m.start() + len(m.group(0))
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        if pos < len(text) and text[pos] == "[":
            bracket_end = text.find("]", pos)
            if bracket_end != -1:
                pos = bracket_end + 1
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        filename = ""
        if pos < len(text) and text[pos] == "{":
            end = _match_brace(text, pos)
            if end != -1:
                filename = text[pos + 1 : end]
                pos = end + 1
        placeholder = (
            f'<span class="graphics-placeholder">[Image: {_escape_html(filename)}]</span>'
        )
        result.append(placeholder)
        i = pos
    return "".join(result)


def _extract_math_blocks(text):
    math_blocks = []
    text = text.replace("\\$", "XESCDOLLAR")

    def save_block(content, display):
        idx = len(math_blocks)
        math_blocks.append((content, display))
        return f"%%MATH_{idx}%%"

    out = []
    i = 0
    while i < len(text):
        if text.startswith("$$", i):
            end = text.find("$$", i + 2)
            if end != -1:
                content = text[i + 2 : end]
                out.append(save_block(content, True))
                i = end + 2
                continue
        if text.startswith(r"\[", i):
            end = text.find(r"\]", i + 2)
            if end != -1:
                content = text[i + 2 : end]
                out.append(save_block(content, True))
                i = end + 2
                continue
        if text.startswith(r"\(", i):
            end = text.find(r"\)", i + 2)
            if end != -1:
                content = text[i + 2 : end]
                out.append(save_block(content, False))
                i = end + 2
                continue
        env_m = re.match(
            r"\\begin\{(equation|align|gather|multline)\*?\}",
            text[i:],
        )
        if env_m:
            env_name = env_m.group(1)
            start = i + env_m.end()
            end_tag = rf"\end{{{env_name}}}"
            end_m = re.search(rf"\\end\{{{env_name}\}}\*?", text[start:])
            if end_m:
                content = text[start : start + end_m.start()]
                out.append(save_block(content, True))
                i = start + end_m.end()
                continue
        if text[i] == "$":
            j = i + 1
            while j < len(text):
                if text[j] == "$" and text[j - 1] != "\\":
                    break
                j += 1
            else:
                out.append(text[i])
                i += 1
                continue
            content = text[i + 1 : j]
            out.append(save_block(content, False))
            i = j + 1
            continue
        out.append(text[i])
        i += 1

    return "".join(out), math_blocks


def _restore_math_blocks(text, math_blocks):
    for i, (content, display) in enumerate(math_blocks):
        content = content.replace("XESCDOLLAR", "\\$").strip()
        # Math is rendered by KaTeX client-side; keep LaTeX source, escape only HTML delimiters.
        safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if display:
            replacement = f'<div class="math-display">{safe}</div>'
        else:
            replacement = f'<span class="math-inline">{safe}</span>'
        text = text.replace(f"%%MATH_{i}%%", replacement)
    return text


def _convert_center(text):
    def repl(m):
        return f'<div class="center">{_process_inline_fragment(m.group(1))}</div>'

    return re.sub(
        r"\\begin\{center\}(.*?)\\end\{center\}",
        repl,
        text,
        flags=re.DOTALL,
    )


def _convert_heading_commands(text):
    for cmd, tag in (
        ("section", "h2"),
        ("subsection", "h3"),
        ("subsubsection", "h4"),
        ("paragraph", "h5"),
    ):
        text = _convert_braced_command(text, cmd, lambda c, t=tag: f"<{t}>{_inline_format(c)}</{t}>")
    return text


def _convert_braced_command(text, command, make_html):
    pattern = rf"\\{command}\*?"
    result = []
    i = 0
    while i < len(text):
        m = re.search(pattern, text[i:])
        if not m:
            result.append(text[i:])
            break
        result.append(text[i : i + m.start()])
        pos = i + m.start() + len(m.group(0))
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        if pos < len(text) and text[pos] == "{":
            end = _match_brace(text, pos)
            if end != -1:
                content = text[pos + 1 : end]
                result.append(make_html(content))
                i = end + 1
                continue
        result.append(m.group(0))
        i = i + m.start() + len(m.group(0))
    return "".join(result)


def _convert_text_formatting(text):
    for cmd, tag in (
        ("textbf", "strong"),
        ("textit", "em"),
        ("emph", "em"),
        ("underline", "u"),
        ("texttt", "code"),
    ):
        text = re.sub(
            rf"\\{cmd}\{{([^{{}}]*)\}}",
            lambda m, t=tag: f"<{t}>{_inline_format(m.group(1))}</{t}>",
            text,
        )
    return text


def _convert_special_chars(text):
    text = text.replace("XESCPCTX", "%")
    text = text.replace("XESCDOLLAR", "$")
    text = text.replace("\\&", "&amp;")
    text = text.replace("\\%", "%")
    text = text.replace("\\$", "$")
    text = text.replace("\\#", "#")
    text = re.sub(r"(?<![\\a-zA-Z])~(?![\\a-zA-Z])", "&nbsp;", text)
    text = re.sub(r"\\~", "~", text)
    return text


def _convert_links(text):
    def href_repl(m):
        url = _safe_href(m.group(1))
        label = _inline_format(m.group(2))
        return f'<a href="{url}" rel="noopener noreferrer">{label}</a>'

    text = re.sub(r"\\href\{([^{}]*)\}\{([^{}]*)\}", href_repl, text)

    def url_repl(m):
        url = _safe_href(m.group(1))
        label = _inline_format(m.group(1))
        return f'<a href="{url}" rel="noopener noreferrer">{label}</a>'

    text = re.sub(r"\\url\{([^{}]*)\}", url_repl, text)
    return text


def _convert_list_environments(text):
    def repl(m):
        env = m.group(1)
        content = m.group(2)
        tag = "ul" if env == "itemize" else "ol"
        parts = re.split(r"\\item\s*", content)
        items = [p.strip() for p in parts if p.strip()]
        lis = "".join(f"<li>{_inline_format(item)}</li>" for item in items)
        return f"<{tag}>{lis}</{tag}>"

    return re.sub(
        r"\\begin\{(itemize|enumerate)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}",
        repl,
        text,
        flags=re.DOTALL,
    )


def _convert_misc_environments(text):
    text = re.sub(
        r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}",
        lambda m: f"<pre><code>{_escape_html(m.group(1))}</code></pre>",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\\begin\{quote\}(.*?)\\end\{quote\}",
        lambda m: f"<blockquote>{_process_inline_fragment(m.group(1))}</blockquote>",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\\footnote\{([^{}]*)\}",
        lambda m: f'<sup class="footnote">{_inline_format(m.group(1))}</sup>',
        text,
    )
    return text


def _convert_line_breaks(text):
    text = re.sub(r"\\\\(?:\[[^\]]*\])?", "<br>", text)
    text = re.sub(r"---", "—", text)
    text = re.sub(r"--", "–", text)
    text = re.sub(r"``(.*?)''", lambda m: f'"{_escape_html(m.group(1))}"', text)
    return text


def _process_inline_fragment(text):
    text = _convert_text_formatting(text)
    text = _convert_links(text)
    text = _convert_special_chars(text)
    for _ in range(5):
        text = re.sub(r"(?<!\\)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^}]*\})*", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    return _escape_html(text)


def _convert_all_tabulars(text):
    result = []
    i = 0
    while i < len(text):
        m = re.search(r"\\begin\{tabular\*?\}", text[i:])
        if not m:
            result.append(text[i:])
            break
        result.append(text[i : i + m.start()])

        env_name = m.group(0)
        end_tag = env_name.replace("\\begin", "\\end")
        env_start = i + m.start()

        end_pos = text.find(end_tag, env_start + len(env_name))
        if end_pos == -1:
            result.append(text[env_start:])
            break

        pos = env_start + len(env_name)
        while pos < end_pos:
            if text[pos] in " \t\n":
                pos += 1
            elif text[pos] == "{":
                brace_end = _match_brace(text, pos)
                if brace_end == -1:
                    break
                pos = brace_end + 1
            elif text[pos] == "[":
                bracket_end = text.find("]", pos)
                if bracket_end == -1:
                    break
                pos = bracket_end + 1
            else:
                break

        content = text[pos:end_pos]
        rows = re.split(r"\\\\", content)
        html_table = '<table class="resume-entry">'
        for row in rows:
            row = row.strip()
            if not row or row == "\\hline":
                continue
            row = row.replace("\\hline", "").strip()
            if not row:
                continue
            cells = row.split("&")
            if len(cells) == 2:
                left = _inline_format(cells[0].strip())
                right = _inline_format(cells[1].strip())
                html_table += (
                    f'<tr><td class="entry-left">{left}</td>'
                    f'<td class="entry-right">{right}</td></tr>'
                )
            else:
                html_table += (
                    "<tr>"
                    + "".join(f"<td>{_inline_format(c.strip())}</td>" for c in cells)
                    + "</tr>"
                )
        html_table += "</table>"

        result.append(html_table)
        i = end_pos + len(end_tag)

    return "".join(result)


def _inline_format(text):
    text = text.replace("XESCDOLLAR", "$")
    text = _convert_text_formatting(text)
    text = _convert_links(text)
    text = re.sub(r"\\(scshape|Large|large|small|tiny|normalsize|footnotesize)\s*", "", text)
    text = re.sub(r"\\vspace\*?\{[^}]*\}", "", text)
    text = _convert_special_chars(text)
    for _ in range(5):
        text = re.sub(r"(?<!\\)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^}]*\})*", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    if re.search(r"</?(?:strong|em|u|code|a|sup|br)\b", text):
        return text
    return _escape_html(text)


def _match_brace(text, start):
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        elif text[i] == "\\" and i + 1 < len(text):
            i += 1
        i += 1
    return -1


def _parse_newcommands(preamble):
    macros = {}
    i = 0
    while i < len(preamble):
        m = re.match(r"\\(?:new|renew)command\s*", preamble[i:])
        if not m:
            i += 1
            continue

        pos = i + m.end()
        if pos < len(preamble) and preamble[pos] == "*":
            pos += 1
        if pos >= len(preamble):
            i += 1
            continue

        if preamble[pos] == "{":
            end_brace = _match_brace(preamble, pos)
            if end_brace == -1:
                i += 1
                continue
            cmd_name = preamble[pos + 1 : end_brace].strip()
            pos = end_brace + 1
        elif preamble[pos] == "\\":
            m2 = re.match(r"\\[a-zA-Z]+", preamble[pos:])
            if not m2:
                i += 1
                continue
            cmd_name = m2.group(0)
            pos += m2.end()
        else:
            i += 1
            continue

        while pos < len(preamble) and preamble[pos] in " \t\n":
            pos += 1
        nargs = 0
        if pos < len(preamble) and preamble[pos] == "[":
            bracket_end = preamble.index("]", pos)
            nargs = int(preamble[pos + 1 : bracket_end].strip())
            pos = bracket_end + 1
        while pos < len(preamble) and preamble[pos] in " \t\n":
            pos += 1
        if pos < len(preamble) and preamble[pos] == "[":
            bracket_end = preamble.index("]", pos)
            pos = bracket_end + 1
        while pos < len(preamble) and preamble[pos] in " \t\n":
            pos += 1

        if pos < len(preamble) and preamble[pos] == "{":
            end_brace = _match_brace(preamble, pos)
            if end_brace == -1:
                i += 1
                continue
            body = preamble[pos + 1 : end_brace]
            macros[cmd_name] = (nargs, body)
            i = end_brace + 1
        else:
            i += 1
    return macros


def _expand_macros(text, macros, max_passes=20):
    for _ in range(max_passes):
        changed = False
        for name, (nargs, body) in sorted(macros.items(), key=lambda x: -len(x[0])):
            escaped_name = re.escape(name)
            if nargs == 0:
                pattern = escaped_name + r"(?![a-zA-Z])"
                m = re.search(pattern, text)
                if m:
                    text = text[: m.start()] + body + text[m.end() :]
                    changed = True
            else:
                while True:
                    m = re.search(escaped_name + r"(?![a-zA-Z])", text)
                    if not m:
                        break
                    pos = m.end()
                    args = []
                    ok = True
                    for _ in range(nargs):
                        while pos < len(text) and text[pos] in " \t\n":
                            pos += 1
                        if pos >= len(text) or text[pos] != "{":
                            ok = False
                            break
                        end = _match_brace(text, pos)
                        if end == -1:
                            ok = False
                            break
                        args.append(text[pos + 1 : end])
                        pos = end + 1
                    if not ok:
                        break
                    replacement = body
                    for j, arg in enumerate(args):
                        replacement = replacement.replace(f"#{j + 1}", arg)
                    text = text[: m.start()] + replacement + text[pos:]
                    changed = True
        if not changed:
            break
    return text
