from pydantic import BaseModel, ConfigDict, Field


class IntegrationClientOut(BaseModel):
    """Стабильное представление клиента для внешних backend-сервисов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client: str = Field(validation_alias="name")
    name: str
    manager: str | None = None
    buyer_type: str | None = None
