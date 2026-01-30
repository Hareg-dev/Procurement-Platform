from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
import json
import time
import redis

from app.api.v1.dependencies import get_current_user
from app.core.db import get_db
from app.core.config import settings
from app.models.orm import User
from app.models.message import Message
from app.repositories.rfq_repo import rfq_repository

router = APIRouter()

class MessageRequest(BaseModel):
    content: str
    recipient_id: int  # User ID to send message to

class ConversationRequest(BaseModel):
    content: str
    conversation_id: str  # Format: "user1_user2" (sorted by ID)

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

# Active WebSocket connections
active_connections: dict = {}

async def get_redis_client():
    try:
        return redis.from_url(settings.redis_url, decode_responses=True)
    except:
        # Fallback if Redis not available
        return None

async def save_user_message(sender: User, recipient_id: int, content: str, db: AsyncSession) -> str:
    """Save message between two users."""
    conversation_id = f"{min(sender.id, recipient_id)}_{max(sender.id, recipient_id)}"
    
    # Save to database
    db_message = Message(
        content=content,
        sender_id=sender.id,
        recipient_id=recipient_id,
        conversation_id=conversation_id
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    
    return str(db_message.id)

async def update_conversation_list(user_id: int, other_user_id: int, last_message: str, timestamp: int):
    """Update user's conversation list."""
    redis_conn = await get_redis_client()
    if not redis_conn:
        return
        
    try:
        conversation_id = f"{min(user_id, other_user_id)}_{max(user_id, other_user_id)}"
        
        conversation_data = {
            "conversation_id": conversation_id,
            "other_user_id": other_user_id,
            "last_message": last_message,
            "last_message_time": timestamp
        }
        
        # Add to user's conversation list
        key = f"user_conversations:{user_id}"
        await redis_conn.hset(key, conversation_id, json.dumps(conversation_data))
        await redis_conn.expire(key, 90 * 24 * 60 * 60)
    except Exception as e:
        print(f"Redis error in update_conversation_list: {e}")

async def get_user_messages(conversation_id: str, limit: int, db: AsyncSession) -> List[dict]:
    """Get messages for a conversation."""
    from sqlalchemy import select, desc
    
    query = select(Message, User, Company).join(
        User, Message.sender_id == User.id
    ).join(
        Company, User.company_id == Company.id
    ).where(
        Message.conversation_id == conversation_id
    ).order_by(desc(Message.created_at)).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    messages = []
    for message, user, company in reversed(rows):  # Reverse to get chronological order
        messages.append({
            "id": str(message.id),
            "content": message.content,
            "sender_id": message.sender_id,
            "sender_name": f"{user.first_name} {user.last_name}",
            "sender_company": company.name,
            "recipient_id": message.recipient_id,
            "timestamp": int(message.created_at.timestamp()),
            "conversation_id": message.conversation_id
        })
    
    return messages

@router.post("/send", response_model=dict)
async def send_message(
    message_req: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a direct message to another user."""
    # Verify recipient exists
    from app.repositories.user_repo import user_repository
    recipient = await user_repository.get_with_company(db, message_req.recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    # Save message
    message_id = await save_user_message(current_user, message_req.recipient_id, message_req.content, db)
    
    # Create conversation ID
    conversation_id = f"{min(current_user.id, message_req.recipient_id)}_{max(current_user.id, message_req.recipient_id)}"
    
    # Broadcast to WebSocket if connected
    if conversation_id in active_connections:
        message_data = {
            "type": "new_message",
            "id": message_id,
            "content": message_req.content,
            "sender_id": current_user.id,
            "sender_name": f"{current_user.first_name} {current_user.last_name}",
            "sender_company": current_user.company.name,
            "timestamp": int(time.time()),
            "conversation_id": conversation_id
        }
        
        for websocket in active_connections[conversation_id]:
            try:
                await websocket.send_json(message_data)
            except:
                pass
    
    return {"message": "Message sent successfully", "message_id": message_id}

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's conversation list."""
    from sqlalchemy import select, func, desc, or_
    
    # Get latest message for each conversation
    subquery = select(
        Message.conversation_id,
        func.max(Message.created_at).label('last_time')
    ).where(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).group_by(Message.conversation_id).subquery()
    
    # Get conversation details
    query = select(Message, User, Company).join(
        subquery, Message.conversation_id == subquery.c.conversation_id
    ).join(
        User, Message.sender_id == User.id
    ).join(
        Company, User.company_id == Company.id
    ).where(
        Message.created_at == subquery.c.last_time
    ).order_by(desc(subquery.c.last_time))
    
    result = await db.execute(query)
    rows = result.all()
    
    conversations = []
    for message, user, company in rows:
        # Determine the other user
        other_user_id = message.recipient_id if message.sender_id == current_user.id else message.sender_id
        
        # Get other user details
        other_user_query = select(User, Company).join(Company).where(User.id == other_user_id)
        other_result = await db.execute(other_user_query)
        other_user, other_company = other_result.first()
        
        conversations.append(ConversationResponse(
            conversation_id=message.conversation_id,
            other_user_name=f"{other_user.first_name} {other_user.last_name}",
            other_user_company=other_company.name,
            last_message=message.content,
            last_message_time=int(message.created_at.timestamp()),
            unread_count=0
        ))
    
    return conversations

@router.get("/conversation/{conversation_id}", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user)
):
    """Get messages for a specific conversation."""
    # Verify user is part of this conversation
    user_ids = conversation_id.split("_")
    if str(current_user.id) not in user_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    
    messages = await get_user_messages(conversation_id, limit, db)
    return [MessageResponse(**msg) for msg in messages]

@router.websocket("/ws/{conversation_id}")
async def websocket_conversation_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """WebSocket endpoint for real-time messaging in a conversation."""
    await websocket.accept()
    
    try:
        # Authenticate user
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close()
            return
        
        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close()
            return
        
        # Verify user is part of conversation
        user_ids = conversation_id.split("_")
        if user_id not in user_ids:
            await websocket.send_json({"type": "error", "message": "Access denied"})
            await websocket.close()
            return
        
        # Add to active connections
        if conversation_id not in active_connections:
            active_connections[conversation_id] = []
        active_connections[conversation_id].append(websocket)
        
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to conversation {conversation_id}"
        })
        
        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        # Remove from active connections
        if conversation_id in active_connections:
            try:
                active_connections[conversation_id].remove(websocket)
                if not active_connections[conversation_id]:
                    del active_connections[conversation_id]
            except ValueError:
                pass