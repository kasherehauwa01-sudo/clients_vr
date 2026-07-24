from datetime import date, datetime
from pydantic import BaseModel, EmailStr


class PhoneOut(BaseModel):
    phone: str
    type: str


class ClientListItem(BaseModel):
    id: int
    name: str
    company: str | None = None
    manager: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    trade_place: str | None = None
    birth_date: date | None = None
    last_import_at: datetime | None = None
    status: str


class ClientDetail(ClientListItem):
    price_type: str | None = None
    director: str | None = None
    contact_person: str | None = None
    raw_common_phones: str | None = None
    raw_sms_phones: str | None = None
    client_source: str | None = None
    last_purchase_date: date | None = None
    buyer_type: str | None = None
    counterparty_type: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    first_import_at: datetime | None = None
    last_import_file: str | None = None
    phones: list[PhoneOut] = []
    emails: list[str] = []
    trade_places: list[str] = []


class PagedClients(BaseModel):
    items: list[ClientListItem]
    total: int
    page: int
    page_size: int


class BulkUpdate(BaseModel):
    ids: list[int]
    manager: str | None = None
    price_type: str | None = None
    status: str | None = None
