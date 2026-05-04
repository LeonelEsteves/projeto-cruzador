from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import gerar_relatorio_conciliacao_akd_ct2 as cruzador


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "dados" / "brutos"
OUTPUT_DIR = ROOT / "saida" / "descoberta_matches" / "chaves_candidatas"

MIN_KEY_LENGTH = 2
DEFAULT_TOP_COMPOSITES = 30


@dataclass
class ColumnProfile:
    side: str
    column: str
    rows: int
    filled: int
    distinct: int
    duplicate_values: int
    max_frequency: int
    fill_rate: float
    uniqueness_rate: float
    example_values: str


@dataclass
class CandidateKey:
    rank: int
    akd_key: str
    ct2_key: str
    kind: str
    overlap_values: int
    matched_akd_rows: int
    matched_ct2_rows: int
    akd_filled: int
    ct2_filled: int
    akd_distinct: int
    ct2_distinct: int
    akd_coverage_pct: float
    ct2_coverage_pct: float
    overlap_distinct_pct: float
    one_to_one_values: int
    one_to_one_pct: float
    specificity_pct: float
    max_pair_rows: int
    ambiguity_penalty: float
    score: float
    interpretation: str
    sample_values: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descobre chaves candidatas e insights de cruzamento entre AKD e CT2."
    )
    parser.add_argument("--akd", help="Caminho da base AKD. Default: dados/brutos/DADOS-AKD010.")
    parser.add_argument("--ct2", help="Caminho da base CT2. Default: dados/brutos/DADOS-CT2010.")
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Quantidade de melhores candidatos exportados em cada camada.",
    )
    parser.add_argument(
        "--top-composites",
        type=int,
        default=DEFAULT_TOP_COMPOSITES,
        help="Quantidade de candidatos simples usados para gerar chaves compostas.",
    )
    parser.add_argument(
        "--sem-filtros",
        action="store_true",
        help="Analisa as bases brutas sem os filtros de negocio do relatorio.",
    )
    return parser.parse_args()


def log_step(message: str, started_at: float | None = None) -> float:
    if started_at is None:
        print(f"[etapa] {message}")
    else:
        print(f"[etapa] {message} ({perf_counter() - started_at:.2f}s)")
    return perf_counter()


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round((float(part) / float(total)) * 100, 4)


def normalize_key(value: object) -> str:
    text = cruzador.clean(value).upper()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.strip()


def normalize_compact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_key(value))


def normalize_decimal_text(value: object) -> str:
    amount = cruzador.normalize_decimal(value)
    if amount is None:
        return ""
    return f"{amount:.2f}"


def normalize_date_text(value: object) -> str:
    text = normalize_compact(value)
    if len(text) == 8 and text.isdigit():
        return text
    return ""


def normalize_month_text(value: object) -> str:
    date = normalize_date_text(value)
    if not date:
        return ""
    return f"{date[:4]}{date[4:6]}"


def is_usable_key(value: str) -> bool:
    if len(value) < MIN_KEY_LENGTH:
        return False
    if value in {"0", "00", "000", "0000", "1", "2"}:
        return False
    return True


def read_source(path_arg: str | None, stem: str) -> tuple[Path, list[dict[str, str]]]:
    path = Path(path_arg).expanduser() if path_arg else cruzador.resolve_source_path(RAW_DIR, stem)
    if not path.is_absolute():
        path = ROOT / path
    return path, cruzador.read_rows(path)


def derived_rows(rows: list[dict[str, str]], side: str) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        if side == "AKD":
            item["DER_VALOR"] = normalize_decimal_text(row.get("AKD_VALOR1", ""))
            item["DER_DATA"] = normalize_date_text(row.get("AKD_DATA", ""))
            item["DER_MES"] = normalize_month_text(row.get("AKD_DATA", ""))
            item["DER_HIST_DOCS"] = "|".join(sorted(cruzador.extract_doc_keys(row.get("AKD_HIST", ""))))
            item["DER_CHAVE_TOKENS"] = "|".join(sorted(cruzador.extract_structured_key_tokens(row.get("AKD_CHAVE", ""))))
            item["DER_TEXTO_BUSCA"] = " ".join(
                normalize_key(row.get(name, ""))
                for name in ("AKD_XDOC", "AKD_XNUMAP", "AKD_CHAVE", "AKD_HIST", "AKD_XHISTO")
            )
        else:
            item["DER_VALOR"] = normalize_decimal_text(row.get("CT2_VALOR", ""))
            item["DER_DATA"] = normalize_date_text(row.get("CT2_DATA", ""))
            item["DER_MES"] = normalize_month_text(row.get("CT2_DATA", ""))
            item["DER_HIST_DOCS"] = "|".join(sorted(cruzador.extract_doc_keys(row.get("CT2_HIST", ""))))
            item["DER_CHAVE_TOKENS"] = "|".join(sorted(cruzador.extract_structured_key_tokens(row.get("CT2_KEY", ""))))
            item["DER_TEXTO_BUSCA"] = " ".join(
                normalize_key(row.get(name, ""))
                for name in ("CT2_XDOC", "CT2_XDOCUM", "CT2_AT01CR", "CT2_AT04DB", "CT2_KEY", "CT2_HIST")
            )
        enriched.append(item)
    return enriched


def explode_value(value: object) -> list[str]:
    text = normalize_key(value)
    if not text:
        return []
    if "|" in text:
        return [part for part in text.split("|") if is_usable_key(part)]
    compact = normalize_compact(text)
    return [compact] if is_usable_key(compact) else []


def column_value_counts(rows: list[dict[str, str]], column: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for value in explode_value(row.get(column, "")):
            counts[value] += 1
    return counts


def composite_value_counts(rows: list[dict[str, str]], columns: tuple[str, ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        parts: list[str] = []
        for column in columns:
            values = explode_value(row.get(column, ""))
            if len(values) != 1:
                parts = []
                break
            parts.append(values[0])
        if parts:
            counts["||".join(parts)] += 1
    return counts


def profile_columns(rows: list[dict[str, str]], side: str) -> list[ColumnProfile]:
    profiles: list[ColumnProfile] = []
    if not rows:
        return profiles
    for column in rows[0]:
        values = column_value_counts(rows, column)
        filled = sum(values.values())
        distinct = len(values)
        examples = ", ".join(list(values.keys())[:5])
        profiles.append(
            ColumnProfile(
                side=side,
                column=column,
                rows=len(rows),
                filled=filled,
                distinct=distinct,
                duplicate_values=sum(1 for count in values.values() if count > 1),
                max_frequency=max(values.values()) if values else 0,
                fill_rate=pct(filled, len(rows)),
                uniqueness_rate=pct(distinct, filled),
                example_values=examples,
            )
        )
    return profiles


def interpret_candidate(candidate: CandidateKey) -> str:
    if candidate.one_to_one_pct >= 80 and candidate.akd_coverage_pct >= 20 and candidate.ct2_coverage_pct >= 20:
        return "forte para chave relacional 1x1"
    if candidate.specificity_pct >= 25 and candidate.overlap_distinct_pct >= 50 and (
        candidate.akd_coverage_pct >= 20 or candidate.ct2_coverage_pct >= 20
    ):
        return "forte para bloqueio seletivo"
    if candidate.akd_coverage_pct >= 50 or candidate.ct2_coverage_pct >= 50:
        return "boa ancora de bloqueio"
    if candidate.overlap_values >= 20 and candidate.one_to_one_pct < 40:
        return "indicio util, mas com muita ambiguidade"
    if candidate.overlap_values > 0:
        return "sinal complementar"
    return "sem evidencia relevante"


def build_candidate(
    rank: int,
    akd_key: str,
    ct2_key: str,
    kind: str,
    akd_counts: Counter[str],
    ct2_counts: Counter[str],
) -> CandidateKey:
    overlap = set(akd_counts) & set(ct2_counts)
    matched_akd = sum(akd_counts[value] for value in overlap)
    matched_ct2 = sum(ct2_counts[value] for value in overlap)
    one_to_one = sum(1 for value in overlap if akd_counts[value] == 1 and ct2_counts[value] == 1)
    max_pair_rows = max((akd_counts[value] * ct2_counts[value] for value in overlap), default=0)
    akd_filled = sum(akd_counts.values())
    ct2_filled = sum(ct2_counts.values())
    coverage_akd = pct(matched_akd, akd_filled)
    coverage_ct2 = pct(matched_ct2, ct2_filled)
    overlap_distinct = pct(len(overlap), min(len(akd_counts), len(ct2_counts)))
    one_to_one_pct = pct(one_to_one, len(overlap))
    specificity = min(pct(len(akd_counts), akd_filled), pct(len(ct2_counts), ct2_filled))
    ambiguity_penalty = min(30.0, pct(max_pair_rows, max(matched_akd + matched_ct2, 1)) * 3)
    score = round(
        (((coverage_akd + coverage_ct2) / 2) * 0.30)
        + (overlap_distinct * 0.20)
        + (one_to_one_pct * 0.20)
        + (specificity * 0.30)
        - ambiguity_penalty,
        4,
    )
    candidate = CandidateKey(
        rank=rank,
        akd_key=akd_key,
        ct2_key=ct2_key,
        kind=kind,
        overlap_values=len(overlap),
        matched_akd_rows=matched_akd,
        matched_ct2_rows=matched_ct2,
        akd_filled=akd_filled,
        ct2_filled=ct2_filled,
        akd_distinct=len(akd_counts),
        ct2_distinct=len(ct2_counts),
        akd_coverage_pct=coverage_akd,
        ct2_coverage_pct=coverage_ct2,
        overlap_distinct_pct=overlap_distinct,
        one_to_one_values=one_to_one,
        one_to_one_pct=one_to_one_pct,
        specificity_pct=specificity,
        max_pair_rows=max_pair_rows,
        ambiguity_penalty=round(ambiguity_penalty, 4),
        score=score,
        interpretation="",
        sample_values=", ".join(list(sorted(overlap))[:10]),
    )
    candidate.interpretation = interpret_candidate(candidate)
    return candidate


def rank_candidates(candidates: list[CandidateKey]) -> list[CandidateKey]:
    candidates.sort(
        key=lambda item: (
            item.score,
            item.one_to_one_pct,
            item.akd_coverage_pct + item.ct2_coverage_pct,
            item.overlap_values,
        ),
        reverse=True,
    )
    for index, candidate in enumerate(candidates, start=1):
        candidate.rank = index
    return candidates


def analyze_single_columns(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
) -> list[CandidateKey]:
    akd_columns = list(akd_rows[0]) if akd_rows else []
    ct2_columns = list(ct2_rows[0]) if ct2_rows else []
    akd_counts = {column: column_value_counts(akd_rows, column) for column in akd_columns}
    ct2_counts = {column: column_value_counts(ct2_rows, column) for column in ct2_columns}

    candidates: list[CandidateKey] = []
    for akd_column, left_counts in akd_counts.items():
        if not left_counts:
            continue
        for ct2_column, right_counts in ct2_counts.items():
            if not right_counts:
                continue
            if not (set(left_counts) & set(right_counts)):
                continue
            candidates.append(build_candidate(0, akd_column, ct2_column, "coluna_simples", left_counts, right_counts))
    return rank_candidates(candidates)


def useful_composite_parts(candidates: list[CandidateKey], limit: int) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if candidate.kind != "coluna_simples":
            continue
        if candidate.score < 5:
            continue
        pair = (candidate.akd_key, candidate.ct2_key)
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(pair)
        if len(pairs) >= limit:
            break
    defaults = [
        ("DER_VALOR", "DER_VALOR"),
        ("DER_MES", "DER_MES"),
        ("AKD_CC", "CT2_CCD"),
        ("AKD_CC", "CT2_CCC"),
        ("AKD_ENT05", "CT2_DEBITO"),
        ("AKD_ENT05", "CT2_CREDIT"),
    ]
    for pair in defaults:
        if pair not in seen:
            pairs.append(pair)
    return pairs


def columns_equivalent(rows: list[dict[str, str]], first: str, second: str) -> bool:
    if first == second:
        return True
    comparable = 0
    equal = 0
    for row in rows:
        first_values = explode_value(row.get(first, ""))
        second_values = explode_value(row.get(second, ""))
        if len(first_values) != 1 or len(second_values) != 1:
            continue
        comparable += 1
        if first_values[0] == second_values[0]:
            equal += 1
    return comparable > 0 and equal == comparable


def analyze_composites(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
    single_candidates: list[CandidateKey],
    limit: int,
) -> list[CandidateKey]:
    parts = useful_composite_parts(single_candidates, limit)
    candidates: list[CandidateKey] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for index, first in enumerate(parts):
        for second in parts[index + 1 :]:
            akd_cols = (first[0], second[0])
            ct2_cols = (first[1], second[1])
            key = (akd_cols, ct2_cols)
            if key in seen or len(set(akd_cols)) < len(akd_cols) or len(set(ct2_cols)) < len(ct2_cols):
                continue
            if columns_equivalent(akd_rows, akd_cols[0], akd_cols[1]):
                continue
            if columns_equivalent(ct2_rows, ct2_cols[0], ct2_cols[1]):
                continue
            seen.add(key)
            left_counts = composite_value_counts(akd_rows, akd_cols)
            right_counts = composite_value_counts(ct2_rows, ct2_cols)
            if not left_counts or not right_counts or not (set(left_counts) & set(right_counts)):
                continue
            candidates.append(
                build_candidate(
                    0,
                    "+".join(akd_cols),
                    "+".join(ct2_cols),
                    "chave_composta",
                    left_counts,
                    right_counts,
                )
            )
    return rank_candidates(candidates)


def analyze_token_crossings(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
) -> list[CandidateKey]:
    pairs = [
        ("DER_HIST_DOCS", "DER_HIST_DOCS"),
        ("DER_CHAVE_TOKENS", "DER_CHAVE_TOKENS"),
        ("AKD_XDOC", "CT2_XDOC"),
        ("AKD_XDOC", "CT2_AT01CR"),
        ("AKD_XNUMAP", "CT2_XDOCUM"),
        ("AKD_CHAVE", "CT2_KEY"),
    ]
    candidates: list[CandidateKey] = []
    for akd_column, ct2_column in pairs:
        left_counts = column_value_counts(akd_rows, akd_column)
        right_counts = column_value_counts(ct2_rows, ct2_column)
        if left_counts and right_counts and set(left_counts) & set(right_counts):
            candidates.append(build_candidate(0, akd_column, ct2_column, "token_documental", left_counts, right_counts))
    return rank_candidates(candidates)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["vazio"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def top_rows(items: list[CandidateKey], limit: int) -> list[dict[str, object]]:
    return [asdict(item) for item in items[:limit]]


def build_insights(
    akd_rows: list[dict[str, str]],
    ct2_rows: list[dict[str, str]],
    single: list[CandidateKey],
    composite: list[CandidateKey],
    tokens: list[CandidateKey],
    profiles: list[ColumnProfile],
    args: argparse.Namespace,
) -> dict[str, object]:
    best_single = single[0] if single else None
    best_composite = composite[0] if composite else None
    best_token = tokens[0] if tokens else None
    high_fill_profiles = sorted(
        profiles,
        key=lambda item: (item.fill_rate, item.uniqueness_rate),
        reverse=True,
    )[:20]
    return {
        "parametros": {
            "top": args.top,
            "top_composites": args.top_composites,
            "sem_filtros": args.sem_filtros,
        },
        "totais": {
            "akd_linhas_analisadas": len(akd_rows),
            "ct2_linhas_analisadas": len(ct2_rows),
            "candidatos_coluna_simples": len(single),
            "candidatos_chave_composta": len(composite),
            "candidatos_token_documental": len(tokens),
        },
        "melhores": {
            "coluna_simples": asdict(best_single) if best_single else None,
            "chave_composta": asdict(best_composite) if best_composite else None,
            "token_documental": asdict(best_token) if best_token else None,
        },
        "colunas_mais_preenchidas_e_distintas": [asdict(item) for item in high_fill_profiles],
        "arquivos": {
            "perfil_colunas": "saida/descoberta_matches/chaves_candidatas/perfil_colunas.csv",
            "candidatos_coluna_simples": "saida/descoberta_matches/chaves_candidatas/candidatos_coluna_simples.csv",
            "candidatos_chaves_compostas": "saida/descoberta_matches/chaves_candidatas/candidatos_chaves_compostas.csv",
            "candidatos_tokens_documentais": "saida/descoberta_matches/chaves_candidatas/candidatos_tokens_documentais.csv",
            "resumo_json": "saida/descoberta_matches/chaves_candidatas/resumo_chaves_candidatas.json",
            "insights_markdown": "saida/descoberta_matches/chaves_candidatas/INSIGHTS_CHAVES_CANDIDATAS.md",
        },
    }


def render_markdown(summary: dict[str, object], single: list[CandidateKey], composite: list[CandidateKey], tokens: list[CandidateKey]) -> str:
    totals = summary["totais"]

    def table(items: list[CandidateKey], limit: int = 10) -> str:
        lines = [
            "| Rank | AKD | CT2 | Tipo | Cobertura AKD | Cobertura CT2 | 1x1 | Score | Leitura |",
            "|---:|---|---|---|---:|---:|---:|---:|---|",
        ]
        for item in items[:limit]:
            lines.append(
                f"| {item.rank} | `{item.akd_key}` | `{item.ct2_key}` | {item.kind} | "
                f"{item.akd_coverage_pct:.2f}% | {item.ct2_coverage_pct:.2f}% | "
                f"{item.one_to_one_pct:.2f}% | {item.score:.2f} | {item.interpretation} |"
            )
        return "\n".join(lines)

    recommendations: list[str] = []
    if composite:
        recommendations.append(
            f"- Priorizar a chave composta `{composite[0].akd_key}` x `{composite[0].ct2_key}` como candidata de bloqueio/relacionamento."
        )
    if single:
        recommendations.append(
            f"- Usar `{single[0].akd_key}` x `{single[0].ct2_key}` como melhor sinal simples inicial."
        )
    if tokens:
        recommendations.append(
            f"- Usar `{tokens[0].akd_key}` x `{tokens[0].ct2_key}` como trilha documental complementar."
        )
    recommendations.append(
        "- Campos com boa cobertura, mas baixa taxa 1x1, devem entrar como bloqueio ou reforco de score, nao como chave unica."
    )

    return f"""# Insights de Chaves Candidatas AKD x CT2

## Escopo

- AKD analisado: `{totals["akd_linhas_analisadas"]}` linhas.
- CT2 analisado: `{totals["ct2_linhas_analisadas"]}` linhas.
- Candidatos simples encontrados: `{totals["candidatos_coluna_simples"]}`.
- Candidatos compostos encontrados: `{totals["candidatos_chave_composta"]}`.
- Candidatos documentais/tokenizados encontrados: `{totals["candidatos_token_documental"]}`.

## Melhores Chaves Simples

{table(single)}

## Melhores Chaves Compostas

{table(composite)}

## Melhores Sinais Documentais

{table(tokens)}

## Recomendacoes

{chr(10).join(recommendations)}

## Leitura dos Indicadores

- `Cobertura AKD` e `Cobertura CT2` mostram quanto dos valores preenchidos de cada lado encontra correspondencia no outro lado.
- `1x1` mede quantos valores sobrepostos aparecem uma unica vez em cada base, indicando menor ambiguidade.
- `Score` combina cobertura, sobreposicao distinta, taxa 1x1, especificidade/cardinalidade e penalizacao por valores muito repetidos.
- Uma chave candidata boa para relacionamento final costuma ter cobertura relevante e alta taxa `1x1`.
- Uma chave com cobertura alta e `1x1` baixo ainda pode ser excelente para reduzir o universo de busca antes de aplicar valor, data e similaridade textual.
"""


def main() -> None:
    args = parse_args()
    start = log_step("Inicio da descoberta de chaves candidatas")

    akd_path, akd_raw = read_source(args.akd, "DADOS-AKD010")
    ct2_path, ct2_raw = read_source(args.ct2, "DADOS-CT2010")
    start = log_step(f"Bases lidas: {akd_path.name} e {ct2_path.name}", start)

    if args.sem_filtros:
        akd_rows = akd_raw
        ct2_rows = ct2_raw
        start = log_step("Usando bases brutas, sem filtros de negocio", start)
    else:
        akd_rows = cruzador.filter_akd_rows(akd_raw)
        ct2_rows = cruzador.filter_ct2_rows(ct2_raw)
        start = log_step("Filtros de negocio aplicados: AKD_TPSALD e CT2_MOEDLC/CT2_DC", start)

    akd_rows = derived_rows(akd_rows, "AKD")
    ct2_rows = derived_rows(ct2_rows, "CT2")
    start = log_step("Colunas derivadas criadas: valor, data, mes, tokens documentais e texto de busca", start)

    profiles = profile_columns(akd_rows, "AKD") + profile_columns(ct2_rows, "CT2")
    write_csv(OUTPUT_DIR / "perfil_colunas.csv", [asdict(item) for item in profiles])
    start = log_step("Perfil das colunas exportado", start)

    single = analyze_single_columns(akd_rows, ct2_rows)
    write_csv(OUTPUT_DIR / "candidatos_coluna_simples.csv", top_rows(single, args.top))
    start = log_step("Varredura exata de todas as colunas concluida", start)

    composite = analyze_composites(akd_rows, ct2_rows, single, args.top_composites)
    write_csv(OUTPUT_DIR / "candidatos_chaves_compostas.csv", top_rows(composite, args.top))
    start = log_step("Chaves compostas candidatas geradas a partir dos melhores sinais", start)

    tokens = analyze_token_crossings(akd_rows, ct2_rows)
    write_csv(OUTPUT_DIR / "candidatos_tokens_documentais.csv", top_rows(tokens, args.top))
    start = log_step("Sinais documentais e tokens estruturados analisados", start)

    summary = build_insights(akd_rows, ct2_rows, single, composite, tokens, profiles, args)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "resumo_chaves_candidatas.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "INSIGHTS_CHAVES_CANDIDATAS.md").write_text(
        render_markdown(summary, single, composite, tokens),
        encoding="utf-8",
    )
    log_step(f"Analise finalizada em {OUTPUT_DIR}", start)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
