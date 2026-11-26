"""Minimal SwitchBot Cloud API v1.1 client (HMAC-SHA256 signed requests)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import API_BASE


# ヘッダーに入れる値は、表示可能なASCII(空白・改行なし)に限る(ヘッダーインジェクション対策)
_HEADER_SAFE = re.compile(r"^[\x21-\x7e]{1,512}$")


class SwitchBotError(Exception):
    """Base error."""


class SwitchBotAuthError(SwitchBotError):
    """Token/secret invalid (HTTP 401). 1日の上限を超えたときも 401 になる."""


class SwitchBotRateLimitError(SwitchBotError):
    """HTTP 429."""


class SwitchBotConnectionError(SwitchBotError):
    """Network / timeout error."""


class SwitchBotApiError(SwitchBotError):
    """HTTP 200 だが statusCode が 100 以外."""

    def __init__(self, code: int, message: str) -> None:
        message = message[:200]
        super().__init__(f"statusCode {code}: {message}")
        self.code = code
        self.api_message = message


def make_headers(token: str, secret: str) -> dict[str, str]:
    nonce = str(uuid.uuid4())
    t = str(int(round(time.time() * 1000)))
    string_to_sign = f"{token}{t}{nonce}".encode("utf-8")
    sign = base64.b64encode(
        hmac.new(secret.encode("utf-8"), msg=string_to_sign, digestmod=hashlib.sha256).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "Content-Type": "application/json; charset=utf8",
        "t": t,
        "sign": sign,
        "nonce": nonce,
    }


class SwitchBotClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        credentials: Callable[[], tuple[str, str]],
        on_request: Callable[[], None] | None = None,
    ) -> None:
        self._session = session
        self._credentials = credentials
        self._on_request = on_request

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        token, secret = self._credentials()
        if not (_HEADER_SAFE.match(token or "") and _HEADER_SAFE.match(secret or "")):
            raise SwitchBotAuthError("invalid credential format")
        headers = make_headers(token, secret)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        if self._on_request:
            self._on_request()
        try:
            async with self._session.request(
                method,
                f"{API_BASE}{path}",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise SwitchBotAuthError("unauthorized")
                if resp.status == 429:
                    raise SwitchBotRateLimitError("too many requests")
                if resp.status >= 400:
                    raise SwitchBotError(f"HTTP {resp.status}")
                try:
                    payload = await resp.json(content_type=None)
                except ValueError as err:
                    raise SwitchBotError("応答を解析できません") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SwitchBotConnectionError(str(err)) from err
        if not isinstance(payload, dict):
            raise SwitchBotError("想定外の応答です")
        code = payload.get("statusCode")
        if code != 100:
            raise SwitchBotApiError(int(code) if isinstance(code, int) else -1, str(payload.get("message", "")))
        return payload.get("body")

    async def get_devices(self) -> dict[str, Any]:
        """GET /v1.1/devices -> {"deviceList": [...], "infraredRemoteList": [...]}"""
        body = await self._request("GET", "/v1.1/devices")
        return body if isinstance(body, dict) else {}

    async def send_command(
        self, device_id: str, command: str, command_type: str, parameter: str
    ) -> None:
        """POST /v1.1/devices/{id}/commands"""
        await self._request(
            "POST",
            f"/v1.1/devices/{device_id}/commands",
            {"command": command, "parameter": parameter, "commandType": command_type},
        )
