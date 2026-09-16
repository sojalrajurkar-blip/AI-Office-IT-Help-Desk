from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.enums import UserRole



class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")
    full_name: str = Field(..., min_length=2)
    role: Optional[UserRole] = UserRole.REQUESTER
    department: Optional[str] = None
    office_location: Optional[str] = None
    phone_number: Optional[str] = None
    team_id: Optional[int] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: int
    full_name: str
    email: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    department: Optional[str] = None
    office_location: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    team_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):

    full_name: Optional[str] = None
    department: Optional[str] = None
    office_location: Optional[str] = None
    phone_number: Optional[str] = None
    team_id: Optional[int] = None
