"""SQLite compatibility shims for PostgreSQL-specific SQLAlchemy types."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.compiler import compiles


_REGISTERED = False


def register_sqlite_pg_compat() -> None:
    """Map PG-only types to SQLite-friendly DDL for unit-test create_all."""
    global _REGISTERED
    if _REGISTERED:
        return

    @compiles(JSONB, "sqlite")
    def _jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001
        return "TEXT"

    @compiles(UUID, "sqlite")
    def _uuid_sqlite(type_, compiler, **kw):  # noqa: ANN001
        return "CHAR(36)"

    @compiles(ARRAY, "sqlite")
    def _array_sqlite(type_, compiler, **kw):  # noqa: ANN001
        return "TEXT"

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR

        @compiles(TSVECTOR, "sqlite")
        def _tsvector_sqlite(type_, compiler, **kw):  # noqa: ANN001
            return "TEXT"
    except ImportError:
        pass

    _REGISTERED = True
