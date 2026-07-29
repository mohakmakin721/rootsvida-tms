"""Shared column-type helpers.

`pg_enum` binds a Python `StrEnum` to its PostgreSQL ENUM type such that the
database stores the enum *value* (e.g. 'owner'), not the member *name* ('OWNER').
Without `values_callable`, SQLAlchemy persists the name — which would not match
our lowercase PG enum definitions and would fail on insert. Every enum column in
the schema goes through here so that behaviour is guaranteed and centralised.

`create_type=False` because the PG ENUM types are created explicitly in
migrations, not implicitly at table-create time.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM as PgEnum


def pg_enum(enum_cls: type[Enum], name: str) -> PgEnum:
    """A PostgreSQL ENUM column bound to `enum_cls`, storing member values."""
    return PgEnum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [member.value for member in e],
    )
