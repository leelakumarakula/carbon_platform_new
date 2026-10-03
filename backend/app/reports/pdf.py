"""Deterministic, dependency-free, text-only PDF writer (Phase 8A decision B8).

- PDF 1.4, A4 pages, the standard Helvetica font (WinAnsiEncoding) only; no images, no embedded fonts
- no /Info dictionary, no /CreationDate, no /ID, no random values: the same lines always give the same bytes
- characters outside Windows-1252 are mapped to fixed ASCII stand-ins (e.g. → becomes ->), so output never depends on locale
"""
WRITER_VERSION = "text-pdf-1.0"
PAGE_W, PAGE_H = 595, 842          # A4 in points
MARGIN, FONT_SIZE, LEADING = 50, 9, 12
WRAP = 104                         # characters per line (Helvetica 9 pt within the margins)
LINES_PER_PAGE = (PAGE_H - 2 * MARGIN - LEADING) // LEADING
_MAP = {"→": "->", "←": "<-", "≠": "!=", "≤": "<=", "≥": ">=", "✓": "v", "×": "x", "−": "-", "\t": "    "}


def _encode(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        ch = _MAP.get(ch, ch)
        for c in ch:
            try:
                out += c.encode("cp1252")
            except UnicodeEncodeError:
                out += b"?"
    return bytes(out).replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _wrap(line: str) -> list[str]:
    if len(line) <= WRAP:
        return [line]
    indent = len(line) - len(line.lstrip(" "))
    out, rest = [], line
    while len(rest) > WRAP:
        cut = rest.rfind(" ", indent + 1, WRAP)
        cut = cut if cut > indent else WRAP
        out.append(rest[:cut].rstrip())
        rest = " " * (indent + 2) + rest[cut:].lstrip()
    out.append(rest)
    return out


def render(lines: list[str]) -> bytes:
    """Lay out the lines on A4 pages (footer "Page n of N") and return the PDF bytes."""
    wrapped = [w for line in lines for w in _wrap(line)] or [""]
    pages = [wrapped[i:i + LINES_PER_PAGE] for i in range(0, len(wrapped), LINES_PER_PAGE)]
    objects: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [" + b" ".join(f"{p} 0 R".encode() for p in page_ids) + f"] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, page in enumerate(pages):
        body = [b"BT", f"/F1 {FONT_SIZE} Tf {LEADING} TL {MARGIN} {PAGE_H - MARGIN} Td".encode()]
        for line in page:
            body.append(b"(" + _encode(line) + b") Tj T*")
        body.append(f"1 0 0 1 {MARGIN} {MARGIN - 20} Tm".encode())
        body.append(b"(" + _encode(f"Page {i + 1} of {n_pages}") + b") Tj")
        body.append(b"ET")
        stream = b"\n".join(body)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {page_ids[i] + 1} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
