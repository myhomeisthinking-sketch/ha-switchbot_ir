"""Shared error type."""
from __future__ import annotations


class ManagerError(Exception):
    """利用者に見せられるエラー。statusはHTTPステータス。"""

    def __init__(self, message: str, status: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.extra = extra or {}
