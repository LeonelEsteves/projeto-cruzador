from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import gerar_relatorio_conciliacao_akd_ct2 as cruzador


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "saida" / "descoberta_matches"

FIELD_CHECKS = [
    ("xdoc_exato", "AKD_XDOC", ["CT2_XDOC"], "text"),
    ("xdoc_at01cr", "AKD_XDOC", ["CT2_AT01CR"], "text"),
    ("xdoc_ct2_doc", "AKD_XDOC", ["CT2_DOC"], "text"),
    ("xnumap_xdocum", "AKD_XNUMAP", ["CT2_XDOCUM"], "text"),
    ("xnumap_at04db", "AKD_XNUMAP", ["CT2_AT04DB"], "text"),
    ("proc_900027_ri", "AKD_HIST", ["CT2_HIST"], "text"),
    ("idref_xnumct", "AKD_IDREF", ["CT2_XNUMCT"], "text"),
    ("conta_ref", "AKD_ENT05", ["CT2_DEBITO", "CT2_CREDIT"], "text"),
    ("cc", "AKD_CC", ["CT2_CCD", "CT2_CCC"], "text"),
    ("classe_valor", "AKD_CLVLR", ["CT2_CLVLDB", "CT2_CLVLCR"], "text"),
    ("item_contabil", "AKD_ITCTB", ["CT2_ITEMD", "CT2_ITEMC"], "text"),
    ("filial", "AKD_FILIAL", ["CT2_FILIAL", "CT2_FILORI"], "text"),
    ("historico_doc", "AKD_HIST", ["CT2_HIST"], "doc"),
    ("proc_hist_exato_900013_900025_900026", "AKD_HIST", ["CT2_HIST"], "text"),
    ("historico_expandido_doc", "AKD_XHISTO", ["CT2_HIST"], "doc"),
    ("chave_doc", "AKD_CHAVE", ["CT2_KEY"], "doc"),
    ("chave_token", "AKD_CHAVE", ["CT2_KEY"], "token"),
    ("xdoc_token", "AKD_XDOC", ["CT2_XDOC", "CT2_DOC"], "token"),
    ("codpla_origem", "AKD_CODPLA", ["CT2_ORIGEM"], "text"),
    ("tipo_tpsald", "AKD_TPSALD", ["CT2_TPSALD"], "text"),
    ("cliente_fornecedor", "AKD_ENT06", ["CT2_CODCLI", "CT2_CODFOR"], "text"),
    ("mes", "AKD_DATA", ["CT2_DATA"], "month"),
    ("ano", "AKD_DATA", ["CT2_DATA"], "year"),
    ("trimestre", "AKD_DATA", ["CT2_DATA"], "quarter"),
]

AKD_PROFILE_FIELDS = [
    "AKD_FILIAL",
    "AKD_STATUS",
    "AKD_LOTE",
    "AKD_ID",
    "AKD_DATA",
    "AKD_CLASSE",
    "AKD_OPER",
    "AKD_TIPO",
    "AKD_TPSALD",
    "AKD_IDREF",
    "AKD_CHAVE",
    "AKD_ITEM",
    "AKD_CODPLA",
    "AKD_CC",
    "AKD_ITCTB",
    "AKD_CLVLR",
    "AKD_UNIORC",
    "AKD_ENT05",
    "AKD_ENT06",
    "AKD_ENT07",
    "AKD_XNUMAP",
    "AKD_XCLSDE",
    "AKD_XDOC",
]

CT2_PROFILE_FIELDS = [
    "CT2_FILIAL",
    "CT2_DATA",
    "CT2_LOTE",
    "CT2_SBLOTE",
    "CT2_DOC",
    "CT2_LINHA",
    "CT2_MOEDLC",
    "CT2_DC",
    "CT2_DEBITO",
    "CT2_CREDIT",
    "CT2_DCD",
    "CT2_DCC",
    "CT2_HP",
    "CT2_CCD",
    "CT2_CCC",
    "CT2_ITEMD",
    "CT2_ITEMC",
    "CT2_CLVLDB",
    "CT2_CLVLCR",
    "CT2_ATIVDE",
    "CT2_ATIVCR",
    "CT2_ORIGEM",
    "CT2_ROTINA",
    "CT2_TPSALD",
    "CT2_CODCLI",
    "CT2_CODFOR",
    "CT2_AT01CR",
    "CT2_AT04DB",
    "CT2_XDOCUM",
    "CT2_XDOC",
    "CT2_XNUMCT",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analise profunda de match entre AKD e CT2 para descobrir novas regras."
    )
    parser.add_argument("--akd", help="Caminho da base AKD.")
    parser.add_argument("--ct2", help="Caminho da base CT2.")
    parser.add_argument("--top", type=int, default=5, help="Top candidatos por registro sem match.")
    parser.add_argument(
        "--modo",
        choices=["padrao", "amplo", "exaustivo"],
        default="amplo",
        help="Nivel de profundidade da busca.",
    )
    parser.add_argument(
        "--limite-grupo-valor",
        type=int,
        default=800,
        help="Limite para blocos de mesmo valor no modo exaustivo. 0 = sem limite.",
    )
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else ["vazio"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def score_sort_key(candidate: cruzador.CandidateMatch) -> tuple[int, int, float]:
    return (candidate.score, candidate.token_overlap, candidate.text_similarity)


def normalize_reason(reason: str) -> str:
    base = reason.split(":", 1)[0]
    if base.startswith("chave_estruturada_"):
        return "chave_estruturada"
    if base.startswith("doc_extra_"):
        return "doc_extra"
    if base.startswith("tokens_"):
        return "tokens"
    if base.startswith("texto_"):
        return "texto"
    return base


def reason_signature(reasons: str) -> str:
    parts = {normalize_reason(item) for item in reasons.split("|") if item}
    return "|".join(sorted(parts))


def classify_conflict(
    candidate: cruzador.CandidateMatch,
    selected_akd: set[str],
    selected_ct2: set[str],
    selected_pairs: set[tuple[str, str]],
) -> str:
    pair = (candidate.akd_recno, candidate.ct2_recno)
    if pair in selected_pairs:
        return "selecionado"
    if candidate.akd_recno in selected_akd and candidate.ct2_recno in selected_ct2:
        return "bloqueado_1x1"
    if candidate.akd_recno in selected_akd:
        return "bloqueado_por_akd"
    if candidate.ct2_recno in selected_ct2:
        return "bloqueado_por_ct2"
    return "nao_selecionado_livre"


def normalize_compare(kind: str, value: object) -> str:
    text = cruzador.clean(value)
    if not text:
        return ""
    if kind == "doc":
        docs = sorted(cruzador.extract_doc_keys(text))
        return docs[0] if docs else ""
    if kind == "token":
        tokens = sorted(cruzador.extract_structured_key_tokens(text))
        return tokens[0] if tokens else ""
    if kind == "month":
        return cruzador.month_from_akd_date(text) if len(text) == 8 else ""
    if kind == "year":
        return cruzador.year_from_akd_date(text) if len(text) == 8 else ""
    if kind == "quarter":
        return cruzador.quarter_from_akd_date(text) if len(text) == 8 else ""
    return text


def normalize_ct2_compare(kind: str, value: object) -> str:
    text = cruzador.clean(value)
    if not text:
        return ""
    if kind == "doc":
        docs = sorted(cruzador.extract_doc_keys(text))
        return docs[0] if docs else ""
    if kind == "token":
        tokens = sorted(cruzador.extract_structured_key_tokens(text))
        return tokens[0] if tokens else ""
    if kind == "month":
        return cruzador.month_from_ct2_row({"CT2_DATA": text, "CT2_HIST": text})
    if kind == "year":
        return cruzador.year_from_date(text)
    if kind == "quarter":
        return cruzador.quarter_from_date(text)
    return text


def load_rows(args: argparse.Namespace) -> tuple[Path, Path, list[dict[str, str]], list[dict[str, str]]]:
    akd_path = Path(args.akd).expanduser().resolve() if args.akd else cruzador.resolve_source_path(cruzador.RAW_DIR, "DADOS-AKD010")
    ct2_path = Path(args.ct2).expanduser().resolve() if args.ct2 else cruzador.resolve_source_path(cruzador.RAW_DIR, "DADOS-CT2010")
    akd_rows = cruzador.filter_akd_rows(cruzador.read_rows(akd_path))
    ct2_rows = cruzador.filter_ct2_rows(cruzador.read_rows(ct2_path))
    return akd_path, ct2_path, akd_rows, ct2_rows


def add_rows(index: dict[object, list[dict[str, str]]], key: object, row: dict[str, str]) -> None:
    if key in {"", None}:
        return
    index[key].append(row)


def build_candidate_pool(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
    modo: str,
    limite_grupo_valor: int,
) -> tuple[list[cruzador.CandidateMatch], dict[tuple[str, str], set[str]]]:
    cruzador.log_step(f"Gerando candidatos em modo {modo}")
    ct2_by_recno = {cruzador.normalize_recno(row["R_E_C_N_O_"]): row for row in ct2_rows}
    pool = {(c.akd_recno, c.ct2_recno): c for c in cruzador.build_candidate_pairs(akd_rows, ct2_rows)}
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for pair in pool:
        sources[pair].add("motor_atual")
    if modo == "padrao":
        return list(pool.values()), sources

    year_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    quarter_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    account_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    cc_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    class_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    item_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    filial_value: dict[tuple[str, Decimal], list[dict[str, str]]] = defaultdict(list)
    pure_value: dict[Decimal, list[dict[str, str]]] = defaultdict(list)

    for row in ct2_rows:
        value = cruzador.normalize_decimal(row.get("CT2_VALOR", ""))
        if value is None:
            continue
        add_rows(pure_value, value, row)
        add_rows(year_value, (cruzador.year_from_date(row.get("CT2_DATA", "")), value), row)
        add_rows(quarter_value, (cruzador.quarter_from_date(row.get("CT2_DATA", "")), value), row)
        for field in ["CT2_DEBITO", "CT2_CREDIT"]:
            add_rows(account_value, (cruzador.clean(row.get(field, "")), value), row)
        for field in ["CT2_CCD", "CT2_CCC"]:
            add_rows(cc_value, (cruzador.clean(row.get(field, "")), value), row)
        for field in ["CT2_CLVLDB", "CT2_CLVLCR"]:
            add_rows(class_value, (cruzador.clean(row.get(field, "")), value), row)
        for field in ["CT2_ITEMD", "CT2_ITEMC"]:
            add_rows(item_value, (cruzador.clean(row.get(field, "")), value), row)
        for field in ["CT2_FILIAL", "CT2_FILORI"]:
            add_rows(filial_value, (cruzador.clean(row.get(field, "")), value), row)

    progress = cruzador.ProgressBar(len(akd_rows), "Expandindo busca")
    for index, akd_row in enumerate(akd_rows, start=1):
        akd_value = cruzador.normalize_decimal(akd_row.get("AKD_VALOR1", ""))
        if akd_value is None:
            progress.update(index)
            continue
        blocks = [
            ("ano_valor", year_value.get((cruzador.year_from_akd_date(akd_row.get("AKD_DATA", "")), akd_value), [])),
            ("trimestre_valor", quarter_value.get((cruzador.quarter_from_akd_date(akd_row.get("AKD_DATA", "")), akd_value), [])),
            ("conta_valor", account_value.get((cruzador.clean(akd_row.get("AKD_ENT05", "")), akd_value), [])),
            ("cc_valor", cc_value.get((cruzador.clean(akd_row.get("AKD_CC", "")), akd_value), [])),
            ("classe_valor_bloco", class_value.get((cruzador.clean(akd_row.get("AKD_CLVLR", "")), akd_value), [])),
            ("item_valor_bloco", item_value.get((cruzador.clean(akd_row.get("AKD_ITCTB", "")), akd_value), [])),
            ("filial_valor", filial_value.get((cruzador.clean(akd_row.get("AKD_FILIAL", "")), akd_value), [])),
        ]
        if modo == "exaustivo":
            rows = pure_value.get(akd_value, [])
            if limite_grupo_valor <= 0 or len(rows) <= limite_grupo_valor:
                blocks.append(("valor_puro", rows))

        seen: dict[str, set[str]] = defaultdict(set)
        for source, rows in blocks:
            for ct2_row in rows:
                ct2_recno = cruzador.normalize_recno(ct2_row["R_E_C_N_O_"])
                seen[ct2_recno].add(source)

        for ct2_recno, block_sources in seen.items():
            ct2_row = ct2_by_recno[ct2_recno]
            candidate = cruzador.score_candidate(akd_row, ct2_row)
            if candidate is None:
                continue
            pair = (candidate.akd_recno, candidate.ct2_recno)
            current = pool.get(pair)
            if current is None or score_sort_key(candidate) > score_sort_key(current):
                pool[pair] = candidate
            sources[pair].update(block_sources)
        progress.update(index)

    return list(pool.values()), sources


def correlation_rows(
    candidates: list[cruzador.CandidateMatch],
    akd_map: dict[str, dict[str, str]],
    ct2_map: dict[str, dict[str, str]],
    selected_akd: set[str],
    selected_ct2: set[str],
    selected_pairs: set[tuple[str, str]],
) -> list[dict[str, object]]:
    stats: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for candidate in candidates:
        grupo = "selecionados" if (candidate.akd_recno, candidate.ct2_recno) in selected_pairs else "nao_selecionados"
        akd_row = akd_map[candidate.akd_recno]
        ct2_row = ct2_map[candidate.ct2_recno]
        for label, akd_field, ct2_fields, kind in FIELD_CHECKS:
            akd_value = normalize_compare(kind, akd_row.get(akd_field, ""))
            ct2_values = [normalize_ct2_compare(kind, ct2_row.get(field, "")) for field in ct2_fields]
            ct2_values = [value for value in ct2_values if value]
            status = "igual" if akd_value and akd_value in ct2_values else "diferente"
            if not akd_value:
                status = "akd_vazio"
            elif not ct2_values:
                status = "ct2_vazio"
            stats[(grupo, label)][status] += 1
    rows: list[dict[str, object]] = []
    for (grupo, label), counter in sorted(stats.items()):
        comparaveis = counter["igual"] + counter["diferente"]
        rows.append(
            {
                "grupo": grupo,
                "comparacao": label,
                "iguais": counter["igual"],
                "diferentes": counter["diferente"],
                "akd_vazio": counter["akd_vazio"],
                "ct2_vazio": counter["ct2_vazio"],
                "taxa_igualdade": round((counter["igual"] / comparaveis) * 100, 2) if comparaveis else 0,
            }
        )
    return rows


def build_field_profile_rows(rows: list[dict[str, str]], fields: list[str], prefix: str) -> list[dict[str, object]]:
    profile_rows: list[dict[str, object]] = []
    total = len(rows)
    for field in fields:
        non_empty_values = [cruzador.clean(row.get(field, "")) for row in rows]
        non_empty_values = [value for value in non_empty_values if value]
        distinct = len(set(non_empty_values))
        fill_rate = round((len(non_empty_values) / total) * 100, 2) if total else 0
        examples = " | ".join(sorted(set(non_empty_values[:3])))
        profile_rows.append(
            {
                "base": prefix,
                "campo": field,
                "preenchidos": len(non_empty_values),
                "fill_rate": fill_rate,
                "distintos": distinct,
                "exemplos": examples,
            }
        )
    return sorted(profile_rows, key=lambda item: (item["fill_rate"], item["distintos"]), reverse=True)


def build_cross_field_overlap_rows(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, akd_field, ct2_fields, kind in FIELD_CHECKS:
        akd_values = {
            normalize_compare(kind, row.get(akd_field, ""))
            for row in akd_rows
        }
        akd_values.discard("")
        ct2_values: set[str] = set()
        for row in ct2_rows:
            for field in ct2_fields:
                value = normalize_ct2_compare(kind, row.get(field, ""))
                if value:
                    ct2_values.add(value)
        overlap = akd_values & ct2_values
        rows.append(
            {
                "comparacao": label,
                "akd_campo": akd_field,
                "ct2_campos": "|".join(ct2_fields),
                "tipo_normalizacao": kind,
                "akd_distintos": len(akd_values),
                "ct2_distintos": len(ct2_values),
                "distintos_em_comum": len(overlap),
                "taxa_overlap_akd": round((len(overlap) / len(akd_values)) * 100, 2) if akd_values else 0,
                "taxa_overlap_ct2": round((len(overlap) / len(ct2_values)) * 100, 2) if ct2_values else 0,
            }
        )
    return sorted(rows, key=lambda item: (item["distintos_em_comum"], item["taxa_overlap_akd"]), reverse=True)


def main() -> None:
    args = parse_args()
    cruzador.log_step("Inicio da analise profunda de matches")
    akd_path, ct2_path, akd_rows, ct2_rows = load_rows(args)
    akd_map = {cruzador.normalize_recno(row["R_E_C_N_O_"]): row for row in akd_rows}
    ct2_map = {cruzador.normalize_recno(row["R_E_C_N_O_"]): row for row in ct2_rows}

    candidates, sources = build_candidate_pool(akd_rows, ct2_rows, args.modo, args.limite_grupo_valor)
    selected = cruzador.select_best_matches(candidates)
    selected_pairs = {(item.akd_recno, item.ct2_recno) for item in selected}
    selected_akd = {item.akd_recno for item in selected}
    selected_ct2 = {item.ct2_recno for item in selected}

    by_akd: dict[str, list[cruzador.CandidateMatch]] = defaultdict(list)
    by_ct2: dict[str, list[cruzador.CandidateMatch]] = defaultdict(list)
    for candidate in candidates:
        by_akd[candidate.akd_recno].append(candidate)
        by_ct2[candidate.ct2_recno].append(candidate)
    for items in by_akd.values():
        items.sort(key=score_sort_key, reverse=True)
    for items in by_ct2.values():
        items.sort(key=score_sort_key, reverse=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cruzador.log_step("Escrevendo candidatos detalhados")
    detailed_rows: list[dict[str, object]] = []
    signatures: dict[str, dict[str, int]] = {}
    origins: Counter[str] = Counter()
    hypotheses: Counter[str] = Counter()

    for candidate in sorted(candidates, key=score_sort_key, reverse=True):
        akd_row = akd_map[candidate.akd_recno]
        ct2_row = ct2_map[candidate.ct2_recno]
        pair = (candidate.akd_recno, candidate.ct2_recno)
        conflict = classify_conflict(candidate, selected_akd, selected_ct2, selected_pairs)
        signature = reason_signature(candidate.reasons)
        src = "|".join(sorted(sources.get(pair, {"desconhecido"})))
        item = signatures.setdefault(signature, {"candidatos": 0, "selecionados": 0})
        item["candidatos"] += 1
        item["selecionados"] += 1 if conflict == "selecionado" else 0
        for source in sources.get(pair, {"desconhecido"}):
            origins[source] += 1

        reason_set = set(signature.split("|")) if signature else set()
        source_set = sources.get(pair, set())
        if {"competencia", "ent05_conta", "cc"} <= reason_set and "xdoc" not in reason_set:
            hypotheses["competencia_conta_cc_sem_xdoc"] += 1
        if {"competencia", "tokens", "texto"} <= reason_set and "doc_extra" not in reason_set:
            hypotheses["texto_e_tokens_sem_documento_expresso"] += 1
        if "conta_valor" in source_set and "ent05_conta" not in reason_set:
            hypotheses["mesmo_valor_mesma_conta_sem_regra_explicita"] += 1
        if "cc_valor" in source_set and "cc" not in reason_set:
            hypotheses["mesmo_valor_mesmo_cc_sem_regra_explicita"] += 1
        if "valor_puro" in source_set and candidate.text_similarity >= 0.70:
            hypotheses["valor_puro_com_texto_semelhante"] += 1

        detailed_rows.append(
            {
                "akd_recno": candidate.akd_recno,
                "ct2_recno": candidate.ct2_recno,
                "selected": "sim" if conflict == "selecionado" else "nao",
                "conflict_type": conflict,
                "confidence": candidate.confidence,
                "score": candidate.score,
                "candidate_sources": src,
                "reason_signature": signature,
                "reasons": candidate.reasons,
                "token_overlap": candidate.token_overlap,
                "text_similarity": candidate.text_similarity,
                "akd_filial": cruzador.clean(akd_row.get("AKD_FILIAL", "")),
                "ct2_filial": cruzador.clean(ct2_row.get("CT2_FILIAL", "")),
                "akd_lote": cruzador.clean(akd_row.get("AKD_LOTE", "")),
                "ct2_lote": cruzador.clean(ct2_row.get("CT2_LOTE", "")),
                "akd_xdoc": cruzador.clean(akd_row.get("AKD_XDOC", "")),
                "ct2_xdoc": cruzador.clean(ct2_row.get("CT2_XDOC", "")),
                "ct2_at01cr": cruzador.clean(ct2_row.get("CT2_AT01CR", "")),
                "akd_xnumap": cruzador.clean(akd_row.get("AKD_XNUMAP", "")),
                "ct2_xdocum": cruzador.clean(ct2_row.get("CT2_XDOCUM", "")),
                "ct2_at04db": cruzador.clean(ct2_row.get("CT2_AT04DB", "")),
                "akd_chave": cruzador.clean(akd_row.get("AKD_CHAVE", "")),
                "ct2_key": cruzador.clean(ct2_row.get("CT2_KEY", "")),
                "akd_valor": f"{cruzador.normalize_decimal(akd_row.get('AKD_VALOR1', '')) or Decimal('0.00'):.2f}",
                "ct2_valor": f"{cruzador.normalize_decimal(ct2_row.get('CT2_VALOR', '')) or Decimal('0.00'):.2f}",
                "akd_data": cruzador.clean(akd_row.get("AKD_DATA", "")),
                "ct2_data": cruzador.derived_ct2_date(ct2_row),
                "akd_status": cruzador.clean(akd_row.get("AKD_STATUS", "")),
                "akd_classe": cruzador.clean(akd_row.get("AKD_CLASSE", "")),
                "akd_oper": cruzador.clean(akd_row.get("AKD_OPER", "")),
                "akd_tipo": cruzador.clean(akd_row.get("AKD_TIPO", "")),
                "akd_tpsald": cruzador.clean(akd_row.get("AKD_TPSALD", "")),
                "akd_codpla": cruzador.clean(akd_row.get("AKD_CODPLA", "")),
                "akd_uniorc": cruzador.clean(akd_row.get("AKD_UNIORC", "")),
                "akd_ent05": cruzador.clean(akd_row.get("AKD_ENT05", "")),
                "akd_ent06": cruzador.clean(akd_row.get("AKD_ENT06", "")),
                "akd_ent07": cruzador.clean(akd_row.get("AKD_ENT07", "")),
                "akd_xclsde": cruzador.clean(akd_row.get("AKD_XCLSDE", "")),
                "ct2_doc": cruzador.clean(ct2_row.get("CT2_DOC", "")),
                "ct2_linha": cruzador.clean(ct2_row.get("CT2_LINHA", "")),
                "ct2_debito": cruzador.clean(ct2_row.get("CT2_DEBITO", "")),
                "ct2_credito": cruzador.clean(ct2_row.get("CT2_CREDIT", "")),
                "ct2_dcd": cruzador.clean(ct2_row.get("CT2_DCD", "")),
                "ct2_dcc": cruzador.clean(ct2_row.get("CT2_DCC", "")),
                "ct2_hp": cruzador.clean(ct2_row.get("CT2_HP", "")),
                "akd_cc": cruzador.clean(akd_row.get("AKD_CC", "")),
                "ct2_ccd": cruzador.clean(ct2_row.get("CT2_CCD", "")),
                "ct2_ccc": cruzador.clean(ct2_row.get("CT2_CCC", "")),
                "akd_clvlr": cruzador.clean(akd_row.get("AKD_CLVLR", "")),
                "ct2_clvldb": cruzador.clean(ct2_row.get("CT2_CLVLDB", "")),
                "ct2_clvlcr": cruzador.clean(ct2_row.get("CT2_CLVLCR", "")),
                "akd_itctb": cruzador.clean(akd_row.get("AKD_ITCTB", "")),
                "ct2_itemd": cruzador.clean(ct2_row.get("CT2_ITEMD", "")),
                "ct2_itemc": cruzador.clean(ct2_row.get("CT2_ITEMC", "")),
                "ct2_ativde": cruzador.clean(ct2_row.get("CT2_ATIVDE", "")),
                "ct2_ativcr": cruzador.clean(ct2_row.get("CT2_ATIVCR", "")),
                "ct2_origem": cruzador.clean(ct2_row.get("CT2_ORIGEM", "")),
                "ct2_rotina": cruzador.clean(ct2_row.get("CT2_ROTINA", "")),
                "ct2_tpsald": cruzador.clean(ct2_row.get("CT2_TPSALD", "")),
                "ct2_codcli": cruzador.clean(ct2_row.get("CT2_CODCLI", "")),
                "ct2_codfor": cruzador.clean(ct2_row.get("CT2_CODFOR", "")),
                "ct2_xnumct": cruzador.clean(ct2_row.get("CT2_XNUMCT", "")),
                "akd_historico": cruzador.row_text_akd(akd_row),
                "ct2_historico": cruzador.row_text_ct2(ct2_row),
            }
        )

    write_csv(OUTPUT_DIR / "candidatos_match_detalhados.csv", detailed_rows)
    write_csv(
        OUTPUT_DIR / "assinaturas_evidencia.csv",
        [
            {
                "reason_signature": key,
                "candidatos": value["candidatos"],
                "selecionados": value["selecionados"],
                "taxa_selecao": round((value["selecionados"] / value["candidatos"]) * 100, 2) if value["candidatos"] else 0,
            }
            for key, value in sorted(signatures.items(), key=lambda item: item[1]["candidatos"], reverse=True)
        ],
    )
    write_csv(OUTPUT_DIR / "correlacao_campos_match.csv", correlation_rows(candidates, akd_map, ct2_map, selected_akd, selected_ct2, selected_pairs))
    write_csv(
        OUTPUT_DIR / "origens_candidatos.csv",
        [{"origem_candidato": key, "candidatos": value} for key, value in origins.most_common()],
    )
    write_csv(
        OUTPUT_DIR / "campos_prioritarios_akd.csv",
        build_field_profile_rows(akd_rows, AKD_PROFILE_FIELDS, "AKD"),
    )
    write_csv(
        OUTPUT_DIR / "campos_prioritarios_ct2.csv",
        build_field_profile_rows(ct2_rows, CT2_PROFILE_FIELDS, "CT2"),
    )
    write_csv(
        OUTPUT_DIR / "sobreposicao_campos_cruzados.csv",
        build_cross_field_overlap_rows(akd_rows, ct2_rows),
    )

    cruzador.log_step("Escrevendo top candidatos para registros sem match")
    akd_gap_rows: list[dict[str, object]] = []
    for recno, items in by_akd.items():
        if recno in selected_akd:
            continue
        akd_row = akd_map[recno]
        for rank, candidate in enumerate(items[: args.top], start=1):
            ct2_row = ct2_map[candidate.ct2_recno]
            akd_gap_rows.append(
                {
                    "akd_recno": recno,
                    "rank": rank,
                    "ct2_recno_candidato": candidate.ct2_recno,
                    "confidence": candidate.confidence,
                    "score": candidate.score,
                    "candidate_sources": "|".join(sorted(sources.get((candidate.akd_recno, candidate.ct2_recno), {"desconhecido"}))),
                    "reasons": candidate.reasons,
                    "akd_xdoc": cruzador.clean(akd_row.get("AKD_XDOC", "")),
                    "akd_xnumap": cruzador.clean(akd_row.get("AKD_XNUMAP", "")),
                    "akd_ent05": cruzador.clean(akd_row.get("AKD_ENT05", "")),
                    "akd_cc": cruzador.clean(akd_row.get("AKD_CC", "")),
                    "akd_clvlr": cruzador.clean(akd_row.get("AKD_CLVLR", "")),
                    "akd_itctb": cruzador.clean(akd_row.get("AKD_ITCTB", "")),
                    "ct2_xdoc": cruzador.clean(ct2_row.get("CT2_XDOC", "")),
                    "ct2_at01cr": cruzador.clean(ct2_row.get("CT2_AT01CR", "")),
                    "ct2_xdocum": cruzador.clean(ct2_row.get("CT2_XDOCUM", "")),
                    "ct2_at04db": cruzador.clean(ct2_row.get("CT2_AT04DB", "")),
                    "ct2_debito": cruzador.clean(ct2_row.get("CT2_DEBITO", "")),
                    "ct2_credito": cruzador.clean(ct2_row.get("CT2_CREDIT", "")),
                    "ct2_ccd": cruzador.clean(ct2_row.get("CT2_CCD", "")),
                    "ct2_ccc": cruzador.clean(ct2_row.get("CT2_CCC", "")),
                    "akd_historico": cruzador.row_text_akd(akd_row),
                    "ct2_historico": cruzador.row_text_ct2(ct2_row),
                }
            )
    write_csv(OUTPUT_DIR / "top_candidatos_akd_sem_match.csv", akd_gap_rows)

    ct2_gap_rows: list[dict[str, object]] = []
    for recno, items in by_ct2.items():
        if recno in selected_ct2:
            continue
        ct2_row = ct2_map[recno]
        for rank, candidate in enumerate(items[: args.top], start=1):
            akd_row = akd_map[candidate.akd_recno]
            ct2_gap_rows.append(
                {
                    "ct2_recno": recno,
                    "rank": rank,
                    "akd_recno_candidato": candidate.akd_recno,
                    "confidence": candidate.confidence,
                    "score": candidate.score,
                    "candidate_sources": "|".join(sorted(sources.get((candidate.akd_recno, candidate.ct2_recno), {"desconhecido"}))),
                    "reasons": candidate.reasons,
                    "ct2_xdoc": cruzador.clean(ct2_row.get("CT2_XDOC", "")),
                    "ct2_at01cr": cruzador.clean(ct2_row.get("CT2_AT01CR", "")),
                    "ct2_xdocum": cruzador.clean(ct2_row.get("CT2_XDOCUM", "")),
                    "ct2_at04db": cruzador.clean(ct2_row.get("CT2_AT04DB", "")),
                    "ct2_debito": cruzador.clean(ct2_row.get("CT2_DEBITO", "")),
                    "ct2_credito": cruzador.clean(ct2_row.get("CT2_CREDIT", "")),
                    "akd_xdoc": cruzador.clean(akd_row.get("AKD_XDOC", "")),
                    "akd_xnumap": cruzador.clean(akd_row.get("AKD_XNUMAP", "")),
                    "akd_ent05": cruzador.clean(akd_row.get("AKD_ENT05", "")),
                    "akd_cc": cruzador.clean(akd_row.get("AKD_CC", "")),
                    "akd_historico": cruzador.row_text_akd(akd_row),
                    "ct2_historico": cruzador.row_text_ct2(ct2_row),
                }
            )
    write_csv(OUTPUT_DIR / "top_candidatos_ct2_sem_match.csv", ct2_gap_rows)
    write_csv(
        OUTPUT_DIR / "hipoteses_novas_regras.csv",
        [{"hipotese_regra": key, "ocorrencias": value} for key, value in hypotheses.most_common()],
    )

    summary = {
        "arquivos": {"akd": akd_path.name, "ct2": ct2_path.name},
        "parametros": {"modo": args.modo, "top": args.top, "limite_grupo_valor": args.limite_grupo_valor},
        "totais": {
            "akd_pos_filtro": len(akd_rows),
            "ct2_pos_filtro": len(ct2_rows),
            "candidatos_match": len(candidates),
            "matches_selecionados": len(selected),
            "akd_sem_match_final": len(akd_rows) - len(selected_akd),
            "ct2_sem_match_final": len(ct2_rows) - len(selected_ct2),
        },
        "saida": {
            "candidatos_match_detalhados": "saida/descoberta_matches/candidatos_match_detalhados.csv",
            "assinaturas_evidencia": "saida/descoberta_matches/assinaturas_evidencia.csv",
            "correlacao_campos_match": "saida/descoberta_matches/correlacao_campos_match.csv",
            "origens_candidatos": "saida/descoberta_matches/origens_candidatos.csv",
            "campos_prioritarios_akd": "saida/descoberta_matches/campos_prioritarios_akd.csv",
            "campos_prioritarios_ct2": "saida/descoberta_matches/campos_prioritarios_ct2.csv",
            "sobreposicao_campos_cruzados": "saida/descoberta_matches/sobreposicao_campos_cruzados.csv",
            "top_candidatos_akd_sem_match": "saida/descoberta_matches/top_candidatos_akd_sem_match.csv",
            "top_candidatos_ct2_sem_match": "saida/descoberta_matches/top_candidatos_ct2_sem_match.csv",
            "hipoteses_novas_regras": "saida/descoberta_matches/hipoteses_novas_regras.csv",
        },
    }
    (OUTPUT_DIR / "resumo_match_profundo.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    cruzador.log_step(f"Analise profunda finalizada em {OUTPUT_DIR}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
