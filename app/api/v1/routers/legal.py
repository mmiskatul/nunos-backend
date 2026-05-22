from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.modules.platform_admin.deps import get_platform_admin_db

router = APIRouter(prefix="/legal", tags=["Legal"])

LEGAL_DOCUMENT_KEYS = {"terms", "privacy"}


def _default_legal_content() -> dict:
    return {
        "documents": {
            "terms": "Terms of Service",
            "privacy": "Privacy Policy",
        },
        "content": {
            "terms": {
                "apps": "# Terms of Service\n\n### 1. Acceptance of Terms\nBy accessing and using Nuno, you agree to these Terms of Service and all applicable laws and regulations.",
            },
            "privacy": {
                "apps": "# Privacy Policy\n\n### 1. Information We Collect\nWe collect account details, device information, and usage activity needed to operate, secure, and improve the app experience.",
            },
        },
        "lastUpdated": "January 15, 2025 at 2:30 PM",
    }


def _legal_content_response(db: Database) -> dict:
    settings = db["platform_admin_settings"].find_one({"_id": "platform_admin_settings"}) or {}
    legal_content = settings.get("legalContent")
    if isinstance(legal_content, dict):
        return legal_content
    return _default_legal_content()


@router.get("/{doc_type}")
def get_legal_document(
    doc_type: str,
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    normalized_doc_type = doc_type.strip().lower()
    if normalized_doc_type not in LEGAL_DOCUMENT_KEYS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found.")

    legal_content = _legal_content_response(db)
    return {
        "document": normalized_doc_type,
        "title": legal_content["documents"][normalized_doc_type],
        "content": legal_content["content"][normalized_doc_type]["apps"],
        "lastUpdated": legal_content.get("lastUpdated", ""),
    }
