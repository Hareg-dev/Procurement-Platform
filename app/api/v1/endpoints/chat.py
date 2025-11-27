import json
import logging
from typing import Dict, List, Optional

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_token
from app.models.orm import User
from app.repositories.rfq_repo import rfq_repository
from app.services.llm_service import llm_service
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str

# Redis client for chat history storage
redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get Redis client for chat history storage."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return redis_client


async def authenticate_websocket_user(token: str, db: AsyncSession) -> Optional[User]:
    """
    Authenticate user from JWT token for WebSocket connection.
    
    Args:
        token: JWT token from query parameter
        db: Database session
        
    Returns:
        User if authenticated, None otherwise
    """
    try:
        # Decode JWT token
        payload = decode_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Get user from database
        from app.repositories.user_repo import user_repository
        user = await user_repository.get_with_company(db, int(user_id))
        
        if not user or not user.is_active:
            return None
            
        return user
        
    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None


async def get_chat_history(rfq_id: int, limit: int = 50) -> List[Dict[str, str]]:
    """
    Retrieve chat history for an RFQ from Redis.
    
    Args:
        rfq_id: RFQ ID
        limit: Maximum number of messages to retrieve
        
    Returns:
        List of chat messages in chronological order
    """
    try:
        redis_conn = await get_redis_client()
        key = f"chat_history:rfq:{rfq_id}"
        
        # Get recent messages from Redis list
        messages = await redis_conn.lrange(key, -limit, -1)
        
        # Parse JSON messages
        history = []
        for msg in messages:
            try:
                parsed_msg = json.loads(msg)
                history.append(parsed_msg)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse chat message: {msg}")
                continue
        
        return history
        
    except Exception as e:
        logger.error(f"Failed to retrieve chat history for RFQ {rfq_id}: {str(e)}")
        return []


async def save_chat_message(rfq_id: int, role: str, content: str) -> None:
    """
    Save a chat message to Redis.
    
    Args:
        rfq_id: RFQ ID
        role: Message role ('user' or 'assistant')
        content: Message content
    """
    try:
        redis_conn = await get_redis_client()
        key = f"chat_history:rfq:{rfq_id}"
        
        message = {
            "role": role,
            "content": content,
            "timestamp": int(time.time())
        }
        
        # Add message to Redis list
        await redis_conn.lpush(key, json.dumps(message))
        
        # Keep only last 100 messages per RFQ
        await redis_conn.ltrim(key, 0, 99)
        
        # Set expiration (30 days)
        await redis_conn.expire(key, 30 * 24 * 60 * 60)
        
    except Exception as e:
        logger.error(f"Failed to save chat message for RFQ {rfq_id}: {str(e)}")


@router.websocket("/ws/chat/{rfq_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    rfq_id: int,
    token: str = Query(..., description="JWT authentication token"),
):
    """
    WebSocket endpoint for AI co-pilot chat functionality.
    
    This endpoint provides real-time AI assistance for procurement decisions,
    RFQ analysis, bid evaluation, and general procurement guidance.
    
    Authentication:
    - Requires valid JWT token passed as query parameter
    - User must have access to the specified RFQ
    
    Message Format:
    - Send: {"message": "Your question or request"}
    - Receive: {"type": "ai_response", "message": "AI assistant response"}
    - Receive: {"type": "error", "message": "Error description"}
    
    Features:
    - Contextual AI assistance based on RFQ details
    - Persistent chat history stored in Redis
    - Real-time responses with WebSocket
    - Proper error handling and connection management
    """
    import time
    
    # Accept WebSocket connection
    await websocket.accept()
    
    user = None
    db = None
    
    try:
        # Get database session
        async for session in get_db():
            db = session
            break
        
        if not db:
            await websocket.send_json({
                "type": "error",
                "message": "Database connection failed"
            })
            await websocket.close()
            return
        
        # Authenticate user
        user = await authenticate_websocket_user(token, db)
        if not user:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication failed"
            })
            await websocket.close()
            return
        
        # Get RFQ and verify access
        rfq = await rfq_repository.get_with_details(db, rfq_id)
        if not rfq:
            await websocket.send_json({
                "type": "error",
                "message": "RFQ not found"
            })
            await websocket.close()
            return
        
        # Check if user has access to this RFQ
        has_access = (
            user.role.value == "admin" or
            rfq.buyer_company_id == user.company_id or
            (rfq.status.value == "open" and user.role.value == "supplier")
        )
        
        if not has_access:
            await websocket.send_json({
                "type": "error",
                "message": "Access denied to this RFQ"
            })
            await websocket.close()
            return
        
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "message": f"Connected to AI co-pilot for RFQ: {rfq.title}"
        })
        
        # Build RFQ context for AI
        rfq_context = f"""
        RFQ DETAILS:
        Title: {rfq.title}
        Description: {rfq.description}
        Budget: ${rfq.budget_min or 'Not specified'} - ${rfq.budget_max or 'Not specified'}
        Deadline: {rfq.deadline}
        Status: {rfq.status.value}
        Requirements: {rfq.requirements or 'No specific requirements'}
        Number of Bids: {len(rfq.bids) if rfq.bids else 0}
        
        USER CONTEXT:
        Role: {user.role.value}
        Company: {user.company.name}
        """
        
        # Main message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                user_message = message_data.get("message", "").strip()
                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Empty message received"
                    })
                    continue
                
                # Get chat history
                chat_history = await get_chat_history(rfq_id)
                
                # Generate AI response
                try:
                    ai_response = await llm_service.chat_with_ai(
                        rfq_context=rfq_context.strip(),
                        history=chat_history,
                        new_message=user_message
                    )
                    
                    # Save user message and AI response to history
                    await save_chat_message(rfq_id, "user", user_message)
                    await save_chat_message(rfq_id, "assistant", ai_response)
                    
                    # Send AI response to client
                    await websocket.send_json({
                        "type": "ai_response",
                        "message": ai_response
                    })
                    
                except Exception as e:
                    logger.error(f"AI response generation failed: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to generate AI response. Please try again."
                    })
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user.id if user else 'unknown'}")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": "An unexpected error occurred"
                })
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Connection error"
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@router.post("/simple-chat", response_model=ChatResponse)
async def simple_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user)
) -> ChatResponse:
    """
    Simple chat endpoint with TinyLlama AI.
    
    Provides basic AI assistance without RFQ context.
    """
    try:
        response = await llm_service.simple_chat(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"Simple chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get AI response")
