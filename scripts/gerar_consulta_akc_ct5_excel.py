from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "dados" / "referencia"
RAW_DIR = ROOT / "dados" / "brutos"
OUTPUT_DIR = ROOT / "saida"


def clean(value: object) -> str:
    return str(value or "").strip().strip('"')


def load_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(8192)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(handle, dialect=dialect)
                return [
                    {key: clean(value) for key, value in row.items() if key is not None}
                    for row in reader
                ]
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Nao foi possivel ler {path}")


def rows_by_key(
    rows: list[dict[str, str]],
    key_fields: tuple[str, ...],
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        key = tuple(clean(row.get(field, "")) for field in key_fields)
        grouped.setdefault(key, []).append(row)
    return grouped


def column_name(index: int) -> str:
    result = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def sheet_xml(rows: list[list[object]]) -> str:
    xml_rows: list[str] = []
    for row_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_idx, value in enumerate(row, start=1):
            cell_ref = f"{column_name(col_idx)}{row_idx}"
            text = "" if value is None else str(value)
            escaped = escape(text)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">{escaped}</t></is></c>'
            )
        xml_rows.append(f"<row r=\"{row_idx}\">{''.join(cells)}</row>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData>"
        "</worksheet>"
    )


def write_xlsx(path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
    workbook_sheets = []
    workbook_rels = []
    for index, (name, _rows) in enumerate(sheets, start=1):
        workbook_sheets.append(
            f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        )
        workbook_rels.append(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        )

    content_types_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(workbook_sheets)}</sheets>"
        "</workbook>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(workbook_rels)}"
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{content_types_overrides}"
        "</Types>"
    )

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        for index, (_name, rows) in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(rows))


def main() -> None:
    match_path = OUTPUT_DIR / "matches_linha_a_linha.csv"
    akd_path = RAW_DIR / "DADOS-AKD010.csv"
    ct2_path = RAW_DIR / "DADOS-CT2010.csv"
    akc_path = REFERENCE_DIR / "AKC010-CHAVE.csv"
    ct5_path = REFERENCE_DIR / "CT5010-CHAVE.csv"
    output_path = OUTPUT_DIR / "consulta_akc_ct5_lado_a_lado_distinct.xlsx"

    matches = load_csv(match_path)
    akd_rows = load_csv(akd_path)
    ct2_rows = load_csv(ct2_path)
    akc_rows = load_csv(akc_path)
    ct5_rows = load_csv(ct5_path)

    akd_by_recno = {clean(row.get("R_E_C_N_O_", "")): row for row in akd_rows}
    ct2_by_recno = {clean(row.get("R_E_C_N_O_", "")): row for row in ct2_rows}
    akc_by_key = rows_by_key(akc_rows, ("AKC_PROCES", "AKC_ITEM", "AKC_SEQ"))
    ct5_by_key = rows_by_key(ct5_rows, ("CT5_LANPAD", "CT5_SEQUEN"))

    headers = [
        "AKD_PROCES",
        "AKD_ITEM",
        "AKD_SEQ",
        "CT2_LP",
        "CT2_SEQLAN",
        "AKC_XDOC",
        "CT5_XDOC",
    ]
    data_rows: list[list[object]] = [headers]
    distinct_rows: set[tuple[str, ...]] = set()

    for match in matches:
        akd_recno = clean(match.get("akd_recno", ""))
        ct2_recno = clean(match.get("ct2_recno", ""))
        akd = akd_by_recno.get(akd_recno, {})
        ct2 = ct2_by_recno.get(ct2_recno, {})

        akd_proces = clean(akd.get("AKD_PROCES", ""))
        akd_item = clean(akd.get("AKD_ITEM", ""))
        akd_seq = clean(akd.get("AKD_SEQ", ""))
        ct2_lp = clean(ct2.get("CT2_LP", ""))
        ct2_seqlan = clean(ct2.get("CT2_SEQLAN", ""))

        akc_matches = akc_by_key.get((akd_proces, akd_item, akd_seq), [{}])
        ct5_matches = ct5_by_key.get((ct2_lp, ct2_seqlan), [{}])

        row_count = max(len(akc_matches), len(ct5_matches))
        for index in range(row_count):
            akc = akc_matches[index] if index < len(akc_matches) else {}
            ct5 = ct5_matches[index] if index < len(ct5_matches) else {}
            distinct_rows.add(
                (
                    akd_proces,
                    akd_item,
                    akd_seq,
                    ct2_lp,
                    ct2_seqlan,
                    clean(akc.get("AKC_XDOC", "")),
                    clean(ct5.get("CT5_XDOC", "")),
                )
            )

    for row in sorted(distinct_rows):
        data_rows.append(list(row))

    meta_rows: list[list[object]] = [["arquivo_origem", "valor"]]
    meta_rows = [
        ["arquivo_origem", "valor"],
        ("matches", str(match_path)),
        ("akd", str(akd_path)),
        ("ct2", str(ct2_path)),
        ("akc", str(akc_path)),
        ("ct5", str(ct5_path)),
        ("linhas_exportadas", len(data_rows) - 1),
    ]
    write_xlsx(
        output_path,
        [
            ("AKC_CT5_Lado_a_Lado", data_rows),
            ("Resumo", [list(item) for item in meta_rows]),
        ],
    )
    print(output_path)


if __name__ == "__main__":
    main()
