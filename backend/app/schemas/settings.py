from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    qr_message: str | None = None
    industry: str | None = None
    team_size: int | None = None
    phone: str | None = None
    address: str | None = None
    brand_color: str | None = None
    manager_name: str | None = None
    staff_names: list[str] | None = None


class SettingsOut(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    qr_message: str | None = None
    industry: str | None = None
    team_size: int | None = None
    phone: str | None = None
    address: str | None = None
    brand_color: str | None = None
    manager_name: str | None = None
    staff_names: list[str] | None = None

    model_config = {"from_attributes": True}
