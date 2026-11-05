from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    qr_message: str | None = None


class SettingsOut(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    qr_message: str | None = None

    model_config = {"from_attributes": True}
