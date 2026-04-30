from __future__ import annotations

import re


BLOCKED_SQL_PATTERNS = {
    "ALTER": r"\bALTER\b",
    "BEGIN": r"\bBEGIN\b",
    "CALL": r"\bCALL\b",
    "COMMIT": r"\bCOMMIT\b",
    "CREATE": r"\bCREATE\b",
    "DECLARE": r"\bDECLARE\b",
    "DELETE": r"\bDELETE\b",
    "DROP": r"\bDROP\b",
    "EXEC": r"\bEXEC(?:UTE)?\b",
    "FOR UPDATE": r"\bFOR\s+UPDATE\b",
    "GRANT": r"\bGRANT\b",
    "INSERT": r"\bINSERT\b",
    "LOCK": r"\bLOCK\b",
    "MERGE": r"\bMERGE\b",
    "PURGE": r"\bPURGE\b",
    "RENAME": r"\bRENAME\b",
    "REVOKE": r"\bREVOKE\b",
    "ROLLBACK": r"\bROLLBACK\b",
    "TRUNCATE": r"\bTRUNCATE\b",
    "UPDATE": r"\bUPDATE\b",
}


def mask_comments_and_strings(sql: str) -> str:
    result: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        current = sql[index]
        next_char = sql[index + 1] if index + 1 < length else ""

        if current == "-" and next_char == "-":
            end = sql.find("\n", index + 2)
            if end == -1:
                result.append(" " * (length - index))
                break
            result.append(" " * (end - index))
            index = end
            continue

        if current == "/" and next_char == "*":
            end = sql.find("*/", index + 2)
            if end == -1:
                result.append(" " * (length - index))
                break
            result.append(" " * (end + 2 - index))
            index = end + 2
            continue

        if current == "'":
            result.append(" ")
            index += 1
            while index < length:
                if sql[index] == "'":
                    result.append(" ")
                    index += 1
                    if index < length and sql[index] == "'":
                        result.append(" ")
                        index += 1
                        continue
                    break
                result.append(" ")
                index += 1
            continue

        result.append(current)
        index += 1

    return "".join(result)


def normalize_readonly_query(sql: str) -> str:
    query = sql.strip()
    masked = mask_comments_and_strings(query)
    masked_stripped = masked.strip()

    if not masked_stripped:
        raise ValueError("Query Oracle vazia.")

    without_trailing_semicolon = masked_stripped.removesuffix(";").strip()
    if ";" in without_trailing_semicolon:
        raise ValueError("Query Oracle bloqueada: multiplos comandos nao sao permitidos.")

    if not re.match(r"^SELECT\b", without_trailing_semicolon, flags=re.IGNORECASE):
        raise ValueError("Query Oracle bloqueada: somente comandos SELECT sao permitidos.")

    for label, pattern in BLOCKED_SQL_PATTERNS.items():
        if re.search(pattern, without_trailing_semicolon, flags=re.IGNORECASE):
            raise ValueError(f"Query Oracle bloqueada: comando proibido detectado ({label}).")

    return query.removesuffix(";").strip()
