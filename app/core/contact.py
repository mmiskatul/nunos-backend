import re

from email_validator import EmailNotValidError, validate_email

PHONE_REGEX = re.compile(r"^\+?\d{8,15}$")
RELAXED_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def parse_email_or_phone(raw_value: str) -> tuple[str | None, str | None]:
    value = raw_value.strip()
    if not value:
        raise ValueError("Email or phone is required.")

    if "@" in value:
        try:
            email = validate_email(value, check_deliverability=False).normalized.lower()
            return email, None
        except EmailNotValidError:
            # Fallback to a relaxed format check to avoid rejecting valid real-world emails
            # because of strict normalization rules.
            if RELAXED_EMAIL_REGEX.fullmatch(value):
                return value.lower(), None
            raise ValueError("Invalid email address.")

    normalized_phone = re.sub(r"[\s().-]", "", value)
    if not PHONE_REGEX.fullmatch(normalized_phone):
        raise ValueError("Invalid phone number format.")
    return None, normalized_phone
