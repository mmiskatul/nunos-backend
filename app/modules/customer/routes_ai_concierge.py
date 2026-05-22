from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user_id, get_db
from app.core.responses import envelope
from app.core.security import decode_token
from app.repositories.base import oid
from app.repositories.booking_repository import BookingRepository
from app.repositories.listing_repository import ListingRepository
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/customer/ai-concierge", tags=["Customer - AI Concierge"])

THREAD_COLLECTION = "ai_concierge_threads"
MEMORY_COLLECTION = "ai_concierge_memory"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _serialize_message(document: dict) -> dict:
    created_at = document.get("created_at")
    return {
        "id": str(document.get("_id") or document.get("id") or ""),
        "session_id": str(document.get("session_id") or ""),
        "role": str(document.get("role") or "assistant"),
        "content": str(document.get("content") or ""),
        "metadata": document.get("metadata") if isinstance(document.get("metadata"), dict) else {},
        "created_at": created_at.isoformat() if created_at else None,
    }


def _serialize_session(document: dict) -> dict:
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    return {
        "id": str(document.get("_id") or ""),
        "title": str(document.get("title") or "AI Concierge"),
        "preview": str(document.get("last_message_preview") or ""),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _profile_snapshot(user: dict) -> dict:
    return {
        "name": str(user.get("full_name") or ""),
        "email": str(user.get("email") or ""),
        "phone": str(user.get("phone") or ""),
        "date_of_birth": str(user.get("date_of_birth") or ""),
        "points_balance": int(user.get("points_balance") or 0),
        "location_enabled": bool(user.get("location_enabled") or False),
        "profile_image_url": str(user.get("profile_image_url") or ""),
    }


def _infer_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics: list[str] = []
    keyword_groups = {
        "restaurant": ["restaurant", "food", "dinner", "lunch", "brunch", "eat", "cafe"],
        "hotel": ["hotel", "stay", "room", "suite", "night"],
        "spa": ["spa", "massage", "relax", "wellness"],
        "event": ["event", "concert", "festival", "show", "party"],
        "booking": ["book", "booking", "reservation", "reserve"],
        "profile": ["profile", "details", "email", "phone", "points", "account"],
    }
    for topic, keywords in keyword_groups.items():
        if any(keyword in lowered for keyword in keywords):
            topics.append(topic)
    return topics


def _memory_summary(user: dict, bookings: list[dict], topics: list[str]) -> dict:
    upcoming_count = 0
    now = _utcnow()
    for booking in bookings:
        scheduled_at = booking.get("scheduled_at")
        if isinstance(scheduled_at, datetime) and scheduled_at >= now:
            upcoming_count += 1
    return {
        "profile": _profile_snapshot(user),
        "topics": topics,
        "booking_count": len(bookings),
        "upcoming_booking_count": upcoming_count,
    }


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[THREAD_COLLECTION].create_index([("user_id", 1), ("updated_at", -1)])
    await db[MEMORY_COLLECTION].create_index([("session_id", 1)], unique=True)
    await db[MEMORY_COLLECTION].create_index([("user_id", 1), ("updated_at", -1)])


async def _load_user_context(db: AsyncIOMotorDatabase, user_id: str) -> tuple[dict, list[dict]]:
    user_repo = UserRepository(db)
    booking_repo = BookingRepository(db)
    user = await user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    bookings = await booking_repo.list_for_user(user_id)
    return user, bookings


async def _find_session(db: AsyncIOMotorDatabase, session_id: str, user_id: str) -> dict | None:
    try:
        return await db[THREAD_COLLECTION].find_one({"_id": oid(session_id), "user_id": ObjectId(user_id)})
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI session not found.")


async def _create_session_document(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    user, bookings = await _load_user_context(db, user_id)
    memory = _memory_summary(user, bookings, [])
    now = _utcnow()
    session = {
        "user_id": ObjectId(user_id),
        "title": "AI Concierge",
        "last_message_preview": "Hello! I'm your AI concierge.",
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db[THREAD_COLLECTION].insert_one(session)
    session["_id"] = result.inserted_id
    welcome_message = {
        "_id": ObjectId(),
        "session_id": result.inserted_id,
        "role": "assistant",
        "content": "Hello! I'm your personal AI concierge. I can help with restaurants, hotels, spas, events, bookings, and your account details.",
        "metadata": {"kind": "welcome"},
        "created_at": now,
    }
    await db[THREAD_COLLECTION].update_one(
        {"_id": result.inserted_id},
        {
            "$push": {"messages": welcome_message},
            "$set": {"last_message_preview": welcome_message["content"][:180]},
        },
    )
    await db[MEMORY_COLLECTION].update_one(
        {"session_id": result.inserted_id, "user_id": ObjectId(user_id)},
        {
            "$set": {
                "session_id": result.inserted_id,
                "user_id": ObjectId(user_id),
                "memory": memory,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return session


async def _find_memory(db: AsyncIOMotorDatabase, session_id: ObjectId, user_id: str) -> dict:
    memory = await db[MEMORY_COLLECTION].find_one({"session_id": session_id, "user_id": ObjectId(user_id)})
    return memory or {}


async def _top_recommendations(db: AsyncIOMotorDatabase, topics: list[str]) -> list[dict]:
    listing_repo = ListingRepository(db)
    ordered_types: list[str] = []
    for topic in topics:
        if topic in {"restaurant", "hotel", "spa", "event"} and topic not in ordered_types:
            ordered_types.append(topic)
    if not ordered_types:
        ordered_types = ["restaurant", "hotel", "spa"]

    recommendations: list[dict] = []
    for listing_type in ordered_types[:2]:
        for item in await listing_repo.top_by_type(listing_type, 2, near_metro=False, offers=None):
            recommendations.append(
                {
                    "name": str(item.get("name") or ""),
                    "type": str(item.get("type") or listing_type),
                    "rating": float(((item.get("rating_summary") or {}).get("average")) or 0),
                    "metro": str(item.get("near_metro_station") or "Unknown"),
                }
            )
    return recommendations[:4]


def _next_booking_line(bookings: list[dict]) -> str | None:
    future = [item for item in bookings if isinstance(item.get("scheduled_at"), datetime) and item["scheduled_at"] >= _utcnow()]
    future.sort(key=lambda item: item["scheduled_at"])
    if not future:
        return None
    booking = future[0]
    when = booking["scheduled_at"].strftime("%b %d, %Y %I:%M %p")
    booking_type = str(booking.get("booking_type") or booking.get("status") or "booking").replace("_", " ")
    return f"Your next {booking_type} is scheduled for {when}."


def _compose_reply(message: str, user: dict, bookings: list[dict], memory: dict, recommendations: list[dict]) -> str:
    lowered = message.lower()
    profile = _profile_snapshot(user)
    known_topics = memory.get("topics") if isinstance(memory.get("topics"), list) else []
    user_name = profile["name"] or "there"

    if any(keyword in lowered for keyword in ["my detail", "my details", "profile", "account", "email", "phone", "points"]):
        parts = [
            f"I have your profile as {profile['name'] or 'Unnamed user'}.",
            f"Email: {profile['email'] or 'not set'}.",
            f"Phone: {profile['phone'] or 'not set'}.",
            f"Points balance: {profile['points_balance']}.",
        ]
        next_booking = _next_booking_line(bookings)
        if next_booking:
            parts.append(next_booking)
        return " ".join(parts)

    if any(keyword in lowered for keyword in ["booking", "reservation", "booked"]):
        next_booking = _next_booking_line(bookings)
        if next_booking:
            return f"You currently have {len(bookings)} total bookings. {next_booking}"
        return f"You currently have {len(bookings)} total bookings and no upcoming reservation on file."

    if "restaurant" in lowered or "food" in lowered or "dinner" in lowered or "lunch" in lowered:
        if recommendations:
            lines = [f"I looked at restaurant options for you, {user_name}:"]
            for item in recommendations[:3]:
                if item["type"] != "restaurant":
                    continue
                lines.append(f"- {item['name']} with rating {item['rating']:.1f}, near {item['metro']}")
            if len(lines) > 1:
                lines.append("If you want, tell me your budget, area, or whether you want family dining or something casual.")
                return "\n".join(lines)
        return f"I can help you find a restaurant, {user_name}. Tell me your preferred area, budget, or cuisine and I will narrow it down."

    if "hotel" in lowered or "room" in lowered or "stay" in lowered:
        if recommendations:
            lines = [f"Here are hotel options I can suggest for you, {user_name}:"]
            for item in recommendations[:3]:
                if item["type"] != "hotel":
                    continue
                lines.append(f"- {item['name']} with rating {item['rating']:.1f}, near {item['metro']}")
            if len(lines) > 1:
                lines.append("Tell me your check-in timing, budget, or preferred area and I will guide the next step.")
                return "\n".join(lines)
        return f"I can help with hotel stays, {user_name}. Tell me your preferred area, budget, or how many nights you need."

    if "spa" in lowered or "massage" in lowered or "relax" in lowered:
        if recommendations:
            lines = [f"I found spa-style options you may like, {user_name}:"]
            for item in recommendations[:3]:
                if item["type"] != "spa":
                    continue
                lines.append(f"- {item['name']} with rating {item['rating']:.1f}, near {item['metro']}")
            if len(lines) > 1:
                lines.append("Tell me whether you want massage, wellness, or a premium spa experience.")
                return "\n".join(lines)
        return f"I can help you with spa and wellness options, {user_name}. Tell me the area or treatment type you want."

    if "event" in lowered or "concert" in lowered or "festival" in lowered or "party" in lowered:
        if recommendations:
            lines = [f"I found event-related options for you, {user_name}:"]
            for item in recommendations[:3]:
                if item["type"] != "event":
                    continue
                lines.append(f"- {item['name']} with rating {item['rating']:.1f}, near {item['metro']}")
            if len(lines) > 1:
                lines.append("Tell me the date, area, or event style you want and I will refine it.")
                return "\n".join(lines)
        return f"I can help you explore events, {user_name}. Tell me what kind of event, date, or area you want."

    if recommendations:
        intro = "Based on your request"
        if known_topics:
            intro += f" and what you've been asking about ({', '.join(known_topics[:3])})"
        intro += ", here are a few options near the app data I can see:"
        lines = [intro]
        for item in recommendations[:3]:
            lines.append(f"- {item['name']} ({item['type']}, rating {item['rating']:.1f}, near {item['metro']})")
        next_booking = _next_booking_line(bookings)
        if next_booking:
            lines.append(next_booking)
        lines.append("If you want, tell me your budget or preferred area and I can narrow this down.")
        return "\n".join(lines)

    previous_topic_text = f" Your recent topics are {', '.join(known_topics[:3])}." if known_topics else ""
    return (
        f"I understood your message as: \"{message.strip()[:120]}\".{previous_topic_text} "
        "I can help with restaurants, hotels, spas, events, bookings, and your profile details. "
        "Tell me one concrete thing like area, budget, date, cuisine, stay type, or treatment type, and I will respond more specifically."
    )


def _fallback_reply(user: dict, bookings: list[dict]) -> str:
    profile = _profile_snapshot(user)
    next_booking = _next_booking_line(bookings)
    parts = [
        f"I can still help using your account details, {profile['name'] or 'there'}.",
        f"You currently have {len(bookings)} bookings on file.",
    ]
    if next_booking:
        parts.append(next_booking)
    parts.append("Try asking with one specific need like restaurant area, hotel stay, spa treatment, event type, booking status, or profile details.")
    return " ".join(parts)


async def _handle_turn(db: AsyncIOMotorDatabase, *, session: dict, user_id: str, content: str, metadata: dict | None = None) -> dict:
    user, bookings = await _load_user_context(db, user_id)
    user_topics = _infer_topics(content)
    current_memory = await _find_memory(db, session["_id"], user_id)
    current_memory = current_memory.get("memory") if isinstance(current_memory.get("memory"), dict) else {}
    prior_topics = current_memory.get("topics") if isinstance(current_memory.get("topics"), list) else []
    merged_topics = list(dict.fromkeys(prior_topics + user_topics))
    recommendations = await _top_recommendations(db, merged_topics or user_topics)
    reply = _compose_reply(content, user, bookings, current_memory, recommendations)

    session_oid = session["_id"]
    user_oid = ObjectId(user_id)
    now = _utcnow()
    user_message = {
        "_id": ObjectId(),
        "session_id": session_oid,
        "role": "user",
        "content": content,
        "metadata": metadata or {},
        "created_at": now,
    }
    assistant_message = {
        "_id": ObjectId(),
        "session_id": session_oid,
        "role": "assistant",
        "content": reply,
        "metadata": {"recommendations": recommendations},
        "created_at": _utcnow(),
    }

    updated_memory = _memory_summary(user, bookings, merged_topics)
    updated_memory["last_user_message"] = content
    updated_memory["last_assistant_reply"] = reply

    await db[THREAD_COLLECTION].update_one(
        {"_id": session_oid},
        {
            "$set": {
                "last_message_preview": reply[:180],
                "updated_at": _utcnow(),
            },
            "$push": {
                "messages": {
                    "$each": [user_message, assistant_message]
                }
            },
        },
    )
    await db[MEMORY_COLLECTION].update_one(
        {"session_id": session_oid, "user_id": user_oid},
        {
            "$set": {
                "session_id": session_oid,
                "user_id": user_oid,
                "memory": updated_memory,
                "updated_at": _utcnow(),
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    return {
        "reply": reply,
        "session": _serialize_session({**session, "last_message_preview": reply[:180], "updated_at": _utcnow()}),
        "user_message": _serialize_message(user_message),
        "assistant_message": _serialize_message(assistant_message),
        "memory": updated_memory,
    }


@router.get("/sessions")
async def list_ai_sessions(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    await _ensure_indexes(db)
    cursor = db[THREAD_COLLECTION].find({"user_id": ObjectId(user_id)}).sort("updated_at", -1)
    sessions = [_serialize_session(item) async for item in cursor]
    return envelope(sessions, meta={"count": len(sessions)})


@router.post("/sessions")
async def create_ai_session(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    await _ensure_indexes(db)
    session = await _create_session_document(db, user_id)
    return envelope(_serialize_session(session))


@router.get("/sessions/{session_id}/messages")
async def list_ai_messages(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    session = await _find_session(db, session_id, user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI session not found.")
    messages_raw = session.get("messages") if isinstance(session.get("messages"), list) else []
    messages = [_serialize_message(item) for item in messages_raw]
    return envelope(messages, meta={"count": len(messages), "session_id": session_id})


@router.post("/sessions/{session_id}/messages")
async def send_ai_message(
    session_id: str,
    payload: dict,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    content = str(payload.get("message") or payload.get("content") or "").strip()
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required.")

    session = await _find_session(db, session_id, user_id)
    if not session:
        session = await _create_session_document(db, user_id)

    try:
        result = await _handle_turn(db, session=session, user_id=user_id, content=content, metadata=metadata)
    except Exception:
        user, bookings = await _load_user_context(db, user_id)
        reply = _fallback_reply(user, bookings)
        result = {
            "reply": reply,
            "session": _serialize_session(session),
            "user_message": {
                "id": "",
                "session_id": session_id,
                "role": "user",
                "content": content,
                "metadata": metadata,
                "created_at": _utcnow().isoformat(),
            },
            "assistant_message": {
                "id": "",
                "session_id": session_id,
                "role": "assistant",
                "content": reply,
                "metadata": {"fallback": True},
                "created_at": _utcnow().isoformat(),
            },
        }
    return envelope(result)


@router.websocket("/sessions/{session_id}/ws")
async def ai_session_ws(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
):
    await websocket.accept()

    if not token:
        await websocket.send_json({"error": "Missing token."})
        await websocket.close(code=4401)
        return

    try:
        payload = decode_token(token, expected_type="access")
    except ValueError:
        await websocket.send_json({"error": "Invalid token."})
        await websocket.close(code=4401)
        return

    user_id = str(payload.get("sub") or "")
    db = websocket.app.state.db
    user_repo = UserRepository(db)
    user = await user_repo.find_by_id(user_id)
    if not user:
        await websocket.send_json({"error": "User not found."})
        await websocket.close(code=4401)
        return

    session = await _find_session(db, session_id, user_id)
    if not session:
        await websocket.send_json({"error": "AI session not found."})
        await websocket.close(code=4404)
        return

    await websocket.send_json({"type": "connected", "session_id": session_id})

    try:
        while True:
            frame = await websocket.receive_json()
            content = str(frame.get("message") or frame.get("content") or "").strip()
            metadata = frame.get("metadata") if isinstance(frame.get("metadata"), dict) else {}
            if not content:
                await websocket.send_json({"type": "error", "detail": "Message is required."})
                continue

            try:
                result = await _handle_turn(db, session=session, user_id=user_id, content=content, metadata=metadata)
                refreshed = await _find_session(db, session_id, user_id)
                if refreshed:
                    session = refreshed
            except Exception:
                user, bookings = await _load_user_context(db, user_id)
                reply = _fallback_reply(user, bookings)
                result = {
                    "reply": reply,
                    "session": _serialize_session(session),
                    "user_message": {
                        "id": "",
                        "session_id": session_id,
                        "role": "user",
                        "content": content,
                        "metadata": metadata,
                        "created_at": _utcnow().isoformat(),
                    },
                    "assistant_message": {
                        "id": "",
                        "session_id": session_id,
                        "role": "assistant",
                        "content": reply,
                        "metadata": {"fallback": True},
                        "created_at": _utcnow().isoformat(),
                    },
                }
            await websocket.send_json({"type": "message", **result})
    except WebSocketDisconnect:
        return
