from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import PurePosixPath


BLOCKED_PATHS = [
    ".env",
    ".env.*",
    "config/oracle.json",
    "config/*.local.json",
    "config/*secret*.json",
    "config/*credential*.json",
    "config/*password*.json",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.jks",
    "*.keystore",
    "wallet/*",
    "Wallet_*/*",
    "cwallet.sso",
    "ewallet.p12",
    "tnsnames.ora",
    "sqlnet.ora",
    "ojdbc.properties",
    "*.kdb",
    "*.sth",
]

ALLOWLIST_PATHS = {
    "config/oracle.example.json",
}

SECRET_PATTERNS = [
    re.compile(r'(?i)["\']?\b(password|passwd|senha|secret|token|api[_-]?key)\b["\']?\s*[:=]\s*["\'](?!SUA_|SEU_|CHANGE_ME|EXAMPLE|EXEMPLO)[^"\']{6,}["\']'),
    re.compile(r"(?i)[\"']?\b(user|usuario)\b[\"']?\s*[:=]\s*[\"'](?!SEU_|SUA_|EXAMPLE|EXEMPLO)[^\"']{4,}[\"']"),
    re.compile(r"(?i)[\"']?\bdsn\b[\"']?\s*[:=]\s*[\"'](?!servidor:1521/service_name)[^\"']+:[0-9]{2,5}/[^\"']+[\"']"),
    re.compile(r"(?i)\bsrv[a-z0-9._-]*:[0-9]{2,5}/[a-z0-9._-]+"),
    re.compile(r"(?i)-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
]

TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".csv",
    ".env",
    ".ini",
    ".json",
    ".md",
    ".ora",
    ".properties",
    ".py",
    ".sql",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout


def staged_files() -> list[str]:
    output = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name
    return any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def is_text_candidate(path: str) -> bool:
    lower = path.lower()
    suffix = PurePosixPath(lower).suffix
    return suffix in TEXT_EXTENSIONS or PurePosixPath(lower).name.startswith(".env")


def staged_content(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("latin-1", errors="ignore")


def main() -> int:
    problems: list[str] = []
    for path in staged_files():
        if path in ALLOWLIST_PATHS:
            continue
        if matches_any(path, BLOCKED_PATHS):
            problems.append(f"arquivo sensivel bloqueado: {path}")
            continue
        if not is_text_candidate(path):
            continue
        content = staged_content(path)
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                problems.append(f"possivel segredo em {path}: padrao {pattern.pattern}")
                break

    if not problems:
        return 0

    print("Commit bloqueado: possivel informacao sensivel detectada.", file=sys.stderr)
    for problem in problems:
        print(f"- {problem}", file=sys.stderr)
    print(
        "Remova o arquivo/valor do stage, use config/oracle.example.json apenas com placeholders "
        "e mantenha credenciais reais fora do Git.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
