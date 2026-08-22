from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ResearchSessionRequest(BaseModel):
    ipo_id: int
    title: str = Field(default="IPO research", min_length=1, max_length=255)


class ResearchQuestion(BaseModel):
    content: str = Field(min_length=3, max_length=4000)


class WatchlistRequest(BaseModel):
    ipo_id: int


class DCFScenario(BaseModel):
    revenue: float = Field(gt=0)
    ebitda_margin: float = Field(ge=0, le=1)
    tax_rate: float = Field(ge=0, le=1)
    growth_rate: float = Field(ge=-.5, le=1)
    discount_rate: float = Field(gt=0, le=1)
    terminal_growth: float = Field(ge=0, lt=1)
    years: int = Field(default=5, ge=1, le=10)

