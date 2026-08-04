"""Export helpers for admin analytics (CSV / Excel / PDF) — stdlib only."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence
from xml.sax.saxutils import escape


def rows_to_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


def rows_to_xlsx_bytes(sheet_name: str, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    """Minimal Office Open XML spreadsheet (Excel-compatible) without openpyxl."""
    sheet_rows = [list(headers)] + [list(r) for r in rows]
    sheet_xml_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_idx, row in enumerate(sheet_rows, start=1):
        sheet_xml_parts.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row):
            col = _col_letter(c_idx)
            cell_ref = f"{col}{r_idx}"
            text = "" if value is None else str(value)
            sheet_xml_parts.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
            )
        sheet_xml_parts.append("</row>")
    sheet_xml_parts.extend(["</sheetData>", "</worksheet>"])
    sheet_xml = "".join(sheet_xml_parts)

    safe_name = (sheet_name or "Sheet1")[:31]
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{escape(safe_name)}" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def rows_to_pdf_bytes(title: str, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    """Minimal single-page text PDF (no external PDF libs)."""
    lines = [title, f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]
    lines.append(" | ".join(str(h) for h in headers))
    lines.append("-" * 72)
    for row in rows:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
        if len(lines) > 80:
            lines.append("… truncated …")
            break
    return _simple_pdf("\n".join(lines))


def export_payload(
    *,
    format: str,
    title: str,
    headers: Sequence[str],
    rows: List[Sequence[Any]],
) -> Dict[str, Any]:
    fmt = (format or "csv").lower()
    generated_at = datetime.now(timezone.utc)
    if fmt == "csv":
        content = rows_to_csv(headers, rows)
        return {
            "format": "csv",
            "filename": f"{_slug(title)}.csv",
            "content_type": "text/csv; charset=utf-8",
            "encoding": "utf-8",
            "content": content,
            "row_count": len(rows),
            "generated_at": generated_at,
        }
    if fmt in ("xlsx", "excel"):
        raw = rows_to_xlsx_bytes(title[:31], headers, rows)
        import base64

        return {
            "format": "xlsx",
            "filename": f"{_slug(title)}.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "encoding": "base64",
            "content": base64.b64encode(raw).decode("ascii"),
            "row_count": len(rows),
            "generated_at": generated_at,
        }
    if fmt == "pdf":
        raw = rows_to_pdf_bytes(title, headers, rows)
        import base64

        return {
            "format": "pdf",
            "filename": f"{_slug(title)}.pdf",
            "content_type": "application/pdf",
            "encoding": "base64",
            "content": base64.b64encode(raw).decode("ascii"),
            "row_count": len(rows),
            "generated_at": generated_at,
        }
    raise ValueError(f"Unsupported export format: {format}")


def _col_letter(idx: int) -> str:
    n = idx + 1
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (value or "export").lower())
    return cleaned.strip("-")[:64] or "export"


def _simple_pdf(text: str) -> bytes:
    # Escape PDF string specials
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Use one text object with T* line breaks
    lines = safe.split("\n")
    content_lines = ["BT /F1 10 Tf 40 780 Td 12 TL"]
    for i, line in enumerate(lines):
        if i == 0:
            content_lines.append(f"({line}) Tj")
        else:
            content_lines.append("T*")
            content_lines.append(f"({line}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: List[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        b"4 0 obj<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>stream\n"
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj)
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return out.getvalue()
