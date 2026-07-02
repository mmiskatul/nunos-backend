from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.api.deps import get_cloudinary_uploader
from app.core.account_lookup import find_existing_email_sync
from app.core.security import hash_password, verify_password
from app.modules.platform_admin.deps_auth import get_current_platform_admin
from app.modules.platform_admin.deps import get_platform_admin_db
from app.modules.vendor.repositories_portal import VendorPortalRepository
from app.providers.cloudinary_uploader import CloudinaryUploader

router = APIRouter(prefix="/platform-admin/settings", tags=["Platform Admin - Settings (Live)"])

SETTINGS_DOC_ID = "platform_admin_settings"
LEGAL_DOCUMENT_KEYS = {"terms", "privacy"}
LEGAL_AUDIENCE_KEYS = {"apps", "business"}


class PlatformUpdateBroadcastRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=5, max_length=4000)
    action_label: str | None = Field(default=None, max_length=80)
    vendor_ids: list[str] = Field(default_factory=list)


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


def _admin_profile_response(db: Database, admin_id: str) -> dict:
    admin = db["platform_admins"].find_one({"_id": ObjectId(admin_id)}) or {}
    return {
        "admin": {
            "name": admin.get("full_name") or admin.get("name") or "Platform Admin",
            "email": admin.get("email") or "admin@nuno.app",
            "avatar": admin.get("avatar") or admin.get("avatar_url") or "",
        }
    }


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


@router.get("/commission")
def get_admin_settings_commission(
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    return {
        "commission": _settings_response(db).get("commission") or {},
    }


@router.patch("/commission")
def update_admin_settings_commission(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    commission = payload.get("commission") if isinstance(payload.get("commission"), dict) else payload
    current = _settings_response(db)
    current["commission"] = _deep_merge(current.get("commission") or {}, commission if isinstance(commission, dict) else {})
    current["updated_at"] = datetime.now(UTC)
    _persist_settings(db, current)
    return {
        "commission": _settings_response(db).get("commission") or {},
    }


@router.get("/profile")
def get_admin_settings_profile(
    db: Database = Depends(get_platform_admin_db),
    current_admin: dict = Depends(get_current_platform_admin),
) -> dict:
    return _admin_profile_response(db, str(current_admin["id"]))


@router.patch("/profile")
def update_admin_settings_profile(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
    current_admin: dict = Depends(get_current_platform_admin),
) -> dict:
    admin_payload = payload.get("admin") if isinstance(payload.get("admin"), dict) else payload
    name = str(admin_payload.get("name") or current_admin.get("full_name") or current_admin.get("name") or "").strip()
    email = str(admin_payload.get("email") or current_admin.get("email") or "").strip().lower()
    avatar = str(admin_payload.get("avatar") or admin_payload.get("avatar_url") or current_admin.get("avatar") or current_admin.get("avatar_url") or "").strip()

    if not name:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin name is required.")
    if not email:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin email is required.")

    existing = find_existing_email_sync(
        db,
        email,
        exclude_collection="platform_admins",
        exclude_id=str(current_admin.get("id")),
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already in use by another account.",
        )

    db["platform_admins"].update_one(
        {"_id": ObjectId(str(current_admin["id"]))},
        {
            "$set": {
                "full_name": name,
                "email": email,
                "avatar": avatar,
                "avatar_url": avatar,
                "updated_at": datetime.now(UTC),
            }
        },
    )

    current = _settings_response(db)
    current["admin"] = _deep_merge(current.get("admin") or {}, {"name": name, "email": email, "avatar": avatar})
    current["general"] = _deep_merge(
        current.get("general") or {},
        {"supportEmail": current.get("general", {}).get("supportEmail") or email},
    )
    current["updated_at"] = datetime.now(UTC)
    _persist_settings(db, current)
    return _admin_profile_response(db, str(current_admin["id"]))


@router.post("/profile/avatar")
async def upload_admin_profile_avatar(
    file: UploadFile = File(..., description="Profile avatar image to upload"),
    db: Database = Depends(get_platform_admin_db),
    current_admin: dict = Depends(get_current_platform_admin),
    uploader: CloudinaryUploader = Depends(get_cloudinary_uploader),
) -> dict:
    secure_url = await uploader.upload_image(
        file,
        folder_suffix=f"platform-admin/{current_admin['id']}/profile",
    )

    db["platform_admins"].update_one(
        {"_id": ObjectId(str(current_admin["id"]))},
        {
            "$set": {
                "avatar": secure_url,
                "avatar_url": secure_url,
                "updated_at": datetime.now(UTC),
            }
        },
    )

    current = _settings_response(db)
    current["admin"] = _deep_merge(current.get("admin") or {}, {"avatar": secure_url})
    current["updated_at"] = datetime.now(UTC)
    _persist_settings(db, current)
    return {"avatar": secure_url, "profile_image_url": secure_url}


@router.patch("/password")
def update_admin_settings_password(
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
    current_admin: dict = Depends(get_current_platform_admin),
) -> dict:
    current_password = str(payload.get("currentPassword") or payload.get("current_password") or "").strip()
    new_password = str(payload.get("newPassword") or payload.get("new_password") or "").strip()
    confirm_password = str(payload.get("confirmPassword") or payload.get("confirm_password") or "").strip()

    if not current_password or not new_password or not confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All password fields are required.")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 8 characters.")
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password and confirmation do not match.")

    admin_doc = db["platform_admins"].find_one({"_id": ObjectId(str(current_admin["id"]))})
    if not admin_doc or not verify_password(current_password, str(admin_doc.get("password_hash") or "")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    db["platform_admins"].update_one(
        {"_id": admin_doc["_id"]},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": datetime.now(UTC)}},
    )
    return {"message": "Password updated successfully."}


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


@router.post("/platform-updates")
def broadcast_platform_update(
    payload: PlatformUpdateBroadcastRequest,
    db: Database = Depends(get_platform_admin_db),
    current_admin: dict = Depends(get_current_platform_admin),
) -> dict:
    repo = VendorPortalRepository(db)
    inserted_count = repo.broadcast_platform_update(
        payload.title,
        payload.message,
        action_label=payload.action_label,
        metadata={
            "source": "platform_admin",
            "broadcast_by": str(current_admin.get("id") or ""),
        },
        vendor_ids=payload.vendor_ids or None,
    )
    return {
        "message": "Platform update broadcast created.",
        "inserted_count": inserted_count,
        "target_scope": "selected_vendors" if payload.vendor_ids else "all_opted_in_vendors",
    }
