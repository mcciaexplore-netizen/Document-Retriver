from datetime import date
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("name", "email", mode="before")
    @classmethod
    def trim_input(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.lower()
        local, separator, domain = value.rpartition("@")
        labels = domain.split(".")
        if (not separator or len(local) > 64
                or not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*", local)
                or len(labels) < 2
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
            raise ValueError("Enter a valid email address.")
        return value


class PasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    color: str = Field(default="teal", pattern="^(teal|blue|green|amber|violet|rose)$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Workspace name cannot be empty.")
        return value


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_type: str | None = None
    file_id: int | None = None
    file_name: str | None = Field(default=None, max_length=255)
    date_from: date | None = None
    date_to: date | None = None
    source: str | None = Field(default=None, max_length=40)
    source_type: str | None = Field(default=None, max_length=40)
    sheet: str | None = Field(default=None, max_length=255)
    sheet_name: str | None = Field(default=None, max_length=255)
    page: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=80)
    header: str | None = Field(default=None, max_length=500)
    amount_min: float | None = Field(default=None, allow_inf_nan=False)
    amount_max: float | None = Field(default=None, allow_inf_nan=False)
    keyword: str | None = Field(default=None, max_length=500)
    status: str | None = None


class SearchInput(BaseModel):
    query: str = Field(default="", max_length=500)
    workspace_id: int = Field(gt=0)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=100, ge=1, le=500)


class MembershipInput(BaseModel):
    user_id: int = Field(gt=0)


class UserInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=200)
    role: str = Field(pattern="^(Admin|Manager|Viewer)$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("User name cannot be empty.")
        return value
