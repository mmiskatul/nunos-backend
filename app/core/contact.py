import re

from email_validator import EmailNotValidError, validate_email

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


def parse_email_or_phone(raw_value: str) -> tuple[str | None, str | None]:
    value = raw_value.strip()
    if not value:
        raise ValueError("Email or phone is required.")

    if "@" in value:
        try:
            email = validate_email(value, check_deliverability=False).normalized.lower()
        except EmailNotValidError as exc:
            raise ValueError("Invalid email address.") from exc
        return email, None

    normalized_phone = re.sub(r"[\s().-]", "", value)
    if not PHONE_REGEX.fullmatch(normalized_phone):
        raise ValueError("Invalid phone number format.")
    return None, normalized_phone

