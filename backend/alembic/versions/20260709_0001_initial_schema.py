"""initial normalized schema

Revision ID: 20260709_0001
Revises:
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260709_0001"
down_revision = None
branch_labels = None
depends_on = None

client_status = postgresql.ENUM("active", "archived", "out_of_stock", name="clientstatus", create_type=False)
phone_type = postgresql.ENUM("sms", "common", name="phonetype", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        client_status.create(bind, checkfirst=True)
        phone_type.create(bind, checkfirst=True)
    op.create_table("imports", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_name", sa.String(255), nullable=False), sa.Column("imported_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("rows_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"), if_not_exists=True)
    op.create_index("ix_imports_file_name", "imports", ["file_name"], if_not_exists=True); op.create_index("ix_imports_imported_at", "imports", ["imported_at"], if_not_exists=True)
    op.create_table("clients", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("company", sa.String(255)), sa.Column("price_type", sa.String(120)), sa.Column("manager", sa.String(120)), sa.Column("birth_date", sa.Date()), sa.Column("director", sa.String(255)), sa.Column("contact_person", sa.String(255)), sa.Column("status", client_status if bind.dialect.name == "postgresql" else sa.Enum("active", "archived", "out_of_stock", name="clientstatus"), nullable=False, server_default="active"), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), sa.Column("first_import_id", sa.Integer(), sa.ForeignKey("imports.id")), sa.Column("last_import_id", sa.Integer(), sa.ForeignKey("imports.id")), if_not_exists=True)
    for col in ["name", "company", "price_type", "manager", "birth_date", "status", "updated_at", "last_import_id"]: op.create_index(f"ix_clients_{col}", "clients", [col], if_not_exists=True)
    op.create_index("ix_clients_name_company", "clients", ["name", "company"], if_not_exists=True)
    op.create_table("phones", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False), sa.Column("phone", sa.String(32), nullable=False), sa.Column("type", phone_type if bind.dialect.name == "postgresql" else sa.Enum("sms", "common", name="phonetype"), nullable=False), sa.UniqueConstraint("client_id", "phone", "type", name="uq_client_phone_type"), if_not_exists=True)
    op.create_index("ix_phones_client_id", "phones", ["client_id"], if_not_exists=True); op.create_index("ix_phones_phone", "phones", ["phone"], if_not_exists=True); op.create_index("ix_phones_type", "phones", ["type"], if_not_exists=True)
    op.create_table("emails", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False), sa.Column("email", sa.String(255), nullable=False), sa.UniqueConstraint("client_id", "email", name="uq_client_email"), if_not_exists=True)
    op.create_index("ix_emails_client_id", "emails", ["client_id"], if_not_exists=True); op.create_index("ix_emails_email", "emails", ["email"], if_not_exists=True)
    op.create_table("trade_places", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False), sa.Column("place", sa.String(255), nullable=False), if_not_exists=True)
    op.create_index("ix_trade_places_client_id", "trade_places", ["client_id"], if_not_exists=True); op.create_index("ix_trade_places_place", "trade_places", ["place"], if_not_exists=True)
    op.create_table("import_issues", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("import_id", sa.Integer(), sa.ForeignKey("imports.id", ondelete="CASCADE"), nullable=False), sa.Column("row_number", sa.Integer()), sa.Column("level", sa.String(24), nullable=False), sa.Column("message", sa.Text(), nullable=False), if_not_exists=True)
    op.create_index("ix_import_issues_import_id", "import_issues", ["import_id"], if_not_exists=True); op.create_index("ix_import_issues_level", "import_issues", ["level"], if_not_exists=True)
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL")), sa.Column("action", sa.String(80), nullable=False), sa.Column("payload", sa.Text()), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False), if_not_exists=True)
    op.create_index("ix_audit_logs_client_id", "audit_logs", ["client_id"], if_not_exists=True); op.create_index("ix_audit_logs_action", "audit_logs", ["action"], if_not_exists=True); op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], if_not_exists=True)


def downgrade() -> None:
    for table in ["audit_logs", "import_issues", "trade_places", "emails", "phones", "clients", "imports"]:
        op.drop_table(table, if_exists=True)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        phone_type.drop(bind, checkfirst=True)
        client_status.drop(bind, checkfirst=True)
