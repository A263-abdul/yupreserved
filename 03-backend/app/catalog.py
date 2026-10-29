"""
Named-query catalog.

Reads the annotated .sql files of 02-database, where every entry starts with
a header block:

    -- @name: joins.inner
    -- @title: Inner (equi) join — hotels with their city and state
    -- @topic: Joins › Inner / equi join
    -- @algebra: π … (hotels ⋈ cities ⋈ states)
    -- @setup: SET LOCAL enable_hashjoin = off      (optional)
    -- @explain: Keeps only pairs of rows whose join columns are equal …
    SELECT …;

Three collections use this format:
    queries   02-database/queries/*.sql             read-only named queries
    why       02-database/demos/why_not.sql         statements that must fail
    plans     02-database/demos/query_processing.sql  EXPLAIN demonstrations

The same parser is used by the API and by the CLI (04-cli/yup.py).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from .config import PROJECT_ROOT

_HEADER = re.compile(r"^--\s*@(\w+):\s*(.*)$")

SOURCES = {
    "queries": sorted((PROJECT_ROOT / "02-database" / "queries").glob("*.sql")),
    "why": [PROJECT_ROOT / "02-database" / "demos" / "why_not.sql"],
    "plans": [PROJECT_ROOT / "02-database" / "demos" / "query_processing.sql"],
}


@dataclass(frozen=True)
class NamedQuery:
    name: str
    title: str
    topic: str
    algebra: str
    explain: str
    setup: str
    sql: str
    file: str

    def as_dict(self) -> dict:
        return asdict(self)


def _parse_file(path: Path) -> list[NamedQuery]:
    queries, meta, body = [], None, []

    def flush():
        if meta:
            sql = "\n".join(body).strip().rstrip(";").strip()
            queries.append(NamedQuery(
                name=meta["name"], title=meta.get("title", meta["name"]),
                topic=meta.get("topic", ""), algebra=meta.get("algebra", ""),
                explain=meta.get("explain", ""), setup=meta.get("setup", ""),
                sql=sql, file=path.name))

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADER.match(line)
        if m:
            key, value = m.groups()
            if key == "name":
                flush()
                meta, body = {"name": value.strip()}, []
            elif meta is not None:
                meta[key] = value.strip()
        elif meta is not None and not line.startswith("-- ════"):
            body.append(line)
    flush()
    return queries


@lru_cache(maxsize=None)
def load(collection: str = "queries") -> dict[str, NamedQuery]:
    out: dict[str, NamedQuery] = {}
    for path in SOURCES[collection]:
        for q in _parse_file(path):
            out[q.name] = q
    return out
