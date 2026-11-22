"""Blocks -> .docx in Euneiz format (Times New Roman 12, line spacing 1.5). Needs python-docx; otherwise
`available()` is False and the caller keeps the Markdown export (see SKILL.md fallback)."""
import re

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
except ImportError:      # pragma: no cover
    docx = None

FONT = "Times New Roman"


def available():
    return docx is not None


def _font(style_or_run, size=12, bold=None):
    f = style_or_run.font
    f.name = FONT
    f.size = Pt(size)
    f.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        f.bold = bold
    rpr = style_or_run.element.get_or_add_rPr() if hasattr(style_or_run, "element") and hasattr(style_or_run.element, "get_or_add_rPr") else None
    if rpr is not None:
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(a), FONT)


def _field(par, instr):
    for t, txt in (("begin", None), (None, instr), ("separate", None), (None, "Actualizar campo (F9)"), ("end", None)):
        r = par.add_run()
        if t:
            c = OxmlElement("w:fldChar")
            c.set(qn("w:fldCharType"), t)
            r._r.append(c)
        elif txt == instr:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = instr
            r._r.append(it)
        else:
            r.text = txt
        _font(r)


def _inline(par, text):
    for i, part in enumerate(re.split(r"(\*\*[^*]+\*\*)", text)):
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        r = par.add_run(part[2:-2] if bold else part)
        _font(r, bold=bold or None)


def _setup(d):
    for name in ("Normal", "List Bullet", "List Number", "Title"):
        st = d.styles[name]
        _font(st, 12, bold=(True if name == "Title" else None))
        st.paragraph_format.line_spacing = 1.5
    for lvl in (1, 2, 3):
        st = d.styles["Heading %d" % lvl]
        _font(st, 12, bold=True)
        st.font.italic = (lvl == 3)
        st.font.all_caps = (lvl == 1)
        st.paragraph_format.line_spacing = 1.5
    sec = d.sections[0]
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _field(p, "PAGE")


def _body(d, md):
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if not s or s.startswith("<!--") or s == "---":
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^:?-{2,}:?$", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                n = max(len(r) for r in rows)
                t = d.add_table(rows=len(rows), cols=n)
                t.style = "Table Grid"
                for ri, r in enumerate(rows):
                    for ci in range(n):
                        cell = t.cell(ri, ci)
                        cell.text = ""
                        _inline(cell.paragraphs[0], r[ci] if ci < len(r) else "")
                        for rr in cell.paragraphs[0].runs:
                            rr.font.size = Pt(10)
                            if ri == 0:
                                rr.font.bold = True
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = min(len(m.group(1)), 3)
            d.add_heading(m.group(2), level=lvl)
            i += 1
            continue
        m = re.match(r"^[-*]\s+(?:\[[ xX]\]\s+)?(.*)$", s)
        if m:
            _inline(d.add_paragraph(style="List Bullet"), m.group(1))
            i += 1
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", s)
        if m:
            _inline(d.add_paragraph(style="List Number"), m.group(1))
            i += 1
            continue
        _inline(d.add_paragraph(), s)
        i += 1


def write_docx(blocks, path):
    d = docx.Document()
    _setup(d)
    for b in blocks:
        k = b[0]
        if k == "title":
            p = d.add_paragraph(style="Title")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(b[1])
            _font(r, 12, bold=True)
        elif k == "center":
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _inline(p, b[1])
        elif k == "banner":
            p = d.add_paragraph()
            r = p.add_run(b[1])
            _font(r, 12, bold=True)
        elif k == "pagebreak":
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif k == "toc":
            p = d.add_paragraph()
            r = p.add_run("Índice")
            _font(r, 12, bold=True)
            _field(d.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u')
        elif k == "h":
            d.add_heading(b[2], level=min(b[1], 3))
        elif k == "md":
            _body(d, b[1])
    d.save(str(path))
