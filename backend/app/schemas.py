from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, model_validator


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


class DCFInput(BaseModel):
    revenue_growth_rate: float = Field(ge=-0.5, le=1.0)
    ebitda_margin: float = Field(ge=0, le=1.0)
    tax_rate: float = Field(ge=0, le=1.0)
    d_and_a_pct_of_revenue: float = Field(ge=0, le=1.0)
    capex_pct_of_revenue: float = Field(ge=0, le=1.0)
    change_in_nwc_pct_of_revenue: float = Field(ge=-1.0, le=1.0)
    discount_rate: float = Field(gt=0, le=1.0)
    terminal_growth_rate: float = Field(ge=0, lt=1.0)
    years: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def check_terminal_growth(self) -> "DCFInput":
        if self.terminal_growth_rate >= self.discount_rate:
            raise ValueError("terminal_growth_rate must be less than discount_rate")
        return self

