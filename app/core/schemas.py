"""Request bodies. Inputs and documents are JSON trees validated by size and shape here,
then interpreted by the generator."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    inputs: dict[str, Any]
    status: Literal["draft", "review", "sent", "approved", "rejected"] = "draft"


class ProposalUpdate(BaseModel):
    doc: dict[str, Any] | None = None
    inputs: dict[str, Any] | None = None
    status: Literal["draft", "review", "sent", "approved", "rejected"] | None = None


class RegenerateSection(BaseModel):
    tone: str | None = None


class RegenerateAll(BaseModel):
    inputs: dict[str, Any] | None = None


class VersionRequest(BaseModel):
    note: str = Field(default="", max_length=300)


class TemplateFromProposal(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class LibraryItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    key: str | None = Field(default=None, max_length=80)
    data: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    sort: int | None = None


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=120)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=60)
    about: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=300)
    logo: str | None = Field(default=None, max_length=300)


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    project_type: str = Field(default="", max_length=40)
    inputs: dict[str, Any] = Field(default_factory=dict)


class SettingsIn(BaseModel):
    values: dict[str, Any]
