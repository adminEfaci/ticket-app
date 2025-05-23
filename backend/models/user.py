from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Column, String
from pydantic import field_validator
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    PROCESSOR = "processor"
    CLIENT = "client"

class UserBase(SQLModel):
    email: str = Field(sa_column=Column(String(255), unique=True, index=True))
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    role: UserRole = Field(default=UserRole.CLIENT)
    is_active: bool = Field(default=True)

class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow_naive)
    updated_at: datetime = Field(default_factory=utcnow_naive)

class UserCreate(UserBase):
    password: str = Field(min_length=12)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        from pydantic import validate_email as pydantic_validate_email
        pydantic_validate_email(v)
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError('Password must contain uppercase, lowercase, digit, and special character')
        
        return v

class UserUpdate(SQLModel):
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

class UserLogin(SQLModel):
    email: str
    password: str