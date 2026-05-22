from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pymongo.database import Database

from app.modules.platform_admin.deps import get_platform_admin_db

router = APIRouter(prefix="/platform-admin/settings", tags=["Platform Admin - Settings (Live)"])

SETTINGS_DOC_ID = "platform_admin_settings"
LEGAL_DOCUMENT_KEYS = {"terms", "privacy"}
LEGAL_AUDIENCE_KEYS = {"apps", "business"}


def _first_admin(db: Database) -> dict:
    return db["platform_admins"].find_one(sort=[("created_at", 1)]) or {}


def _default_settings(admin: dict) -> dict:
    admin_name = str(admin.get("full_name") or admin.get("name") or "Platform Admin")
    admin_email = str(admin.get("email") or "admin@nuno.app")
    return {
        "title": "Admin Settings",
        "description": "Manage your Nuno platform configuration, users, and global parameters.",
        "general": {
            "platformName": "Nuno",
            "supportEmail": admin_email,
            "brandIdentity": {
                "logoData": "",
                "note": "Upload a logo for the admin panel and emails. Suggested size: 512x512px (PNG, SVG).",
                "cta": "Update Logo",
            },
        },
        "commission": {
            "globalRate": "12.50",
            "categoryRate": "18.00",
            "categoryLabel": "Luxury",
        },
        "legal": {
            "terms": "Terms of Service",
            "privacy": "Privacy Policy",
            "gdpr": "GDPR Compliance",
            "gdprStatus": "Active",
        },
        "legalContent": {
            "title": "Legal Content Editor",
            "lastUpdated": "January 15, 2025 at 2:30 PM",
            "documents": {
                "terms": "Terms of Service",
                "privacy": "Privacy Policy",
            },
            "audiences": {
                "apps": "Apps",
                "business": "Business",
            },
            "content": {
                "terms": {
                    "apps": "# Terms of Service\n\n### 1. Acceptance of Terms\nBy accessing and using Nuno, you agree to these Terms of Service and all applicable laws and regulations.",
                    "business": "# Business Terms of Service\n\n### 1. Commercial Eligibility\nBusiness accounts must provide accurate company information and maintain an active point of contact for compliance updates.",
                },
                "privacy": {
                    "apps": "# Privacy Policy\n\n### 1. Information We Collect\nWe collect account details, device information, and usage activity needed to operate, secure, and improve the app experience.",
                    "business": "# Business Privacy Policy\n\n### 1. Business Contact Data\nWe collect administrator details, team member information, and account-level configuration data required to deliver business services.",
                },
            },
        },
        "admin": {
            "name": admin_name,
            "email": admin_email,
            "avatar": str(admin.get("avatar") or admin.get("avatar_url") or ""),
        },
    }


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = {**base}
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _settings_response(db: Database) -> dict:
    admin = _first_admin(db)
    defaults = _default_settings(admin)
    stored = db["platform_admin_settings"].find_one({"_id": SETTINGS_DOC_ID}) or {}
    response = _deep_merge(defaults, {key: value for key, value in stored.items() if key != "_id"})
    response["admin"] = _deep_merge(defaults["admin"], response.get("admin") or {})
    return response


def _persist_settings(db: Database, payload: dict) -> None:
    document = {key: value for key, value in payload.items() if key not in {"_id", "created_at"}}
    db["platform_admin_settings"].update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": document, "$setOnInsert": {"created_at": datetime.now(UTC)}},
        upsert=True,
    )


def _format_timestamp(date: datetime) -> str:
    hour = date.strftime("%I").lstrip("0") or "0"
    return f"{date.strftime('%B')} {date.day}, {date.year} at {hour}:{date.strftime('%M')} {date.strftime('%p')}"


def _legal_content_response(db: Database) -> dict:
    settings = _settings_response(db)
    return settings.get("legalContent") or _default_settings(_first_admin(db))["legalContent"]


@router.get("/general")
def get_admin_settings_general(
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    return _settings_response(db)


@router.patch("/general")
def update_admin_settings_general(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    current = _settings_response(db)
    updated = _deep_merge(current, payload)
    updated["updated_at"] = datetime.now(UTC)
    _persist_settings(db, updated)
    return _settings_response(db)


@router.get("/legal-content")
def get_admin_legal_content(
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    return _legal_content_response(db)


@router.patch("/legal-content")
def update_admin_legal_content(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    document = str(payload.get("document") or "").strip().lower()
    audience = str(payload.get("audience") or "").strip().lower()
    content = payload.get("content")

    if document not in LEGAL_DOCUMENT_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid legal document.")
    if audience not in LEGAL_AUDIENCE_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid legal audience.")
    if not isinstance(content, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content is required.")

    current = _settings_response(db)
    legal_content = _deep_merge({}, current.get("legalContent") or {})
    legal_content["lastUpdated"] = _format_timestamp(datetime.now(UTC))
    legal_content.setdefault("content", {}).setdefault(document, {})[audience] = content
    current["legalContent"] = legal_content
    current["updated_at"] = datetime.now(UTC)

    _persist_settings(db, current)
    return _legal_content_response(db)


@router.get("/legal/{doc_type}")
def get_admin_legal_doc(
    doc_type: str,
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    normalized_doc_type = doc_type.strip().lower()
    if normalized_doc_type not in LEGAL_DOCUMENT_KEYS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found.")
    legal_content = _legal_content_response(db)
    return {
        "document": normalized_doc_type,
        "label": legal_content["documents"][normalized_doc_type],
        "audiences": legal_content["audiences"],
        "content": legal_content["content"][normalized_doc_type],
        "lastUpdated": legal_content["lastUpdated"],
    }


@router.patch("/legal/{doc_type}")
def update_admin_legal_doc(
    doc_type: str,
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    payload = {**payload, "document": doc_type}
    return update_admin_legal_content(payload=payload, db=db)
