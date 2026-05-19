"""Shared Pydantic models used across multiple routers.

Centralized here so identical response shapes aren't redefined per-router
(previously `SuccessResponse` lived in three separate files).
"""

from __future__ import annotations

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool
    message: str | None = None
