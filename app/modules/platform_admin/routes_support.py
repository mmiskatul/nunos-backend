from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.modules.platform_admin.deps import get_platform_admin_db

router = APIRouter(prefix="/platform-admin/support/tickets", tags=["Platform Admin - Support (Live)"])


def _ensure_indexes(db: Database) -> None:
    collection = db["support_tickets"]
    collection.create_index([("user_id", 1), ("created_at", -1)])
    collection.create_index([("status", 1), ("updated_at", -1)])
    collection.create_index([("ticket_code", 1)], unique=True)


def _title_case(value: str, fallback: str) -> str:
    normalized = str(value or "").strip().replace("_", " ").lower()
    if not normalized:
        return fallback
    return " ".join(part.capitalize() for part in normalized.split())


def _resolve_ticket_query(ticket_id: str) -> dict:
    try:
        return {"_id": ObjectId(ticket_id)}
    except (InvalidId, ValueError):
        return {"ticket_code": ticket_id}


def _serialize_message(message: dict) -> dict:
    created_at = message.get("created_at")
    return {
        "sender": "agent" if str(message.get("sender_role") or "").lower() == "agent" else "user",
        "text": str(message.get("text") or ""),
        "time": created_at.isoformat() if isinstance(created_at, datetime) else None,
        "name": str(message.get("sender_name") or ""),
    }


def _serialize_ticket(document: dict | None) -> dict | None:
    if not document:
        return None
    messages = document.get("messages") if isinstance(document.get("messages"), list) else []
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    return {
        "id": str(document.get("ticket_code") or document.get("_id") or ""),
        "ticket_key": str(document.get("_id") or ""),
        "ticket_code": str(document.get("ticket_code") or ""),
        "user_name": str(document.get("user_name") or "Unknown User"),
        "user_role": "User",
        "avatar": str(document.get("user_avatar") or ""),
        "type": _title_case(str(document.get("issue_type") or ""), "Account"),
        "subject": str(document.get("subject") or ""),
        "status": _title_case(str(document.get("status") or ""), "Open"),
        "priority": _title_case(str(document.get("priority") or ""), "Medium"),
        "opened_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
        "issue_details": str(document.get("description") or ""),
        "conversation": [_serialize_message(item) for item in messages],
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
    }


def _summary_cards(tickets: list[dict]) -> list[dict]:
    total = len(tickets)
    open_count = sum(1 for ticket in tickets if ticket.get("status") == "Open")
    in_progress = sum(1 for ticket in tickets if ticket.get("status") == "In Progress")
    resolved = sum(1 for ticket in tickets if ticket.get("status") == "Resolved")
    return [
        {"label": "TOTAL TICKETS", "value": str(total), "note": "All support requests", "tone": "text-[#1f3d8f]"},
        {"label": "IN PROGRESS", "value": str(in_progress), "note": "Needs follow-up", "tone": "text-[#b45309]"},
        {"label": "RESOLVED", "value": str(resolved), "note": "Closed tickets", "tone": "text-[#15803d]"},
        {"label": "OPEN", "value": str(open_count), "note": "Awaiting response", "tone": "text-[#1d4ed8]"},
    ]


def _normalize_status(raw_status: str) -> str:
    normalized = str(raw_status or "").strip().lower().replace(" ", "_")
    if normalized not in {"open", "in_progress", "resolved"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    return normalized


@router.get("")
def list_support_tickets(
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    priority_filter: str | None = Query(default=None, alias="priority"),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    _ensure_indexes(db)
    query: dict = {}
    if search:
        query["$or"] = [
            {"ticket_code": {"$regex": search, "$options": "i"}},
            {"user_name": {"$regex": search, "$options": "i"}},
            {"subject": {"$regex": search, "$options": "i"}},
        ]
    if status_filter:
        query["status"] = _normalize_status(status_filter)
    if priority_filter:
        query["priority"] = str(priority_filter).strip().lower()

    rows = list(db["support_tickets"].find(query).sort("updated_at", -1).skip(skip).limit(limit))
    tickets = [_serialize_ticket(row) for row in rows if row]
    return {
        "summary_cards": _summary_cards(tickets),
        "tickets": tickets,
        "total": int(db["support_tickets"].count_documents(query)),
    }


@router.get("/{ticket_id}")
def get_support_ticket(
    ticket_id: str,
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    _ensure_indexes(db)
    ticket = db["support_tickets"].find_one(_resolve_ticket_query(ticket_id))
    serialized = _serialize_ticket(ticket)
    if not serialized:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found.")
    return serialized


@router.post("/{ticket_id}/messages")
def reply_support_ticket(
    ticket_id: str,
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    _ensure_indexes(db)
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required.")

    now = datetime.now(UTC)
    update = {
        "$push": {
            "messages": {
                "sender_role": "agent",
                "sender_name": str(payload.get("name") or "Support Agent"),
                "text": message,
                "created_at": now,
            }
        },
        "$set": {"updated_at": now},
    }

    ticket = db["support_tickets"].find_one(_resolve_ticket_query(ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found.")
    if str(ticket.get("status") or "") == "open":
        update["$set"]["status"] = "in_progress"

    db["support_tickets"].update_one({"_id": ticket["_id"]}, update)
    updated = db["support_tickets"].find_one({"_id": ticket["_id"]})
    return _serialize_ticket(updated) or {}


@router.patch("/{ticket_id}/status")
def update_support_ticket_status(
    ticket_id: str,
    payload: dict = Body(...),
    db: Database = Depends(get_platform_admin_db),
) -> dict:
    _ensure_indexes(db)
    normalized_status = _normalize_status(str(payload.get("status") or ""))
    ticket = db["support_tickets"].find_one(_resolve_ticket_query(ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found.")

    now = datetime.now(UTC)
    db["support_tickets"].update_one(
        {"_id": ticket["_id"]},
        {
            "$set": {"status": normalized_status, "updated_at": now},
            "$push": {
                "messages": {
                    "sender_role": "agent",
                    "sender_name": "System",
                    "text": f'Ticket status updated to "{_title_case(normalized_status, "Open")}".',
                    "created_at": now,
                }
            },
        },
    )
    updated = db["support_tickets"].find_one({"_id": ticket["_id"]})
    return _serialize_ticket(updated) or {}
