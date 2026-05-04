from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from validar_sql_somente_leitura import normalize_readonly_query


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "dados" / "brutos"
DEFAULT_ORACLE_CONFIG = ROOT / "config" / "oracle.json"
DEFAULT_TARGETS = {
    "akd": RAW_DIR / "DADOS-AKD010.csv",
    "ct2": RAW_DIR / "DADOS-CT2010.csv",
    "glossario": RAW_DIR / "GLOSSARIO-CONTAS.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Atualiza dados/brutos consultando AKD, CT2 e glossario no Oracle."
    )
    parser.add_argument(
        "--oracle-config",
        default=str(DEFAULT_ORACLE_CONFIG),
        help="Arquivo JSON com credenciais e caminhos das queries Oracle.",
    )
    parser.add_argument(
        "--somente",
        choices=sorted(DEFAULT_TARGETS),
        nargs="+",
        default=list(DEFAULT_TARGETS),
        help="Bases a atualizar. Padrao: akd ct2 glossario.",
    )
    parser.add_argument(
        "--sem-backup",
        action="store_true",
        help="Substitui os CSVs sem criar backup dos arquivos atuais.",
    )
    parser.add_argument(
        "--fetch-size",
        type=int,
        default=5000,
        help="Quantidade de linhas por lote lido do Oracle. Padrao: 5000.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return str(value).strip()


def resolve_repo_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Configuracao Oracle nao encontrada: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuracao Oracle invalida: esperado um objeto JSON.")
    return config


def load_query(value: object) -> str:
    text = clean(value)
    if not text:
        raise ValueError("Query Oracle vazia.")
    if text.lstrip().upper().startswith("SELECT"):
        return normalize_readonly_query(text)
    return normalize_readonly_query(resolve_repo_path(text).read_text(encoding="utf-8"))


def oracle_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, Decimal):
        return format(value, "f")
    try:
        return str(value).strip()
    except TypeError:
        try:
            return bytes(value).hex()
        except TypeError:
            return repr(value)


def backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{path.stem}.{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def export_query(
    connection: object,
    name: str,
    query: str,
    target: Path,
    fetch_size: int,
    create_backup: bool,
) -> int:
    print(f"[etapa] Consultando Oracle: {name}", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    with connection.cursor() as cursor:
        cursor.arraysize = fetch_size
        cursor.execute(query)
        columns = [str(col[0]).upper() for col in cursor.description]

        with NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8-sig",
            dir=target.parent,
            prefix=f".{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)

            total = 0
            while True:
                rows = cursor.fetchmany(fetch_size)
                if not rows:
                    break
                for row in rows:
                    writer.writerow([oracle_text(value) for value in row])
                total += len(rows)
                print(f"\r[etapa] {name}: {total} linhas", end="", flush=True)
            print()

    backup_path = backup_existing(target) if create_backup else None
    temp_path.replace(target)
    if backup_path is not None:
        print(f"[etapa] Backup criado: {backup_path.relative_to(ROOT)}", flush=True)
    print(f"[etapa] CSV atualizado: {target.relative_to(ROOT)} ({total} linhas)", flush=True)
    return total


def main() -> None:
    args = parse_args()
    config_path = resolve_repo_path(args.oracle_config)
    config = load_config(config_path)

    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError(
            "Dependencia Oracle ausente. Instale com: python -m pip install -r requirements.txt"
        ) from exc

    queries = config.get("queries")
    if not isinstance(queries, dict):
        raise ValueError("Configure o objeto 'queries' em config/oracle.json.")

    user = clean(config.get("user", ""))
    password = clean(config.get("password", ""))
    dsn = clean(config.get("dsn", ""))
    if not user or not password or not dsn:
        raise ValueError("Preencha user, password e dsn em config/oracle.json.")

    missing = [name for name in args.somente if name not in queries]
    if missing:
        raise ValueError(f"Queries nao configuradas: {', '.join(missing)}")

    print("[etapa] Abrindo conexao Oracle", flush=True)
    totals: dict[str, int] = {}
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection:
        for name in args.somente:
            totals[name] = export_query(
                connection=connection,
                name=name,
                query=load_query(queries[name]),
                target=DEFAULT_TARGETS[name],
                fetch_size=max(args.fetch_size, 1),
                create_backup=not args.sem_backup,
            )

    print("[etapa] Atualizacao finalizada", flush=True)
    print(json.dumps(totals, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
