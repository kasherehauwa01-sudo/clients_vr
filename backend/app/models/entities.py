from datetime import datetime, date
from enum import StrEnum
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class ClientStatus(StrEnum):
    active = "active"
    archived = "archived"
    out_of_stock = "out_of_stock"


class PhoneType(StrEnum):
    sms = "sms"
    common = "common"


class ImportStatus(StrEnum):
    completed = "completed"
    failed = "failed"


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    company: Mapped[str | None] = mapped_column(String(255), index=True)
    price_type: Mapped[str | None] = mapped_column(String(120), index=True)
    manager: Mapped[str | None] = mapped_column(String(120), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, index=True)
    director: Mapped[str | None] = mapped_column(String(255))
    contact_person: Mapped[str | None] = mapped_column(String(255))
    raw_common_phones: Mapped[str | None] = mapped_column(Text)
    raw_sms_phones: Mapped[str | None] = mapped_column(Text)
    client_source: Mapped[str | None] = mapped_column(String(255), index=True)
    last_purchase_date: Mapped[date | None] = mapped_column(Date, index=True)
    buyer_type: Mapped[str | None] = mapped_column(String(120), index=True)
    counterparty_type: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus), default=ClientStatus.active, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)
    first_import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id"))
    last_import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id"), index=True)
    phones = relationship("Phone", cascade="all, delete-orphan", back_populates="client")
    emails = relationship("Email", cascade="all, delete-orphan", back_populates="client")
    trade_places = relationship("TradePlace", cascade="all, delete-orphan", back_populates="client")


class Phone(Base):
    __tablename__ = "phones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[PhoneType] = mapped_column(Enum(PhoneType), index=True)
    client = relationship("Client", back_populates="phones")
    __table_args__ = (UniqueConstraint("client_id", "phone", "type", name="uq_client_phone_type"),)


class Email(Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    client = relationship("Client", back_populates="emails")
    __table_args__ = (UniqueConstraint("client_id", "email", name="uq_client_email"),)


class TradePlace(Base):
    __tablename__ = "trade_places"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    place: Mapped[str] = mapped_column(String(255), index=True)
    client = relationship("Client", back_populates="trade_places")


class Import(Base):
    __tablename__ = "imports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    rows_count: Mapped[int] = mapped_column(Integer, default=0)
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)


class ImportIssue(Base):
    __tablename__ = "import_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(24), index=True)
    message: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


Index("ix_clients_name_company", Client.name, Client.company)
