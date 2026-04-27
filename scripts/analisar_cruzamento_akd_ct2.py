from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Iterable
from zipfile import ZipFile
import csv
import json
import re
import xml.etree.ElementTree as ET


NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "saida"
RAW_DIR = ROOT / "dados" / "brutos"


class ProgressBar:
    def __init__(self, total: int, label: str, width: int = 30) -> None:
        self.total = max(total, 1)
        self.label = label
        self.width = width
        self.last_percent = -1
        self.start = perf_counter()

    def update(self, current: int) -> None:
        percent = int((current / self.total) * 100)
        if percent == self.last_percent and current < self.total:
            return
        self.last_percent = percent
        filled = int(self.width * current / self.total)
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = perf_counter() - self.start
        print(
            f"\r{self.label}: [{bar}] {percent:3d}% "
            f"({current}/{self.total}) {elapsed:6.1f}s",
            end="",
            flush=True,
        )
        if current >= self.total:
            print()


def log_step(message: str) -> None:
    print(f"[etapa] {message}", flush=True)


def col_to_index(cell_ref: str) -> int:
    col = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in col:
        value = value * 26 + (ord(ch.upper()) - 64)
    return value - 1


def read_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("main:si", NS):
        text = "".join(node.text or "" for node in item.iterfind(".//main:t", NS))
        values.append(text)
    return values


def first_sheet_path(zf: ZipFile) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    first_sheet = workbook.find("main:sheets/main:sheet", NS)
    if first_sheet is None:
        raise ValueError("Nenhuma planilha encontrada no arquivo.")
    relation_id = first_sheet.attrib[
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    ]
    return "xl/" + rel_map[relation_id]


def read_excel_rows(path: Path) -> list[dict[str, str]]:
    log_step(f"Lendo arquivo {path.name}")
    with ZipFile(path) as zf:
        shared = read_shared_strings(zf)
        sheet_root = ET.fromstring(zf.read(first_sheet_path(zf)))

    rows: list[list[str]] = []
    max_col = 0
    for row in sheet_root.findall("main:sheetData/main:row", NS):
        values_by_col: dict[int, str] = {}
        for cell in row.findall("main:c", NS):
            index = col_to_index(cell.attrib.get("r", "A1"))
            max_col = max(max_col, index)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("main:v", NS)
            value = ""
            if cell_type == "s" and value_node is not None and value_node.text is not None:
                value = shared[int(value_node.text)]
            elif cell_type == "inlineStr":
                inline = cell.find("main:is", NS)
                if inline is not None:
                    value = "".join(
                        text.text or "" for text in inline.iterfind(".//main:t", NS)
                    )
            elif value_node is not None and value_node.text is not None:
                value = value_node.text
            values_by_col[index] = value
        rows.append([values_by_col.get(i, "") for i in range(max_col + 1)])

    if not rows:
        return []

    header = rows[0]
    data = rows[1:]
    normalized_rows: list[dict[str, str]] = []
    for raw_row in data:
        padded = raw_row + [""] * max(0, len(header) - len(raw_row))
        normalized_rows.append(dict(zip(header, padded)))
    return normalized_rows


def clean(value: object) -> str:
    return str(value).strip()


def normalize_recno(value: object) -> str:
    text = clean(value)
    if text.endswith(".0"):
        return text[:-2]
    return text


def normalize_text(value: object) -> str:
    text = clean(value).upper()
    text = re.sub(r"\s+", " ", text)
    return text


def compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value)).strip()


def normalize_decimal(value: object) -> Decimal | None:
    text = clean(value)
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        try:
            amount = Decimal(str(float(text)))
        except ValueError:
            return None
    return amount.quantize(Decimal("0.01"))


def month_from_akd_date(value: object) -> str:
    text = clean(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[4:6]}/{text[:4]}"
    return ""


def year_from_akd_date(value: object) -> str:
    text = clean(value)
    if len(text) == 8 and text.isdigit():
        return text[:4]
    return ""


def quarter_from_akd_date(value: object) -> str:
    text = clean(value)
    if len(text) == 8 and text.isdigit():
        month = int(text[4:6])
        return f"T{((month - 1) // 3) + 1}"
    return ""


def year_from_date(value: object) -> str:
    text = clean(value)
    if len(text) == 8 and text.isdigit():
        return text[:4]
    return ""


def quarter_from_date(value: object) -> str:
    text = clean(value)
    if len(text) == 8 and text.isdigit():
        month = int(text[4:6])
        return f"T{((month - 1) // 3) + 1}"
    return ""


def account_match_status(akd_account: object, ct2_debito: object, ct2_credito: object) -> str:
    akd = clean(akd_account)
    deb = clean(ct2_debito)
    cred = clean(ct2_credito)
    if not akd:
        return "sem_referencia"
    if akd == deb or akd == cred:
        return "ok"
    return "divergente"


def date_match_status(akd_date: object, ct2_hist: object) -> str:
    akd = clean(akd_date)
    ct2 = clean(ct2_hist)
    if len(akd) == 8 and akd.isdigit() and len(ct2) == 8 and ct2.isdigit():
        return "ok" if akd == ct2 else "divergente"
    akd_month = month_from_akd_date(akd_date)
    ct2_month = month_from_ct2_hist(ct2_hist)
    if not akd_month or not ct2_month:
        return "sem_referencia"
    if akd_month == ct2_month:
        return "ok"
    return "divergente"


def value_match_status(akd_value: object, ct2_value: object) -> str:
    akd = normalize_decimal(akd_value)
    ct2 = normalize_decimal(ct2_value)
    if akd is None or ct2 is None:
        return "sem_referencia"
    if akd == ct2:
        return "ok"
    return "divergente"


def month_from_ct2_hist(value: object) -> str:
    match = re.search(r"(\d{2}/\d{4})", clean(value))
    return match.group(1) if match else ""


def month_from_ct2_row(row: dict[str, str]) -> str:
    ct2_date = clean(row.get("CT2_DATA", ""))
    if len(ct2_date) == 8 and ct2_date.isdigit():
        return f"{ct2_date[4:6]}/{ct2_date[:4]}"
    return month_from_ct2_hist(row.get("CT2_HIST", ""))


def text_tokens(value: object) -> set[str]:
    stop_words = {
        "DO",
        "DA",
        "DE",
        "E",
        "EM",
        "NO",
        "NA",
        "S",
        "P",
        "VALOR",
        "REFERENTE",
        "PAGAMENTO",
        "PGTO",
        "RECBTO",
        "INC",
        "TITULO",
        "MANUAL",
        "CONTAS",
        "RECEBER",
        "APEXBRASIL",
    }
    return {
        token
        for token in re.findall(r"[A-Z0-9]{3,}", normalize_text(value))
        if token not in stop_words
    }


def row_text_akd(row: dict[str, str]) -> str:
    return compact_text(row.get("AKD_XHISTO") or row.get("AKD_HIST") or row.get("AKD_XDOC")).upper()


def row_text_ct2(row: dict[str, str]) -> str:
    return compact_text(row.get("CT2_HIST") or row.get("CT2_XDOC") or row.get("CT2_XDOCUM")).upper()


def row_account_ct2(row: dict[str, str]) -> str:
    return clean(row.get("CT2_DEBITO") or row.get("CT2_CREDIT"))


def derived_ct2_date(row: dict[str, str]) -> str:
    return clean(row.get("CT2_DATA", ""))


@dataclass
class GroupSummary:
    key: str
    akd_rows: int
    ct2_rows: int
    akd_total: Decimal
    ct2_total: Decimal
    status: str


@dataclass
class CandidateMatch:
    akd_recno: str
    ct2_recno: str
    score: int
    confidence: str
    reasons: str
    text_similarity: float
    token_overlap: int


def rows_by_key(rows: Iterable[dict[str, str]], column: str) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = clean(row.get(column, ""))
        if key:
            groups[key].append(row)
    return groups


def summarize_overlap(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
    akd_key: str,
    ct2_key: str,
    output_name: str,
) -> list[GroupSummary]:
    log_step(f"Calculando sobreposicao {akd_key} x {ct2_key}")
    akd_groups = rows_by_key(akd_rows, akd_key)
    ct2_groups = rows_by_key(ct2_rows, ct2_key)
    overlap_keys = sorted(set(akd_groups) & set(ct2_groups))

    summaries: list[GroupSummary] = []
    for key in overlap_keys:
        akd_group = akd_groups[key]
        ct2_group = ct2_groups[key]
        akd_total = sum(normalize_decimal(row["AKD_VALOR1"]) or Decimal("0.00") for row in akd_group)
        ct2_total = sum(normalize_decimal(row["CT2_VALOR"]) or Decimal("0.00") for row in ct2_group)

        if len(akd_group) == 1 and len(ct2_group) == 1 and akd_total == ct2_total:
            status = "forte_1x1"
        elif akd_total == ct2_total:
            status = "forte_grupo"
        else:
            status = "ambiguo"

        summaries.append(
            GroupSummary(
                key=key,
                akd_rows=len(akd_group),
                ct2_rows=len(ct2_group),
                akd_total=akd_total,
                ct2_total=ct2_total,
                status=status,
            )
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / output_name
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["key", "akd_rows", "ct2_rows", "akd_total", "ct2_total", "status"])
        for item in summaries:
            writer.writerow(
                [
                    item.key,
                    item.akd_rows,
                    item.ct2_rows,
                    f"{item.akd_total:.2f}",
                    f"{item.ct2_total:.2f}",
                    item.status,
                ]
            )
    return summaries


def candidate_signatures(
    akd_rows: list[dict[str, str]], ct2_rows: list[dict[str, str]]
) -> dict[str, int]:
    akd_signature = Counter(
        (
            month_from_akd_date(row.get("AKD_DATA", "")),
            normalize_decimal(row.get("AKD_VALOR1", "")),
        )
        for row in akd_rows
        if normalize_decimal(row.get("AKD_VALOR1", "")) is not None
    )
    ct2_signature = Counter(
        (
            month_from_ct2_row(row),
            normalize_decimal(row.get("CT2_VALOR", "")),
        )
        for row in ct2_rows
        if normalize_decimal(row.get("CT2_VALOR", "")) is not None
    )
    overlap = sum(1 for key in akd_signature if key in ct2_signature)
    return {
        "akd_distinct_month_value": len(akd_signature),
        "ct2_distinct_month_value": len(ct2_signature),
        "overlap_month_value": overlap,
    }


def score_candidate(akd_row: dict[str, str], ct2_row: dict[str, str]) -> CandidateMatch | None:
    score = 0
    reasons: list[str] = []

    akd_value = normalize_decimal(akd_row.get("AKD_VALOR1", ""))
    ct2_value = normalize_decimal(ct2_row.get("CT2_VALOR", ""))
    if akd_value is None or ct2_value is None or akd_value != ct2_value:
        return None

    score += 35
    reasons.append("valor")

    akd_xdoc = clean(akd_row.get("AKD_XDOC", ""))
    ct2_xdoc = clean(ct2_row.get("CT2_XDOC", ""))
    if akd_xdoc and ct2_xdoc and akd_xdoc == ct2_xdoc:
        score += 70
        reasons.append("xdoc")

    akd_xnumap = clean(akd_row.get("AKD_XNUMAP", ""))
    ct2_xdocum = clean(ct2_row.get("CT2_XDOCUM", ""))
    if akd_xnumap and ct2_xdocum and akd_xnumap == ct2_xdocum:
        score += 60
        reasons.append("xnumap_xdocum")

    akd_month = month_from_akd_date(akd_row.get("AKD_DATA", ""))
    ct2_month = month_from_ct2_row(ct2_row)
    if akd_month and ct2_month and akd_month == ct2_month:
        score += 15
        reasons.append("competencia")

    akd_ent05 = clean(akd_row.get("AKD_ENT05", ""))
    ct2_account = row_account_ct2(ct2_row)
    if akd_ent05 and ct2_account and akd_ent05 == ct2_account:
        score += 18
        reasons.append("ent05_conta")

    text_akd = row_text_akd(akd_row)
    text_ct2 = row_text_ct2(ct2_row)
    text_similarity = SequenceMatcher(None, text_akd, text_ct2).ratio()
    token_overlap = len(text_tokens(text_akd) & text_tokens(text_ct2))

    if token_overlap >= 8:
        score += 25
        reasons.append("tokens_8+")
    elif token_overlap >= 4:
        score += 15
        reasons.append("tokens_4+")
    elif token_overlap >= 2:
        score += 8
        reasons.append("tokens_2+")

    if text_similarity >= 0.85:
        score += 20
        reasons.append("texto_085")
    elif text_similarity >= 0.70:
        score += 12
        reasons.append("texto_070")
    elif text_similarity >= 0.55:
        score += 6
        reasons.append("texto_055")

    if score >= 125:
        confidence = "muito_forte"
    elif score >= 95:
        confidence = "forte"
    elif score >= 70:
        confidence = "provavel"
    else:
        return None

    return CandidateMatch(
        akd_recno=normalize_recno(akd_row["R_E_C_N_O_"]),
        ct2_recno=normalize_recno(ct2_row["R_E_C_N_O_"]),
        score=score,
        confidence=confidence,
        reasons="|".join(reasons),
        text_similarity=round(text_similarity, 4),
        token_overlap=token_overlap,
    )


def build_candidate_pairs(
    akd_rows: list[dict[str, str]], ct2_rows: list[dict[str, str]]
) -> list[CandidateMatch]:
    log_step("Montando indices auxiliares para candidatos")
    ct2_by_xdoc = rows_by_key(ct2_rows, "CT2_XDOC")
    ct2_by_xdocum = rows_by_key(ct2_rows, "CT2_XDOCUM")
    ct2_by_month_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)

    for row in ct2_rows:
        month = month_from_ct2_row(row)
        value = normalize_decimal(row.get("CT2_VALOR", ""))
        if month and value is not None:
            ct2_by_month_value[(month, value)].append(row)

    candidates: list[CandidateMatch] = []
    seen_pairs: set[tuple[str, str]] = set()
    progress = ProgressBar(len(akd_rows), "Gerando candidatos")

    for index, akd_row in enumerate(akd_rows, start=1):
        candidate_rows: dict[str, dict[str, str]] = {}

        akd_xdoc = clean(akd_row.get("AKD_XDOC", ""))
        if akd_xdoc:
            for row in ct2_by_xdoc.get(akd_xdoc, []):
                candidate_rows[clean(row["R_E_C_N_O_"])] = row

        akd_xnumap = clean(akd_row.get("AKD_XNUMAP", ""))
        if akd_xnumap:
            for row in ct2_by_xdocum.get(akd_xnumap, []):
                candidate_rows[clean(row["R_E_C_N_O_"])] = row

        akd_month = month_from_akd_date(akd_row.get("AKD_DATA", ""))
        akd_value = normalize_decimal(akd_row.get("AKD_VALOR1", ""))
        if akd_month and akd_value is not None:
            for row in ct2_by_month_value.get((akd_month, akd_value), []):
                candidate_rows[clean(row["R_E_C_N_O_"])] = row

        for ct2_row in candidate_rows.values():
            pair = (clean(akd_row["R_E_C_N_O_"]), clean(ct2_row["R_E_C_N_O_"]))
            if pair in seen_pairs:
                continue
            candidate = score_candidate(akd_row, ct2_row)
            if candidate is None:
                continue
            seen_pairs.add(pair)
            candidates.append(candidate)
        progress.update(index)

    return candidates


def select_best_matches(candidates: list[CandidateMatch]) -> list[CandidateMatch]:
    log_step("Selecionando melhor candidato por linha")
    ordered = sorted(
        candidates,
        key=lambda item: (item.score, item.token_overlap, item.text_similarity),
        reverse=True,
    )

    selected: list[CandidateMatch] = []
    used_akd: set[str] = set()
    used_ct2: set[str] = set()

    for candidate in ordered:
        if candidate.akd_recno in used_akd or candidate.ct2_recno in used_ct2:
            continue
        used_akd.add(candidate.akd_recno)
        used_ct2.add(candidate.ct2_recno)
        selected.append(candidate)

    return selected


def export_row_matches(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
) -> dict[str, object]:
    log_step("Gerando reconciliacao linha a linha")
    akd_map = {normalize_recno(row["R_E_C_N_O_"]): row for row in akd_rows}
    ct2_map = {normalize_recno(row["R_E_C_N_O_"]): row for row in ct2_rows}
    candidates = build_candidate_pairs(akd_rows, ct2_rows)
    selected = select_best_matches(candidates)
    selected_akd = {item.akd_recno for item in selected}
    selected_ct2 = {item.ct2_recno for item in selected}

    OUTPUT_DIR.mkdir(exist_ok=True)
    match_path = OUTPUT_DIR / "matches_linha_a_linha.csv"
    log_step(f"Exportando {match_path.name}")
    with match_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            [
                "akd_recno",
                "ct2_recno",
                "confidence",
                "score",
                "akd_lote",
                "ct2_lote",
                "reasons",
                "text_similarity",
                "token_overlap",
                "akd_xdoc",
                "ct2_xdoc",
                "akd_xnumap",
                "ct2_xdocum",
                "akd_data",
                "ct2_data",
                "ct2_hist",
                "akd_valor",
                "ct2_valor",
                "akd_debito",
                "akd_credito",
                "ct2_debito",
                "ct2_credito",
                "akd_conta_referencia",
                "ct2_centro_debito",
                "ct2_centro_credito",
                "akd_historico_base",
                "ct2_historico",
            ]
        )
        for item in selected:
            akd_row = akd_map[item.akd_recno]
            ct2_row = ct2_map[item.ct2_recno]
            writer.writerow(
                [
                    item.akd_recno,
                    item.ct2_recno,
                    item.confidence,
                    item.score,
                    clean(akd_row.get("AKD_LOTE", "")),
                    clean(ct2_row.get("CT2_LOTE", "")),
                    item.reasons,
                    item.text_similarity,
                    item.token_overlap,
                    clean(akd_row.get("AKD_XDOC", "")),
                    clean(ct2_row.get("CT2_XDOC", "")),
                    clean(akd_row.get("AKD_XNUMAP", "")),
                    clean(ct2_row.get("CT2_XDOCUM", "")),
                    clean(akd_row.get("AKD_DATA", "")),
                    derived_ct2_date(ct2_row),
                    clean(ct2_row.get("CT2_HIST", "")),
                    f"{normalize_decimal(akd_row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                    f"{normalize_decimal(ct2_row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                    "",
                    "",
                    clean(ct2_row.get("CT2_DEBITO", "")),
                    clean(ct2_row.get("CT2_CREDIT", "")),
                    clean(akd_row.get("AKD_ENT05", "")),
                    clean(ct2_row.get("CT2_CCD", "")),
                    clean(ct2_row.get("CT2_CCC", "")),
                    row_text_akd(akd_row),
                    row_text_ct2(ct2_row),
                ]
            )

    comparison_path = OUTPUT_DIR / "comparativo_conciliacao.csv"
    log_step(f"Exportando {comparison_path.name}")
    with comparison_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
                [
                    "confidence",
                    "score",
                    "akd_lote",
                    "ct2_lote",
                    "reasons",
                    "akd_data",
                    "ct2_data",
                "akd_valor",
                "ct2_valor",
                "akd_xdoc",
                "ct2_xdoc",
                "akd_xnumap",
                "ct2_xdocum",
                "akd_conta_referencia",
                "ct2_debito",
                "ct2_credito",
                "ct2_centro_debito",
                "ct2_centro_credito",
                "akd_historico",
                "ct2_historico",
                "recno_akd",
                "recno_ct2",
            ]
        )
        for item in selected:
            akd_row = akd_map[item.akd_recno]
            ct2_row = ct2_map[item.ct2_recno]
            writer.writerow(
                [
                    item.confidence,
                    item.score,
                    clean(akd_row.get("AKD_LOTE", "")),
                    clean(ct2_row.get("CT2_LOTE", "")),
                    item.reasons,
                    clean(akd_row.get("AKD_DATA", "")),
                    derived_ct2_date(ct2_row),
                    f"{normalize_decimal(akd_row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                    f"{normalize_decimal(ct2_row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                    clean(akd_row.get("AKD_XDOC", "")),
                    clean(ct2_row.get("CT2_XDOC", "")),
                    clean(akd_row.get("AKD_XNUMAP", "")),
                    clean(ct2_row.get("CT2_XDOCUM", "")),
                    clean(akd_row.get("AKD_ENT05", "")),
                    clean(ct2_row.get("CT2_DEBITO", "")),
                    clean(ct2_row.get("CT2_CREDIT", "")),
                    clean(ct2_row.get("CT2_CCD", "")),
                    clean(ct2_row.get("CT2_CCC", "")),
                    row_text_akd(akd_row),
                    row_text_ct2(ct2_row),
                    item.akd_recno,
                    item.ct2_recno,
                ]
                )

    pending_ct2_path = OUTPUT_DIR / "ct2_sem_match.csv"
    log_step(f"Exportando {pending_ct2_path.name}")
    with pending_ct2_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            [
                "ct2_recno",
                "ct2_lote",
                "ct2_data",
                "ct2_valor",
                "ct2_xdoc",
                "ct2_xdocum",
                "ct2_debito",
                "ct2_credito",
                "ct2_centro_debito",
                "ct2_centro_credito",
                "ct2_historico",
            ]
        )
        for row in ct2_rows:
            recno = normalize_recno(row["R_E_C_N_O_"])
            if recno in selected_ct2:
                continue
            writer.writerow(
                [
                    recno,
                    clean(row.get("CT2_LOTE", "")),
                    derived_ct2_date(row),
                    f"{normalize_decimal(row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                    clean(row.get("CT2_XDOC", "")),
                    clean(row.get("CT2_XDOCUM", "")),
                    clean(row.get("CT2_DEBITO", "")),
                    clean(row.get("CT2_CREDIT", "")),
                    clean(row.get("CT2_CCD", "")),
                    clean(row.get("CT2_CCC", "")),
                    row_text_ct2(row),
                ]
            )

    pending_akd_path = OUTPUT_DIR / "akd_sem_match.csv"
    log_step(f"Exportando {pending_akd_path.name}")
    with pending_akd_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            [
                "akd_recno",
                "akd_lote",
                "akd_data",
                "akd_valor",
                "akd_xdoc",
                "akd_xnumap",
                "akd_conta_referencia",
                "akd_historico",
            ]
        )
        for row in akd_rows:
            recno = normalize_recno(row["R_E_C_N_O_"])
            if recno in selected_akd:
                continue
            writer.writerow(
                [
                    recno,
                    clean(row.get("AKD_LOTE", "")),
                    clean(row.get("AKD_DATA", "")),
                    f"{normalize_decimal(row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                    clean(row.get("AKD_XDOC", "")),
                    clean(row.get("AKD_XNUMAP", "")),
                    clean(row.get("AKD_ENT05", "")),
                    row_text_akd(row),
                ]
            )

    report_path = OUTPUT_DIR / "relatorio_conciliacao.html"
    log_step(f"Exportando {report_path.name}")

    report_rows: list[dict[str, object]] = []
    for item in selected:
        akd_row = akd_map[item.akd_recno]
        ct2_row = ct2_map[item.ct2_recno]
        report_rows.append(
            {
                "confidence": item.confidence,
                "score": item.score,
                "akd_lote": clean(akd_row.get("AKD_LOTE", "")),
                "ct2_lote": clean(ct2_row.get("CT2_LOTE", "")),
                "reasons": item.reasons,
                "akd_data": clean(akd_row.get("AKD_DATA", "")),
                "akd_year": year_from_akd_date(akd_row.get("AKD_DATA", "")),
                "akd_quarter": quarter_from_akd_date(akd_row.get("AKD_DATA", "")),
                "ct2_data": derived_ct2_date(ct2_row),
                "akd_valor": f"{normalize_decimal(akd_row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                "ct2_valor": f"{normalize_decimal(ct2_row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                "akd_xdoc": clean(akd_row.get("AKD_XDOC", "")),
                "ct2_xdoc": clean(ct2_row.get("CT2_XDOC", "")),
                "akd_xnumap": clean(akd_row.get("AKD_XNUMAP", "")),
                "ct2_xdocum": clean(ct2_row.get("CT2_XDOCUM", "")),
                "akd_conta_referencia": clean(akd_row.get("AKD_ENT05", "")),
                "ct2_debito": clean(ct2_row.get("CT2_DEBITO", "")),
                "ct2_credito": clean(ct2_row.get("CT2_CREDIT", "")),
                "ct2_centro_debito": clean(ct2_row.get("CT2_CCD", "")),
                "ct2_centro_credito": clean(ct2_row.get("CT2_CCC", "")),
                "akd_historico": row_text_akd(akd_row),
                "ct2_historico": row_text_ct2(ct2_row),
                "date_status": date_match_status(akd_row.get("AKD_DATA", ""), ct2_row.get("CT2_DATA", "")),
                "value_status": value_match_status(akd_row.get("AKD_VALOR1", ""), ct2_row.get("CT2_VALOR", "")),
                "account_status": account_match_status(
                    akd_row.get("AKD_ENT05", ""),
                    ct2_row.get("CT2_DEBITO", ""),
                    ct2_row.get("CT2_CREDIT", ""),
                ),
                "recno_akd": item.akd_recno,
                "recno_ct2": item.ct2_recno,
                "text_similarity": item.text_similarity,
                "token_overlap": item.token_overlap,
            }
        )

    report_data = {
        "summary": {
            "matches_selecionados": len(selected),
            "candidatos_gerados": len(candidates),
            "muito_forte": sum(1 for item in selected if item.confidence == "muito_forte"),
            "forte": sum(1 for item in selected if item.confidence == "forte"),
            "provavel": sum(1 for item in selected if item.confidence == "provavel"),
        },
        "rows": report_rows,
        "akd_unmatched_rows": [
            {
                "akd_lote": clean(row.get("AKD_LOTE", "")),
                "akd_data": clean(row.get("AKD_DATA", "")),
                "akd_year": year_from_akd_date(row.get("AKD_DATA", "")),
                "akd_quarter": quarter_from_akd_date(row.get("AKD_DATA", "")),
                "akd_valor": f"{normalize_decimal(row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                "akd_xdoc": clean(row.get("AKD_XDOC", "")),
                "akd_xnumap": clean(row.get("AKD_XNUMAP", "")),
                "akd_conta_referencia": clean(row.get("AKD_ENT05", "")),
                "akd_historico": row_text_akd(row),
                "recno_akd": normalize_recno(row.get("R_E_C_N_O_", "")),
            }
            for row in akd_rows
            if normalize_recno(row.get("R_E_C_N_O_", "")) not in selected_akd
        ],
        "ct2_unmatched_rows": [
            {
                "ct2_lote": clean(row.get("CT2_LOTE", "")),
                "ct2_data": derived_ct2_date(row),
                "ct2_year": year_from_date(row.get("CT2_DATA", "")),
                "ct2_quarter": quarter_from_date(row.get("CT2_DATA", "")),
                "ct2_valor": f"{normalize_decimal(row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                "ct2_xdoc": clean(row.get("CT2_XDOC", "")),
                "ct2_xdocum": clean(row.get("CT2_XDOCUM", "")),
                "ct2_debito": clean(row.get("CT2_DEBITO", "")),
                "ct2_credito": clean(row.get("CT2_CREDIT", "")),
                "ct2_centro_debito": clean(row.get("CT2_CCD", "")),
                "ct2_centro_credito": clean(row.get("CT2_CCC", "")),
                "ct2_historico": row_text_ct2(row),
                "recno_ct2": normalize_recno(row.get("R_E_C_N_O_", "")),
            }
            for row in ct2_rows
            if normalize_recno(row.get("R_E_C_N_O_", "")) not in selected_ct2
        ],
        "years": sorted({row["akd_year"] for row in report_rows if row["akd_year"]}),
        "quarters": sorted({row["akd_quarter"] for row in report_rows if row["akd_quarter"]}),
    }

    header_help = {
        "Confianca": "Nivel de seguranca do match encontrado entre AKD e CT2.",
        "Score": "Pontuacao calculada pelo reconciliador para ranquear a qualidade do cruzamento.",
        "Lote AKD": "Numero do lote do lancamento na base AKD.",
        "Lote CT2": "Numero do lote do lancamento na base CT2.",
        "Data AKD": "Data do lancamento vinda da base AKD.",
        "Data CT2": "Data do lancamento vinda da base CT2.",
        "Valor AKD": "Valor do lancamento na base AKD.",
        "Valor CT2": "Valor do lancamento na base CT2.",
        "DOC AKD": "Documento chave da AKD usado como uma das ancoras principais do cruzamento.",
        "DOC CT2": "Documento chave da CT2 usado como uma das ancoras principais do cruzamento.",
        "AP AKD": "Numero AP da AKD, usado como segunda ancora importante de conciliacao.",
        "Doc APEX CT2": "Documento APEX da CT2 comparado com o numero AP da AKD.",
        "Conta Ref AKD": "Referencia de conta disponivel na AKD. No extrato atual corresponde ao campo AKD_ENT05.",
        "Debito CT2": "Conta contabil de debito do lancamento na CT2.",
        "Credito CT2": "Conta contabil de credito do lancamento na CT2.",
        "CC Debito CT2": "Centro de custo do lado debito na CT2.",
        "CC Credito CT2": "Centro de custo do lado credito na CT2.",
        "Historico AKD": "Texto do historico da AKD usado para comparacao semantica.",
        "Historico CT2": "Texto do historico da CT2 usado para comparacao semantica.",
        "RECNO AKD": "Identificador unico do registro na base AKD.",
        "RECNO CT2": "Identificador unico do registro na base CT2.",
    }

    filter_help = {
        "Busca livre": "Pesquisa texto em qualquer coluna visivel do relatorio, como documento, conta, valor, historico e RECNO.",
        "Confianca": "Filtra os registros pelo nivel de seguranca calculado pelo reconciliador.",
        "Ano": "Filtra os registros pelo ano da data da AKD.",
        "Trimestre": "Filtra os registros pelo trimestre calculado a partir da data da AKD.",
        "Score minimo": "Mostra apenas registros com pontuacao igual ou acima do valor informado.",
        "Motivo": "Filtra por evidencias internas do match, como documento, AP, conta ou similaridade textual.",
        "Valor igual": "Quando selecionado, mantem somente registros em que o valor da AKD e o valor da CT2 sao iguais.",
        "Data divergente": "Compara a data do lancamento da AKD com a data real do lancamento da CT2.",
        "Valor divergente": "Mostra se o valor entre AKD e CT2 bate, diverge ou nao possui referencia suficiente.",
        "Conta divergente": "Mostra se a conta de referencia da AKD bate com debito/credito da CT2, diverge ou esta sem referencia.",
        "Limpar filtros": "Remove todos os filtros aplicados e volta a exibir todos os registros do relatorio.",
    }

    summary_help = {
        "Matches Selecionados": "Quantidade final de pares AKD x CT2 escolhidos pelo reconciliador apos aplicar score e desempate.",
        "Candidatos Gerados": "Quantidade total de combinacoes candidatas avaliadas antes da selecao final dos melhores pares.",
        "Muito Forte": "Matches com evidencias muito fortes, normalmente com varias chaves e sinais batendo ao mesmo tempo.",
        "Forte": "Matches com alta confianca, mas com menos evidencias que a faixa muito forte.",
        "Provavel": "Matches aceitos com score menor, indicados para revisao mais cuidadosa.",
    }

    sort_fields = {
        "Confianca": {"field": "confidence", "type": "string"},
        "Score": {"field": "score", "type": "number"},
        "Lote AKD": {"field": "akd_lote", "type": "string"},
        "Lote CT2": {"field": "ct2_lote", "type": "string"},
        "Data AKD": {"field": "akd_data", "type": "string"},
        "Data CT2": {"field": "ct2_data", "type": "string"},
        "Valor AKD": {"field": "akd_valor", "type": "number"},
        "Valor CT2": {"field": "ct2_valor", "type": "number"},
        "DOC AKD": {"field": "akd_xdoc", "type": "string"},
        "DOC CT2": {"field": "ct2_xdoc", "type": "string"},
        "AP AKD": {"field": "akd_xnumap", "type": "string"},
        "Doc APEX CT2": {"field": "ct2_xdocum", "type": "string"},
        "Conta Ref AKD": {"field": "akd_conta_referencia", "type": "string"},
        "Debito CT2": {"field": "ct2_debito", "type": "string"},
        "Credito CT2": {"field": "ct2_credito", "type": "string"},
        "CC Debito CT2": {"field": "ct2_centro_debito", "type": "string"},
        "CC Credito CT2": {"field": "ct2_centro_credito", "type": "string"},
        "Historico AKD": {"field": "akd_historico", "type": "string"},
        "Historico CT2": {"field": "ct2_historico", "type": "string"},
        "RECNO AKD": {"field": "recno_akd", "type": "number"},
        "RECNO CT2": {"field": "recno_ct2", "type": "number"},
    }

    report_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatorio de Conciliacao AKD x CT2</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffdf8;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #dfd4c4;
      --accent: #0f766e;
      --accent-2: #b45309;
      --good: #166534;
      --good-bg: #dcfce7;
      --mid: #92400e;
      --mid-bg: #fef3c7;
      --warn: #9a3412;
      --warn-bg: #ffedd5;
      --shadow: 0 18px 50px rgba(68, 47, 24, 0.12);
      --font: "Segoe UI", "Aptos", sans-serif;
      --mono: "Cascadia Code", "Consolas", monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--font);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.12), transparent 26%),
        radial-gradient(circle at top right, rgba(180,83,9,0.12), transparent 28%),
        linear-gradient(180deg, #f8f3ea 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(15,118,110,0.94), rgba(17,94,89,0.88));
      color: white;
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
    }}
    .hero p {{
      margin: 0;
      max-width: 900px;
      color: rgba(255,255,255,0.88);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin: 18px 0 22px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .card .label {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      width: fit-content;
    }}
    .card .value {{
      font-size: 28px;
      font-weight: 700;
    }}
    .filters {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow);
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      align-items: end;
    }}
    .field {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .field label {{
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      width: fit-content;
    }}
    .field input, .field select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 11px 12px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }}
    .table-wrap {{
        margin-top: 18px;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 20px;
        overflow: hidden;
        box-shadow: var(--shadow);
      }}
      .tabs {{
        display: flex;
        gap: 10px;
        padding: 16px 18px 0;
        flex-wrap: wrap;
      }}
      .tab-btn {{
        border: 1px solid var(--line);
        background: #f8f4ec;
        color: var(--ink);
        border-radius: 999px;
        padding: 10px 14px;
        font: inherit;
        cursor: pointer;
        font-weight: 600;
      }}
      .tab-btn.active {{
        background: var(--accent);
        color: white;
        border-color: var(--accent);
      }}
    .scroll-hint {{
      padding: 10px 18px 0;
      font-size: 12px;
      color: var(--muted);
    }}
      .resize-hint {{
        padding: 4px 18px 10px;
        font-size: 12px;
        color: var(--accent);
        font-weight: 600;
      }}
    .top-scroll {{
      overflow-x: auto;
      overflow-y: hidden;
      padding: 0 18px 8px;
    }}
    .top-scroll-inner {{
      height: 1px;
    }}
    .table-meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(15,118,110,0.04);
      gap: 12px;
      flex-wrap: wrap;
    }}
    .table-meta strong {{
      color: var(--accent);
    }}
    .table-scroll {{
      overflow: auto;
      max-height: 72vh;
    }}
    table {{
      width: max-content;
      min-width: 100%;
      border-collapse: collapse;
      min-width: 1700px;
      font-size: 13px;
      table-layout: fixed;
    }}
    th, td {{
      border-bottom: 1px solid #efe6da;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
      th {{
        position: sticky;
        top: 0;
        background: #f8f4ec;
        z-index: 1;
      color: #4b5563;
      font-size: 12px;
      text-transform: uppercase;
        letter-spacing: 0.05em;
        position: sticky;
      }}
      th.sorted {{
        background: #eef6f4;
      }}
    tr:hover td {{
      background: #fffcf6;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .confidence-muito_forte {{ background: var(--good-bg); color: var(--good); }}
    .confidence-forte {{ background: var(--mid-bg); color: var(--mid); }}
    .confidence-provavel {{ background: var(--warn-bg); color: var(--warn); }}
    .mono {{ font-family: var(--mono); }}
    .muted {{ color: var(--muted); }}
    .history-cell {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .history-expanded {{
      max-width: none !important;
    }}
    .col-resizer {{
      position: absolute;
      top: 0;
      right: 0;
      width: 10px;
      height: 100%;
      cursor: col-resize;
      user-select: none;
      touch-action: none;
      border-right: 2px dashed rgba(15,118,110,0.28);
    }}
    .col-resizer:hover,
    .col-resizer.active {{
      background: rgba(15,118,110,0.16);
      border-right-color: rgba(15,118,110,0.9);
    }}
    .th-help {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      position: relative;
      user-select: none;
    }}
    .th-help .help-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }}
    .th-help .help-dot {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: rgba(15,118,110,0.12);
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      border: 1px solid rgba(15,118,110,0.18);
    }}
    .history-toggle {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-left: 6px;
      padding: 1px 6px;
      border-radius: 999px;
      border: 1px solid rgba(15,118,110,0.24);
      background: rgba(15,118,110,0.08);
      color: var(--accent);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      cursor: pointer;
      user-select: none;
    }}
    .history-toggle:hover {{
      background: rgba(15,118,110,0.16);
    }}
    .th-help .sort-label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }}
    .th-help .header-tools {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .th-help .sort-arrow {{
      font-size: 10px;
      color: var(--accent);
      min-width: 12px;
      text-align: center;
    }}
    .help-pop {{
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      min-width: 240px;
      max-width: 320px;
      padding: 10px 12px;
      border-radius: 12px;
      background: #fffdf8;
      color: var(--ink);
      border: 1px solid var(--line);
      box-shadow: 0 20px 35px rgba(31, 41, 55, 0.16);
      text-transform: none;
      letter-spacing: normal;
      font-size: 12px;
      line-height: 1.45;
      white-space: normal;
      z-index: 5;
    }}
    .th-help.open .help-pop {{
      display: block;
    }}
    .btn {{
      border: 0;
      border-radius: 12px;
      padding: 11px 14px;
      font: inherit;
      cursor: pointer;
      background: var(--accent);
      color: white;
      font-weight: 600;
    }}
    @media (max-width: 900px) {{
      .wrap {{ padding: 16px; }}
      .hero h1 {{ font-size: 26px; }}
      .table-scroll {{ max-height: none; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Relatorio de Conciliacao AKD x CT2</h1>
      <p>Conferir a conciliacao entre as bases AKD e CT2.</p>
    </section>

    <section class="cards">
      <div class="card"><div class="label" data-title="Matches Selecionados">Matches Selecionados</div><div class="value" id="sumMatches"></div></div>
      <div class="card"><div class="label" data-title="Candidatos Gerados">Candidatos Gerados</div><div class="value" id="sumCandidates"></div></div>
      <div class="card"><div class="label" data-title="Muito Forte">Muito Forte</div><div class="value" id="sumMuitoForte"></div></div>
      <div class="card"><div class="label" data-title="Forte">Forte</div><div class="value" id="sumForte"></div></div>
      <div class="card"><div class="label" data-title="Provavel">Provavel</div><div class="value" id="sumProvavel"></div></div>
    </section>

    <section class="filters">
      <div class="field">
        <label for="search" data-title="Busca livre">Busca livre</label>
        <input id="search" type="text" placeholder="Procure em qualquer coluna: historico, documento, conta, valor, recno...">
      </div>
      <div class="field">
        <label for="confidence" data-title="Confianca">Confianca</label>
        <select id="confidence">
          <option value="">Todas</option>
          <option value="muito_forte">Muito forte</option>
          <option value="forte">Forte</option>
          <option value="provavel">Provavel</option>
        </select>
      </div>
      <div class="field">
        <label for="yearFilter" data-title="Ano">Ano</label>
        <select id="yearFilter">
          <option value="">Todos</option>
        </select>
      </div>
      <div class="field">
        <label for="quarterFilter" data-title="Trimestre">Trimestre</label>
        <select id="quarterFilter">
          <option value="">Todos</option>
        </select>
      </div>
      <div class="field">
        <label for="minScore" data-title="Score minimo">Score minimo</label>
        <input id="minScore" type="number" min="0" value="0">
      </div>
      <div class="field">
        <label for="reason" data-title="Motivo">Motivo</label>
        <select id="reason">
          <option value="">Todos</option>
          <option value="xdoc">Tem xdoc</option>
          <option value="xnumap_xdocum">Tem xnumap/doc apex</option>
          <option value="ent05_conta">Tem conta equivalente</option>
          <option value="texto_070">Texto forte</option>
          <option value="tokens_8+">Tokens fortes</option>
        </select>
      </div>
      <div class="field">
        <label for="onlySameValue" data-title="Valor igual">Valor igual</label>
        <select id="onlySameValue">
          <option value="">Todos</option>
          <option value="sim">Somente valor igual</option>
        </select>
      </div>
      <div class="field">
        <label for="dateStatusFilter" data-title="Data divergente">Data divergente</label>
        <select id="dateStatusFilter">
          <option value="">Todos</option>
          <option value="ok">Data alinhada</option>
          <option value="divergente">Data divergente</option>
          <option value="sem_referencia">Sem referencia</option>
        </select>
      </div>
      <div class="field">
        <label for="valueStatusFilter" data-title="Valor divergente">Valor divergente</label>
        <select id="valueStatusFilter">
          <option value="">Todos</option>
          <option value="ok">Valor alinhado</option>
          <option value="divergente">Valor divergente</option>
          <option value="sem_referencia">Sem referencia</option>
        </select>
      </div>
      <div class="field">
        <label for="accountStatusFilter" data-title="Conta divergente">Conta divergente</label>
        <select id="accountStatusFilter">
          <option value="">Todos</option>
          <option value="ok">Conta alinhada</option>
          <option value="divergente">Conta divergente</option>
          <option value="sem_referencia">Sem referencia</option>
        </select>
      </div>
      <div class="field">
        <label data-title="Limpar filtros">Limpar filtros</label>
        <button class="btn" id="resetBtn" type="button">Limpar filtros</button>
      </div>
    </section>

      <section class="table-wrap">
        <div class="tabs">
          <button class="tab-btn active" data-tab="matches">Matches</button>
          <button class="tab-btn" data-tab="akd_unmatched">AKD sem match</button>
          <button class="tab-btn" data-tab="ct2_unmatched">CT2 sem match</button>
        </div>
        <div class="table-meta">
        <div><strong id="visibleCount"></strong> <span id="visibleLabel">matches visiveis</span></div>
          <div class="muted">Busca livre cobre todas as colunas do relatorio</div>
        </div>
      <div class="scroll-hint">Use a barra horizontal para navegar pelas colunas da direita.</div>
        <div class="resize-hint">Arraste a borda pontilhada no lado direito da coluna para ajustar a largura ou de duplo clique para autoajustar como no Excel.</div>
      <div class="top-scroll" id="topScroll">
        <div class="top-scroll-inner" id="topScrollInner"></div>
      </div>
      <div class="table-scroll">
        <table id="resultTable">
          <thead>
              <tr>
                <th data-title="Confianca" data-width="130">Confianca</th>
                <th data-title="Score" data-width="90">Score</th>
                <th data-title="Lote AKD" data-width="110">Lote AKD</th>
                <th data-title="Lote CT2" data-width="110">Lote CT2</th>
                <th data-title="Data AKD" data-width="110">Data AKD</th>
                <th data-title="Data CT2" data-width="110">Data CT2</th>
              <th data-title="Valor AKD" data-width="120">Valor AKD</th>
              <th data-title="Valor CT2" data-width="120">Valor CT2</th>
              <th data-title="DOC AKD" data-width="130">DOC AKD</th>
              <th data-title="DOC CT2" data-width="130">DOC CT2</th>
              <th data-title="AP AKD" data-width="130">AP AKD</th>
              <th data-title="Doc APEX CT2" data-width="140">Doc APEX CT2</th>
              <th data-title="Conta Ref AKD" data-width="130">Conta Ref AKD</th>
              <th data-title="Debito CT2" data-width="130">Debito CT2</th>
              <th data-title="Credito CT2" data-width="130">Credito CT2</th>
              <th data-title="CC Debito CT2" data-width="140">CC Debito CT2</th>
              <th data-title="CC Credito CT2" data-width="140">CC Credito CT2</th>
              <th data-title="Historico AKD" data-width="280">Historico AKD</th>
              <th data-title="Historico CT2" data-width="280">Historico CT2</th>
              <th data-title="RECNO AKD" data-width="120">RECNO AKD</th>
              <th data-title="RECNO CT2" data-width="120">RECNO CT2</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>
  </div>

    <script>
      const report = {json.dumps(report_data, ensure_ascii=False)};
      const rowsEl = document.getElementById("rows");
      const visibleCountEl = document.getElementById("visibleCount");
      const visibleLabelEl = document.getElementById("visibleLabel");
      const searchEl = document.getElementById("search");
    const confidenceEl = document.getElementById("confidence");
    const yearFilterEl = document.getElementById("yearFilter");
    const quarterFilterEl = document.getElementById("quarterFilter");
    const minScoreEl = document.getElementById("minScore");
    const reasonEl = document.getElementById("reason");
    const onlySameValueEl = document.getElementById("onlySameValue");
    const dateStatusFilterEl = document.getElementById("dateStatusFilter");
    const valueStatusFilterEl = document.getElementById("valueStatusFilter");
    const accountStatusFilterEl = document.getElementById("accountStatusFilter");
    const resetBtn = document.getElementById("resetBtn");
    const topScrollEl = document.getElementById("topScroll");
    const topScrollInnerEl = document.getElementById("topScrollInner");
      const tableWrapEl = document.querySelector(".table-scroll");
      const resultTableEl = document.getElementById("resultTable");
      const tabButtons = Array.from(document.querySelectorAll("[data-tab]"));
      const headerHelp = {json.dumps(header_help, ensure_ascii=False)};
    const filterHelp = {json.dumps(filter_help, ensure_ascii=False)};
    const summaryHelp = {json.dumps(summary_help, ensure_ascii=False)};
    const sortFields = {json.dumps(sort_fields, ensure_ascii=False)};
    const confidenceRank = {{ muito_forte: 3, forte: 2, provavel: 1 }};
    const historyTitles = new Set(["Historico AKD", "Historico CT2"]);
    const preferredWidths = {{
      "Confianca": 130,
      "Score": 90,
      "Lote AKD": 110,
      "Lote CT2": 110,
      "Data AKD": 110,
      "Data CT2": 110,
      "Valor AKD": 120,
      "Valor CT2": 120,
      "DOC AKD": 130,
      "DOC CT2": 130,
      "AP AKD": 130,
      "Doc APEX CT2": 140,
      "Conta Ref AKD": 130,
      "Debito CT2": 130,
      "Credito CT2": 130,
      "CC Debito CT2": 140,
      "CC Credito CT2": 140,
      "Historico AKD": 320,
      "Historico CT2": 320,
      "RECNO AKD": 120,
      "RECNO CT2": 120,
    }};
      let sortState = {{ title: "", direction: "" }};
      const expandedHistory = new Set();
      let activeTab = "matches";
      let currentColumns = [];
      const tabConfigs = {{
        matches: {{
          label: "matches visiveis",
          rows: report.rows,
          columns: [
            {{ title: "Confianca", field: "confidence", className: "confidence" }},
            {{ title: "Score", field: "score", className: "mono" }},
            {{ title: "Lote AKD", field: "akd_lote", className: "mono" }},
            {{ title: "Lote CT2", field: "ct2_lote", className: "mono" }},
            {{ title: "Data AKD", field: "akd_data", className: "mono" }},
            {{ title: "Data CT2", field: "ct2_data", className: "mono muted" }},
            {{ title: "Valor AKD", field: "akd_valor", className: "mono" }},
            {{ title: "Valor CT2", field: "ct2_valor", className: "mono" }},
            {{ title: "DOC AKD", field: "akd_xdoc", className: "mono" }},
            {{ title: "DOC CT2", field: "ct2_xdoc", className: "mono" }},
            {{ title: "AP AKD", field: "akd_xnumap", className: "mono" }},
            {{ title: "Doc APEX CT2", field: "ct2_xdocum", className: "mono" }},
            {{ title: "Conta Ref AKD", field: "akd_conta_referencia", className: "mono" }},
            {{ title: "Debito CT2", field: "ct2_debito", className: "mono" }},
            {{ title: "Credito CT2", field: "ct2_credito", className: "mono" }},
            {{ title: "CC Debito CT2", field: "ct2_centro_debito", className: "mono" }},
            {{ title: "CC Credito CT2", field: "ct2_centro_credito", className: "mono" }},
            {{ title: "Historico AKD", field: "akd_historico", className: "history-cell", isHistory: true }},
            {{ title: "Historico CT2", field: "ct2_historico", className: "history-cell", isHistory: true }},
            {{ title: "RECNO AKD", field: "recno_akd", className: "mono" }},
            {{ title: "RECNO CT2", field: "recno_ct2", className: "mono" }},
          ],
        }},
        akd_unmatched: {{
          label: "registros AKD sem match",
          rows: report.akd_unmatched_rows,
          columns: [
            {{ title: "Lote AKD", field: "akd_lote", className: "mono" }},
            {{ title: "Data AKD", field: "akd_data", className: "mono" }},
            {{ title: "Valor AKD", field: "akd_valor", className: "mono" }},
            {{ title: "DOC AKD", field: "akd_xdoc", className: "mono" }},
            {{ title: "AP AKD", field: "akd_xnumap", className: "mono" }},
            {{ title: "Conta Ref AKD", field: "akd_conta_referencia", className: "mono" }},
            {{ title: "Historico AKD", field: "akd_historico", className: "history-cell", isHistory: true }},
            {{ title: "RECNO AKD", field: "recno_akd", className: "mono" }},
          ],
        }},
        ct2_unmatched: {{
          label: "registros CT2 sem match",
          rows: report.ct2_unmatched_rows,
          columns: [
            {{ title: "Lote CT2", field: "ct2_lote", className: "mono" }},
            {{ title: "Data CT2", field: "ct2_data", className: "mono" }},
            {{ title: "Valor CT2", field: "ct2_valor", className: "mono" }},
            {{ title: "DOC CT2", field: "ct2_xdoc", className: "mono" }},
            {{ title: "Doc APEX CT2", field: "ct2_xdocum", className: "mono" }},
            {{ title: "Debito CT2", field: "ct2_debito", className: "mono" }},
            {{ title: "Credito CT2", field: "ct2_credito", className: "mono" }},
            {{ title: "CC Debito CT2", field: "ct2_centro_debito", className: "mono" }},
            {{ title: "CC Credito CT2", field: "ct2_centro_credito", className: "mono" }},
            {{ title: "Historico CT2", field: "ct2_historico", className: "history-cell", isHistory: true }},
            {{ title: "RECNO CT2", field: "recno_ct2", className: "mono" }},
          ],
        }},
      }};

    document.getElementById("sumMatches").textContent = report.summary.matches_selecionados.toLocaleString("pt-BR");
    document.getElementById("sumCandidates").textContent = report.summary.candidatos_gerados.toLocaleString("pt-BR");
    document.getElementById("sumMuitoForte").textContent = report.summary.muito_forte.toLocaleString("pt-BR");
    document.getElementById("sumForte").textContent = report.summary.forte.toLocaleString("pt-BR");
    document.getElementById("sumProvavel").textContent = report.summary.provavel.toLocaleString("pt-BR");
    yearFilterEl.innerHTML = `<option value="">Todos</option>` + report.years.map(year => `<option value="${{escapeHtml(year)}}">${{escapeHtml(year)}}</option>`).join("");
    quarterFilterEl.innerHTML = `<option value="">Todos</option>` + report.quarters.map(quarter => `<option value="${{escapeHtml(quarter)}}">${{escapeHtml(quarter)}}</option>`).join("");

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function formatConfidence(value) {{
      const label = value === "muito_forte" ? "Muito forte" : value === "forte" ? "Forte" : "Provavel";
      return `<span class="pill confidence-${{value}}">${{label}}</span>`;
    }}

    function renderHeader(title) {{
      const expand = historyTitles.has(title)
        ? `<span class="history-toggle" data-expand-title="${{escapeHtml(title)}}" title="Expandir ou recolher a coluna de historico">EXP</span>`
        : ``;
      return `
        <span class="sort-label" data-sort-title="${{escapeHtml(title)}}">
          <span>${{escapeHtml(title)}}</span>
        </span>
        ${{expand}}
        <span class="col-resizer" data-resizer></span>
      `;
    }}

    function renderFilterLabel(title) {{
      const help = filterHelp[title] || "";
      return `
        <span class="th-help" data-help>
          <span class="help-toggle" data-help-toggle>
            <span>${{escapeHtml(title)}}</span>
            <span class="help-dot">i</span>
          </span>
          <span class="help-pop">${{escapeHtml(help)}}</span>
        </span>
      `;
    }}

    function renderSummaryLabel(title) {{
      const help = summaryHelp[title] || "";
      return `
        <span class="th-help" data-help>
          <span class="help-toggle" data-help-toggle>
            <span>${{escapeHtml(title)}}</span>
            <span class="help-dot">i</span>
          </span>
          <span class="help-pop">${{escapeHtml(help)}}</span>
        </span>
      `;
    }}

    function syncHorizontalScroll() {{
      topScrollInnerEl.style.width = `${{resultTableEl.scrollWidth}}px`;
    }}

    function autoFitColumns() {{
      const headers = Array.from(resultTableEl.querySelectorAll("thead th"));
      const bodyRows = Array.from(rowsEl.querySelectorAll("tr")).slice(0, 24);
      headers.forEach((th, index) => {{
        if (th.dataset.manual === "1") return;
        const title = th.getAttribute("data-title") || "";
        const base = preferredWidths[title] || Number(th.getAttribute("data-width") || "120");
        if (historyTitles.has(title) && expandedHistory.has(title)) {{
          th.style.width = "900px";
          return;
        }}
        let maxLen = title.length;
        bodyRows.forEach((row) => {{
          const cell = row.children[index];
          if (!cell) return;
          const text = (cell.textContent || "").trim();
          maxLen = Math.max(maxLen, text.length);
        }});
        const isHistory = title === "Historico AKD" || title === "Historico CT2";
        const cap = isHistory ? 360 : 240;
        const floor = isHistory ? 240 : Math.max(90, base - 10);
        const computed = Math.min(cap, Math.max(floor, Math.min(maxLen, 28) * 7 + 34, base));
        th.style.width = `${{computed}}px`;
      }});
      syncHorizontalScroll();
    }}

    function autoFitSingleColumn(th, index) {{
      const title = th.getAttribute("data-title") || "";
      const base = preferredWidths[title] || Number(th.getAttribute("data-width") || "120");
      const bodyRows = Array.from(rowsEl.querySelectorAll("tr")).slice(0, 120);
      let maxLen = title.length;
      bodyRows.forEach((row) => {{
        const cell = row.children[index];
        if (!cell) return;
        const text = (cell.textContent || "").trim();
        maxLen = Math.max(maxLen, text.length);
      }});
      const isHistory = title === "Historico AKD" || title === "Historico CT2";
      const cap = isHistory ? 900 : 340;
      const floor = isHistory ? 240 : Math.max(90, base - 10);
      const computed = Math.min(cap, Math.max(floor, Math.min(maxLen, 120) * 7 + 34, base));
      th.style.width = `${{computed}}px`;
      th.dataset.manual = "1";
      syncHorizontalScroll();
    }}

    function initColumnResize() {{
      const headers = Array.from(resultTableEl.querySelectorAll("thead th"));
      headers.forEach((th) => {{
        if (!th.style.width) {{
          const width = th.getAttribute("data-width");
          if (width) th.style.width = `${{width}}px`;
        }}
      }});

        headers.forEach((th, index) => {{
          const resizer = th.querySelector("[data-resizer]");
          if (!resizer || resizer.dataset.bound === "1") return;
          resizer.dataset.bound = "1";
        resizer.addEventListener("mousedown", (event) => {{
          event.preventDefault();
          event.stopPropagation();
          const startX = event.clientX;
          const startWidth = th.offsetWidth;
          resizer.classList.add("active");

          const onMove = (moveEvent) => {{
            const nextWidth = Math.max(80, startWidth + (moveEvent.clientX - startX));
            th.style.width = `${{nextWidth}}px`;
            th.dataset.manual = "1";
            syncHorizontalScroll();
          }};

          const onUp = () => {{
            resizer.classList.remove("active");
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
          }};

            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
          }});
          resizer.addEventListener("dblclick", (event) => {{
            event.preventDefault();
            event.stopPropagation();
            autoFitSingleColumn(th, index);
          }});
        }});
      }}

    function parseSortableValue(row, title) {{
      const config = sortFields[title];
      if (!config) return "";
      const value = row[config.field];
      if (config.type === "number") {{
        const parsed = Number(String(value ?? "").replace(",", "."));
        return Number.isNaN(parsed) ? -Infinity : parsed;
      }}
      if (config.field === "confidence") {{
        return confidenceRank[value] || 0;
      }}
      return String(value ?? "").toLowerCase();
    }}

    function sortRows(rows) {{
      if (!sortState.title || !sortState.direction) return rows;
      const direction = sortState.direction === "asc" ? 1 : -1;
      return [...rows].sort((a, b) => {{
        const va = parseSortableValue(a, sortState.title);
        const vb = parseSortableValue(b, sortState.title);
        if (va < vb) return -1 * direction;
        if (va > vb) return 1 * direction;
        return 0;
      }});
    }}

    function rowMatches(row) {{
      if (activeTab !== "matches") {{
        const term = searchEl.value.trim().toLowerCase();
        if (!term) return true;
        const haystack = Object.values(row).join(" ").toLowerCase();
        return haystack.includes(term);
      }}
      const term = searchEl.value.trim().toLowerCase();
      const confidence = confidenceEl.value;
      const year = yearFilterEl.value;
      const quarter = quarterFilterEl.value;
      const minScore = Number(minScoreEl.value || 0);
      const reason = reasonEl.value;
      const onlySameValue = onlySameValueEl.value;
      const dateStatus = dateStatusFilterEl.value;
      const valueStatus = valueStatusFilterEl.value;
      const accountStatus = accountStatusFilterEl.value;

      if (confidence && row.confidence !== confidence) return false;
      if (year && row.akd_year !== year) return false;
      if (quarter && row.akd_quarter !== quarter) return false;
      if (row.score < minScore) return false;
      if (reason && !String(row.reasons).includes(reason)) return false;
      if (onlySameValue === "sim" && row.akd_valor !== row.ct2_valor) return false;
      if (dateStatus && row.date_status !== dateStatus) return false;
      if (valueStatus && row.value_status !== valueStatus) return false;
      if (accountStatus && row.account_status !== accountStatus) return false;

      if (!term) return true;

        const haystack = [
          row.confidence,
          row.reasons,
          row.akd_lote,
          row.ct2_lote,
          row.akd_data,
          row.ct2_data,
        row.akd_valor,
        row.ct2_valor,
        row.akd_xdoc,
        row.ct2_xdoc,
        row.akd_xnumap,
        row.ct2_xdocum,
        row.akd_conta_referencia,
        row.ct2_debito,
        row.ct2_credito,
        row.ct2_centro_debito,
        row.ct2_centro_credito,
        row.akd_historico,
        row.ct2_historico,
        row.recno_akd,
        row.recno_ct2
      ].join(" ").toLowerCase();

      return haystack.includes(term);
    }}

    function renderThead() {{
      const theadRow = resultTableEl.querySelector("thead tr");
      theadRow.innerHTML = currentColumns
        .map(col => `<th data-title="${{escapeHtml(col.title)}}" data-width="${{preferredWidths[col.title] || 120}}">${{col.title}}</th>`)
        .join("");
    }}

    function renderBodyCell(row, col) {{
      const rawValue = row[col.field] ?? "";
      if (col.field === "confidence") {{
        return `<td>${{formatConfidence(rawValue)}}</td>`;
      }}
      const cls = col.className ? ` class="${{col.className}}"` : "";
      const title = col.isHistory ? ` title="${{escapeHtml(rawValue)}}"` : "";
      return `<td${{cls}}${{title}}>${{escapeHtml(rawValue)}}</td>`;
    }}

    function render() {{
      currentColumns = tabConfigs[activeTab].columns;
      renderThead();
      const filtered = sortRows(tabConfigs[activeTab].rows.filter(rowMatches));
      visibleCountEl.textContent = filtered.length.toLocaleString("pt-BR");
      visibleLabelEl.textContent = tabConfigs[activeTab].label;
      const headers = resultTableEl.querySelectorAll("thead th");
      headers.forEach(th => {{
        const title = th.getAttribute("data-title");
        if (title) {{
          th.innerHTML = renderHeader(title);
          th.title = headerHelp[title] || title;
          th.classList.toggle("sorted", sortState.title === title);
        }}
      }});
      const filterLabels = document.querySelectorAll(".filters label[data-title]");
      filterLabels.forEach(label => {{
        const title = label.getAttribute("data-title");
        if (title) label.innerHTML = renderFilterLabel(title);
      }});
      const summaryLabels = document.querySelectorAll(".cards .label[data-title]");
      summaryLabels.forEach(label => {{
        const title = label.getAttribute("data-title");
        if (title) label.innerHTML = renderSummaryLabel(title);
        }});
        initColumnResize();
        rowsEl.innerHTML = filtered.map(row => `
          <tr>${{currentColumns.map(col => renderBodyCell(row, col)).join("")}}</tr>
        `).join("");
      const headerList = Array.from(resultTableEl.querySelectorAll("thead th"));
      headerList.forEach((th, index) => {{
        const title = th.getAttribute("data-title") || "";
        const expanded = expandedHistory.has(title);
        Array.from(rowsEl.querySelectorAll("tr")).forEach((row) => {{
          const cell = row.children[index];
          if (!cell) return;
          if (expanded && historyTitles.has(title)) {{
            cell.classList.add("history-expanded");
          }} else {{
            cell.classList.remove("history-expanded");
          }}
        }});
      }});
      autoFitColumns();
      syncHorizontalScroll();
    }}

      [searchEl, confidenceEl, yearFilterEl, quarterFilterEl, minScoreEl, reasonEl, onlySameValueEl, dateStatusFilterEl, valueStatusFilterEl, accountStatusFilterEl].forEach(el => {{
        el.addEventListener("input", render);
        el.addEventListener("change", render);
      }});

      tabButtons.forEach((button) => {{
        button.addEventListener("click", () => {{
          activeTab = button.getAttribute("data-tab") || "matches";
          tabButtons.forEach((item) => item.classList.toggle("active", item === button));
          render();
        }});
      }});

    resetBtn.addEventListener("click", () => {{
      searchEl.value = "";
      confidenceEl.value = "";
      yearFilterEl.value = "";
      quarterFilterEl.value = "";
      minScoreEl.value = "0";
      reasonEl.value = "";
      onlySameValueEl.value = "";
      dateStatusFilterEl.value = "";
      valueStatusFilterEl.value = "";
      accountStatusFilterEl.value = "";
      render();
    }});

    let syncingTop = false;
    let syncingBottom = false;

    topScrollEl.addEventListener("scroll", () => {{
      if (syncingBottom) return;
      syncingTop = true;
      tableWrapEl.scrollLeft = topScrollEl.scrollLeft;
      syncingTop = false;
    }});

    tableWrapEl.addEventListener("scroll", () => {{
      if (syncingTop) return;
      syncingBottom = true;
      topScrollEl.scrollLeft = tableWrapEl.scrollLeft;
      syncingBottom = false;
    }});

    document.addEventListener("click", (event) => {{
      const sortTrigger = event.target.closest("[data-sort-title]");
      if (sortTrigger) {{
        const title = sortTrigger.getAttribute("data-sort-title") || "";
        if (sortState.title !== title) {{
          sortState = {{ title, direction: "asc" }};
        }} else if (sortState.direction === "asc") {{
          sortState = {{ title, direction: "desc" }};
        }} else if (sortState.direction === "desc") {{
          sortState = {{ title: "", direction: "" }};
        }} else {{
          sortState = {{ title, direction: "asc" }};
        }}
        render();
        event.stopPropagation();
        return;
      }}
      const expandTrigger = event.target.closest("[data-expand-title]");
      if (expandTrigger) {{
        const title = expandTrigger.getAttribute("data-expand-title") || "";
        const th = expandTrigger.closest("th");
        if (expandedHistory.has(title)) {{
          expandedHistory.delete(title);
          if (th) {{
            delete th.dataset.manual;
            th.style.width = "";
          }}
        }} else {{
          expandedHistory.add(title);
          if (th) {{
            th.style.width = "900px";
            th.dataset.manual = "1";
          }}
        }}
        render();
        event.preventDefault();
        event.stopPropagation();
        return;
      }}
      const helpToggle = event.target.closest("[data-help-toggle]");
      if (helpToggle) {{
        const trigger = helpToggle.closest("[data-help]");
        document.querySelectorAll("[data-help].open").forEach(item => {{
          if (item !== trigger) item.classList.remove("open");
        }});
        if (trigger) trigger.classList.toggle("open");
        event.preventDefault();
        event.stopPropagation();
        return;
      }}
      const trigger = event.target.closest("[data-help]");
      document.querySelectorAll("[data-help].open").forEach(item => {{
        if (item !== trigger) item.classList.remove("open");
      }});
      if (!trigger) return;
      trigger.classList.toggle("open");
      event.stopPropagation();
    }});

    window.addEventListener("resize", syncHorizontalScroll);

    render();
  </script>
</body>
</html>
"""
    report_path.write_text(report_html, encoding="utf-8")

    return {
        "candidatos_gerados": len(candidates),
        "matches_selecionados": len(selected),
        "por_confianca": dict(Counter(item.confidence for item in selected)),
        "arquivo_comparativo": "saida/comparativo_conciliacao.csv",
        "arquivo_html": "saida/relatorio_conciliacao.html",
    }


def build_summary(akd_rows: list[dict[str, str]], ct2_rows: list[dict[str, str]]) -> dict[str, object]:
    xdoc_summaries = summarize_overlap(
        akd_rows=akd_rows,
        ct2_rows=ct2_rows,
        akd_key="AKD_XDOC",
        ct2_key="CT2_XDOC",
        output_name="overlap_xdoc.csv",
    )
    xnumap_summaries = summarize_overlap(
        akd_rows=akd_rows,
        ct2_rows=ct2_rows,
        akd_key="AKD_XNUMAP",
        ct2_key="CT2_XDOCUM",
        output_name="overlap_xnumap.csv",
    )

    row_level = export_row_matches(akd_rows, ct2_rows)
    xdoc_status = Counter(item.status for item in xdoc_summaries)
    xnumap_status = Counter(item.status for item in xnumap_summaries)

    return {
        "arquivos": {
            "akd": "DADOS-AKD010.xlsx",
            "ct2": "DADOS-CT2010.xlsx",
        },
        "linhas": {
            "akd": len(akd_rows),
            "ct2": len(ct2_rows),
        },
        "sobreposicao_documental": {
            "akd_xdoc__ct2_xdoc": {
                "keys_em_comum": len(xdoc_summaries),
                "status": dict(xdoc_status),
            },
            "akd_xnumap__ct2_xdocum": {
                "keys_em_comum": len(xnumap_summaries),
                "status": dict(xnumap_status),
            },
        },
        "assinatura_residual": candidate_signatures(akd_rows, ct2_rows),
        "reconciliacao_linha_a_linha": row_level,
        "recomendacao": [
            "Priorizar match por AKD_XDOC = CT2_XDOC.",
            "Usar AKD_XNUMAP = CT2_XDOCUM como segunda camada.",
            "Usar competencia + valor como bloco residual para limitar candidatos.",
            "Reforcar score com similaridade de texto e com coincidencia de conta em AKD_ENT05.",
            "Selecionar apenas um melhor candidato por linha com score auditavel.",
        ],
    }


def main() -> None:
    log_step("Inicio da analise AKD x CT2")
    akd_path = RAW_DIR / "DADOS-AKD010.xlsx"
    ct2_path = RAW_DIR / "DADOS-CT2010.xlsx"

    akd_rows = read_excel_rows(akd_path)
    ct2_rows = read_excel_rows(ct2_path)
    summary = build_summary(akd_rows, ct2_rows)

    OUTPUT_DIR.mkdir(exist_ok=True)
    summary_path = OUTPUT_DIR / "resumo_analise.json"
    log_step(f"Exportando {summary_path.name}")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    log_step("Analise finalizada")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
