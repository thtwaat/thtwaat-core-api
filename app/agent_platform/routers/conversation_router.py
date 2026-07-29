from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.agent_platform.conversation_schemas import (
    ConversationCreate, 
    ConversationResponse, 
    ConversationDetailResponse,
    MessageCreate
)
from app.agent_platform.services.conversation_service import ConversationService

router = APIRouter(prefix="/v2/conversations", tags=["Conversations"])

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """Create a new conversation thread"""
    company_id = auth_data.get("company_id")
    return ConversationService.create_conversation(db, company_id, data)


@router.get("", response_model=List[ConversationResponse])
def get_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """List all conversations for the authenticated company"""
    company_id = auth_data.get("company_id")
    return ConversationService.get_conversations(db, company_id, skip, limit)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """Get conversation details and full message history"""
    company_id = auth_data.get("company_id")
    return ConversationService.get_conversation(db, conversation_id, company_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """Delete a conversation"""
    company_id = auth_data.get("company_id")
    ConversationService.delete_conversation(db, conversation_id, company_id)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """Send a message to a conversation thread and get an AI response"""
    company_id = auth_data.get("company_id")
    result = await ConversationService.send_message(db, conversation_id, company_id, data.content)
    
    # We return the new user message and the assistant message
    return result
