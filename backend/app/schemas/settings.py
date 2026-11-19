import re

from pydantic import BaseModel, field_validator


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


class SettingsUpdate(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    # country calling code (digits only, e.g. "234") used to complete phone
    # numbers customers were saved with in local format ("0801 234 5678")
    default_country_code: str | None = None
    qr_message: str | None = None
    industry: str | None = None
    team_size: int | None = None
    phone: str | None = None
    address: str | None = None
    brand_color: str | None = None
    manager_name: str | None = None
    staff_names: list[str] | None = None
    default_currency: str | None = None
    support_email: str | None = None
    sender_handle: str | None = None

    @field_validator("whatsapp_number")
    @classmethod
    def _check_whatsapp_number(cls, value: str | None) -> str | None:
        # empty clears it; otherwise it must be something wa.me can open:
        # international format, 8-15 digits, no leading 0
        if value is None or not value.strip():
            return None
        digits = _digits(value)
        if not 8 <= len(digits) <= 15 or digits.startswith("0"):
            raise ValueError("WhatsApp number must include the country code, e.g. +234 801 234 5678.")
        return value.strip()

    @field_validator("default_country_code")
    @classmethod
    def _check_country_code(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = _digits(value)
        if not 1 <= len(digits) <= 3 or digits.startswith("0"):
            raise ValueError("Country code must be 1-3 digits, e.g. 234.")
        return digits


class SettingsOut(BaseModel):
    biz_name: str | None = None
    whatsapp_number: str | None = None
    default_country_code: str | None = None
    qr_message: str | None = None
    industry: str | None = None
    team_size: int | None = None
    phone: str | None = None
    address: str | None = None
    brand_color: str | None = None
    manager_name: str | None = None
    staff_names: list[str] | None = None
    default_currency: str | None = None
    support_email: str | None = None
    sender_handle: str | None = None
    # read-only: the verified domain sender_handle sits on, so the UI can
    # show the full address without hardcoding it
    sender_domain: str | None = None

    model_config = {"from_attributes": True}
