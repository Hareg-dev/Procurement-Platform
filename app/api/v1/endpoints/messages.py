import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.dependencies import get_current_user
from app.core.db import get_db
from app.core.security import decode_token
from app.models.message import Message
from app.models.orm import Company, User
from app.repositories.user_repo import user_repository

router = APIRouter()


class MessageRequest(BaseModel):
    content: str
    recipient_id: int  # User ID to send message to


class MessageResponse(BaseModel):
    id: str
    content: str
    sender_id: int
    sender_name: str
    sender_company: str
    recipient_id: int
    timestamp: int
    conversation_id: str


class ConversationResponse(BaseModel):
    conversation_id: str
    other_user_name: str
    other_user_company: str
    last_message: str
    last_message_time: int
    unread_count: int


# Active WebSocket connections keyed by conversation id.
# Process-local: real-time delivery requires a single worker (or a pub/sub fan-out).
active_connections: dict[str, list[WebSocket]] = {}


def build_conversation_id(first_user_id: int, second_user_id: int) -> str:
    """Build the deterministic conversation id for two users."""
    return f"{min(first_user_id, second_user_id)}_{max(first_user_id, second_user_id)}"


def conversation_participant_ids(conversation_id: str) -> set[int]:
    """Parse a conversation id into its participant user ids."""
    parts = conversation_id.split("_")
    if len(parts) != 2:
        raise ValueError("Invalid conversation id")
    return {int(part) for part in parts}


def unix_timestamp(value: datetime) -> int:
    """Convert a naive UTC datetime into a UNIX timestamp."""
    return int(value.replace(tzinfo=timezone.utc).timestamp())


async def save_user_message(
    sender: User, recipient_id: int, content: str, db: AsyncSession
) -> str:
    """Save a message between two users."""
    db_message = Message(
        content=content,
        sender_id=sender.id,
        recipient_id=recipient_id,
        conversation_id=build_conversation_id(sender.id, recipient_id),
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)

    return str(db_message.id)


async def get_user_messages(
    conversation_id: str, limit: int, db: AsyncSession
) -> List[dict]:
    """Get messages for a conversation in chronological order."""
    query = (
        select(Message, User, Company)
        .join(User, Message.sender_id == User.id)
        .join(Company, User.company_id == Company.id)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )

    rows = (await db.execute(query)).all()

    # Reverse to get chronological order
    return [
        {
            "id": str(message.id),
            "content": message.content,
            "sender_id": message.sender_id,
            "sender_name": f"{user.first_name} {user.last_name}",
            "sender_company": company.name,
            "recipient_id": message.recipient_id,
            "timestamp": unix_timestamp(message.created_at),
            "conversation_id": message.conversation_id,
        }
        for message, user, company in reversed(rows)
    ]


@router.post("/send", response_model=dict)
async def send_message(
    message_req: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a direct message to another user."""
    if message_req.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a message to yourself")

    recipient = await user_repository.get_with_company(db, message_req.recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    message_id = await save_user_message(
        current_user, message_req.recipient_id, message_req.content, db
    )
    conversation_id = build_conversation_id(current_user.id, message_req.recipient_id)

    # Broadcast to WebSocket clients connected to this conversation
    for websocket in active_connections.get(conversation_id, []):
        try:
            await websocket.send_json(
                {
                    "type": "new_message",
                    "id": message_id,
                    "content": message_req.content,
                    "sender_id": current_user.id,
                    "sender_name": f"{current_user.first_name} {current_user.last_name}",
                    "sender_company": current_user.company.name,
                    "timestamp": int(time.time()),
                    "conversation_id": conversation_id,
                }
            )
        except Exception:
            pass

    return {"message": "Message sent successfully", "message_id": message_id}


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's conversation list."""
    # Latest message id per conversation (ids are monotonic, so max(id) is the newest)
    latest_ids = (
        select(func.max(Message.id))
        .where(
            or_(
                Message.sender_id == current_user.id,
                Message.recipient_id == current_user.id,
            )
        )
        .group_by(Message.conversation_id)
        .scalar_subquery()
    )

    result = await db.execute(
        select(Message)
        .where(Message.id.in_(latest_ids))
        .order_by(desc(Message.created_at))
    )
    latest_messages = result.scalars().all()

    other_user_ids = {
        message.recipient_id
        if message.sender_id == current_user.id
        else message.sender_id
        for message in latest_messages
    }

    users: dict[int, User] = {}
    if other_user_ids:
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.id.in_(other_user_ids))
        )
        users = {user.id: user for user in result.scalars().all()}

    conversations = []
    for message in latest_messages:
        other_user_id = (
            message.recipient_id
            if message.sender_id == current_user.id
            else message.sender_id
        )
        other_user = users.get(other_user_id)

        conversations.append(
            ConversationResponse(
                conversation_id=message.conversation_id,
                other_user_name=(
                    f"{other_user.first_name} {other_user.last_name}"
                    if other_user
                    else "Unknown user"
                ),
                other_user_company=(
                    other_user.company.name
                    if other_user and other_user.company
                    else ""
                ),
                last_message=message.content,
                last_message_time=unix_timestamp(message.created_at),
                unread_count=0,
            )
        )

    return conversations


@router.get("/conversation/{conversation_id}", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific conversation."""
    try:
        participants = conversation_participant_ids(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation id")

    if current_user.id not in participants:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await get_user_messages(conversation_id, limit, db)
    return [MessageResponse(**message) for message in messages]


@router.websocket("/ws/{conversation_id}")
async def websocket_conversation_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(..., description="JWT authentication token"),
):
    """WebSocket endpoint for real-time messaging in a conversation."""
    await websocket.accept()

    try:
        payload = decode_token(token)
        user_id = payload.get("sub") if payload else None
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close()
            return

        try:
            participants = conversation_participant_ids(conversation_id)
        except ValueError:
            await websocket.send_json(
                {"type": "error", "message": "Invalid conversation id"}
            )
            await websocket.close()
            return

        if int(user_id) not in participants:
            await websocket.send_json({"type": "error", "message": "Access denied"})
            await websocket.close()
            return

        active_connections.setdefault(conversation_id, []).append(websocket)

        await websocket.send_json(
            {
                "type": "connected",
                "message": f"Connected to conversation {conversation_id}",
            }
        )

        # Keep the connection alive until the client disconnects
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break

    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        connections = active_connections.get(conversation_id)
        if connections and websocket in connections:
            connections.remove(websocket)
            if not connections:
                active_connections.pop(conversation_id, None)
