"""A tiny, dependency-free PDF writer for the synthetic institution documents.

Lays a document out like a Moldovan medical form (see RESEARCH.md §1): institution
header, form number, document number and date, patient block, content sections,
signature / stamp placeholders, and a "MOSTRĂ — date sintetice" watermark on every
page. Output is deterministic (no timestamps, no /ID) and ASCII-only, so committed
files diff as text and regenerate byte-for-byte.

Fonts are the standard Helvetica pair, so nothing is embedded. Romanian letters
outside WinAnsi (ă, ș, ț and capitals) are mapped onto unused WinAnsi slots through
an /Encoding /Differences array.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PAGE_W, PAGE_H = 595, 842  # A4 in points
MARGIN = 50
WATERMARK = "MOSTRĂ — date sintetice"

# Unused WinAnsi code points (0x98, normally "tilde", is never needed here).
_DIFFERENCES = {
    0x81: ("abreve", "ă"),
    0x8D: ("Abreve", "Ă"),
    0x8F: ("scommaaccent", "ș"),
    0x90: ("Scommaaccent", "Ș"),
    0x9D: ("tcommaaccent", "ț"),
    0x98: ("Tcommaaccent", "Ț"),
}
_CHAR_TO_CODE = {char: code for code, (_, char) in _DIFFERENCES.items()}
# Cedilla forms are common in older Romanian text; draw them as comma-below.
_CHAR_TO_CODE.update({"ş": 0x8F, "Ş": 0x90, "ţ": 0x9D, "Ţ": 0x98})


def _encode(text: str) -> str:
    """Text -> a PDF literal string body, ASCII only (octal escapes above 0x7E)."""
    out = []
    for char in text:
        code = _CHAR_TO_CODE.get(char)
        if code is None:
            try:
                code = char.encode("cp1252")[0]
            except UnicodeEncodeError:
                code = ord("?")
        if char in "()\\":
            out.append("\\" + char)
        elif 0x20 <= code <= 0x7E:
            out.append(chr(code))
        else:
            out.append(f"\\{code:03o}")
    return "".join(out)


def _wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    """Greedy word wrap using an average Helvetica glyph width."""
    limit = max(10, int(width / (size * (0.62 if bold else 0.5))))
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if len(candidate) <= limit:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


@dataclass
class _Page:
    ops: list[str] = field(default_factory=list)

    def text(self, x, y, s, size=10, bold=False, gray=0.0):
        font = "F2" if bold else "F1"
        self.ops.append(
            f"BT {gray:.2f} g /{font} {size} Tf {x:.1f} {y:.1f} Td ({_encode(s)}) Tj ET"
        )

    def line(self, x1, y1, x2, y2, width=0.5):
        self.ops.append(f"{width} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def rect(self, x, y, w, h, width=0.5):
        self.ops.append(f"{width} w {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S")

    def watermark(self):
        # cos/sin of 35 degrees
        c, s = 0.8192, 0.5736
        self.ops.append(
            f"BT 0.85 g /F2 46 Tf {c} {s} {-s} {c} 105 190 Tm ({_encode(WATERMARK)}) Tj ET"
        )


class _Layout:
    def __init__(self):
        self.pages: list[_Page] = []
        self.y = 0.0
        self._new_page()

    @property
    def page(self) -> _Page:
        return self.pages[-1]

    def _new_page(self):
        self.pages.append(_Page())
        self.page.watermark()
        self.y = PAGE_H - MARGIN

    def need(self, height: float):
        if self.y - height < MARGIN + 30:
            self._new_page()

    def paragraph(self, text, size=10, bold=False, indent=0.0, gray=0.0, gap=3.0):
        for line in _wrap(text, size, PAGE_W - 2 * MARGIN - indent, bold):
            self.need(size + gap)
            self.y -= size + gap
            self.page.text(MARGIN + indent, self.y, line, size, bold, gray)

    def space(self, height=6.0):
        self.y -= height

    def rule(self):
        self.need(8)
        self.y -= 6
        self.page.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)

    def table(self, header: list[str], rows: list[list[str]], widths: list[float]):
        size = 9
        def draw(cells, bold):
            self.need(size + 6)
            self.y -= size + 6
            x = MARGIN
            for cell, w in zip(cells, widths):
                self.page.text(x + 2, self.y, cell, size, bold)
                x += w
        draw(header, True)
        self.page.line(MARGIN, self.y - 3, MARGIN + sum(widths), self.y - 3)
        for row in rows:
            draw(row, False)


def render(doc: dict) -> bytes:
    """Render one synthetic document.

    `doc` keys: header (lines), form (str), title, number (str), patient (lines),
    sections ([{heading, text?, table?: {header, rows, widths}}]), signatures (lines),
    hidden (optional str drawn white-on-white, for the prompt-injection fixture).
    """
    layout = _Layout()
    for i, line in enumerate(doc["header"]):
        layout.paragraph(line, size=11 if i == 0 else 9, bold=i == 0)
    form_x = PAGE_W - MARGIN - len(doc["form"]) * 9 * 0.56
    layout.page.text(form_x, PAGE_H - MARGIN - 14, doc["form"], 9, True)
    layout.rule()
    layout.space(10)
    layout.paragraph(doc["title"].upper(), size=13, bold=True)
    layout.paragraph(doc["number"], size=10)
    layout.space(6)
    for line in doc["patient"]:
        layout.paragraph(line, size=10)
    layout.rule()
    for section in doc["sections"]:
        layout.space(6)
        layout.paragraph(section["heading"], size=10, bold=True)
        if section.get("text"):
            layout.paragraph(section["text"], size=10, indent=8)
        if section.get("table"):
            table = section["table"]
            layout.table(table["header"], table["rows"], table["widths"])
    if doc.get("hidden"):
        layout.space(4)
        layout.paragraph(doc["hidden"], size=6, gray=1.0)
    layout.space(16)
    layout.need(80)
    for line in doc["signatures"]:
        layout.paragraph(line, size=10)
    layout.space(4)
    layout.need(60)
    layout.page.rect(PAGE_W - MARGIN - 110, layout.y - 56, 100, 50)
    layout.page.text(PAGE_W - MARGIN - 82, layout.y - 34, "L.Ș.", 10, True, 0.4)
    total = len(layout.pages)
    for number, page in enumerate(layout.pages, start=1):
        page.text(
            MARGIN, 28,
            f"Document sintetic generat pentru testarea MedVault — fără valoare juridică."
            f"  Pagina {number}/{total}",
            7, gray=0.35,
        )
    return _assemble(layout.pages)


def _assemble(pages: list[_Page]) -> bytes:
    differences = " ".join(f"{code} /{name}" for code, (name, _) in sorted(_DIFFERENCES.items()))
    encoding = f"<< /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [{differences}] >>"
    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "",  # pages tree, filled below
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding 5 0 R >>",
        f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding 5 0 R >>",
        encoding,
    ]
    kids = []
    for page in pages:
        content = "\n".join(page.ops)
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
        content_id = len(objects)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>"
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    out = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("ascii")
