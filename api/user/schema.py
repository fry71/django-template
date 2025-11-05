# api/user/schema.py
from __future__ import annotations
from typing import Optional, List, Literal
from datetime import datetime
from ninja import Schema
from pydantic import Field, ConfigDict
import re


def validate_email(email: str) -> bool:
    """Простая валидация email"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


class UserSchema(Schema):
    """Schema for representing complete user profile"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    is_staff: bool = False
    is_active: bool = True


class UserCreateSchema(Schema):
    """Schema for creating new user"""

    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None


class UserUpdateSchema(Schema):
    """Schema for partial user data update"""

    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    is_staff: Optional[bool] = None
    is_active: Optional[bool] = None


class PaginatedUsersOut(Schema):
    """Schema for paginated user list output"""

    count: int
    results: List[UserSchema]


class ErrorSchema(Schema):
    """Schema for API error display"""

    detail: str


class UserLoginSchema(Schema):
    """Schema for user login"""

    username: str
    password: str


class UserTokenSchema(Schema):
    """Schema for JWT token issuance"""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"


class MessageInSchema(Schema):
    """Schema for message creation input data"""

    content: str


class MessageSchema(Schema):
    """Schema for message output data"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    timestamp: datetime
    sender: str


class PaginatedMessagesOut(Schema):
    """Schema for paginated message list output"""

    count: int
    search: Optional[str] = None
    sort: Optional[str] = None
    results: List[MessageSchema]


class PhotoSchema(Schema):
    """Schema for user photos"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    image: str
    user_id: int
