from pydantic import BaseModel
from typing import Dict, Any, Optional

# Event models
class EventCreate(BaseModel):
    user_id: Optional[int] = None
    type: str
    meta: Optional[Dict[str, Any]] = {}

class EventUpdate(BaseModel):
    user_id: Optional[int] = None
    type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

# Admin Task models
class AdminTaskCreate(BaseModel):
    user_id: Optional[int] = None
    type: str
    status: str = 'scheduled'
    payload: Optional[Dict[str, Any]] = {}
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None

class AdminTaskUpdate(BaseModel):
    user_id: Optional[int] = None
    type: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None
    sent_at: Optional[str] = None
    result_code: Optional[str] = None

# Template models
class TemplateCreate(BaseModel):
    type: str
    tone: str
    text: str
    enabled: bool = True
    weight: int = 1

class TemplateUpdate(BaseModel):
    type: Optional[str] = None
    tone: Optional[str] = None
    text: Optional[str] = None
    enabled: Optional[bool] = None
    weight: Optional[int] = None

# Daily Message models
class DailyMessageCreate(BaseModel):
    text: str
    is_active: bool = True
    weight: int = 1

class DailyMessageUpdate(BaseModel):
    text: Optional[str] = None
    is_active: Optional[bool] = None
    weight: Optional[int] = None

# AI Prompt models
class PromptCreate(BaseModel):
    key: str
    name: str
    prompt_text: str
    description: Optional[str] = None
    is_active: bool = True

class PromptUpdate(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = None
    prompt_text: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None