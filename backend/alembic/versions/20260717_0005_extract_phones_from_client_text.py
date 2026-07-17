"""extract phone numbers from client text fields

Revision ID: 20260717_0005
Revises: 20260717_0004
Create Date: 2026-07-17
"""
import re
from alembic import op
import sqlalchemy as sa

revision = "20260717_0005"
down_revision = "20260717_0004"
branch_labels = None
depends_on = None

PHONE_RE = re.compile(r"(?<!\d)(?:\+?[78](?:[\s().-]*\d){10}|(?:\d[\s().-]*){9}\d)(?!\d)")


def _extract(value: str | None) -> set[str]:
    result: set[str] = set()
    for match in PHONE_RE.finditer(value or ""):
        digits = "".join(character for character in match.group() if character.isdigit())
        if len(digits) == 10:
            digits = "7" + digits
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) == 11 and digits.startswith("7"):
            result.add(f"+{digits}")
    return result


def upgrade() -> None:
    bind = op.get_bind()
    clients = sa.table(
        "clients",
        sa.column("id", sa.Integer),
        sa.column("director", sa.String),
        sa.column("contact_person", sa.String),
    )
    trade_places = sa.table(
        "trade_places",
        sa.column("client_id", sa.Integer),
        sa.column("place", sa.String),
    )
    phones = sa.table(
        "phones",
        sa.column("client_id", sa.Integer),
        sa.column("phone", sa.String),
        sa.column("type", sa.String),
    )
    existing = set(bind.execute(sa.select(phones.c.client_id, phones.c.phone)).all())
    found: dict[int, set[str]] = {}
    for row in bind.execute(sa.select(clients.c.id, clients.c.director, clients.c.contact_person)):
        found[row.id] = _extract(row.director) | _extract(row.contact_person)
    for row in bind.execute(sa.select(trade_places.c.client_id, trade_places.c.place)):
        found.setdefault(row.client_id, set()).update(_extract(row.place))
    additions = [
        {"client_id": client_id, "phone": phone, "type": "common"}
        for client_id, values in found.items()
        for phone in values
        if (client_id, phone) not in existing
    ]
    if additions:
        bind.execute(sa.insert(phones), additions)


def downgrade() -> None:
    # Невозможно отличить найденные номера от ранее импортированных без потери данных.
    pass
