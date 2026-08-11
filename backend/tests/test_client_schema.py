from app.schemas.client import ClientListItem


def test_client_list_item_accepts_multiple_emails_for_registry():
    item = ClientListItem(
        id=1,
        name="Тестовый клиент",
        email="first@example.com\nsecond@example.com",
        status="active",
    )

    assert item.email == "first@example.com\nsecond@example.com"
