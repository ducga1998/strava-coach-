from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class MeResponse(BaseModel):
    id: int
    email: str
    name: str | None


class ChangePasswordRequest(BaseModel):
    current: str = Field(min_length=1, max_length=256)
    new: str = Field(min_length=12, max_length=256)
