"""Persistent storage (.storage/switchbot_ir): credentials, fetched remotes, daily call counter."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_KEY, STORAGE_VERSION


class Ledger:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True)
        self.token = ""
        self.secret = ""
        self.cache: dict[str, Any] = {}
        self.usage: dict[str, Any] = {}
        # key -> {"alias", "icon", "device_id", "command_type", "command", "parameter"}
        self.buttons: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.token = data.get("token") or ""
        self.secret = data.get("secret") or ""
        self.cache = data.get("cache") or {}
        self.usage = data.get("usage") or {}
        self.buttons = data.get("buttons") or {}

    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {
                "token": self.token,
                "secret": self.secret,
                "cache": self.cache,
                "usage": self.usage,
                "buttons": self.buttons,
            },
            1,
        )

    def set_credentials(self, token: str, secret: str) -> None:
        self.token, self.secret = token, secret
        self._save()

    def set_cache(self, cache: dict[str, Any]) -> None:
        self.cache = cache
        self._save()

    def count_request(self) -> None:
        today = dt_util.now().date().isoformat()
        if self.usage.get("date") != today:
            self.usage = {"date": today, "count": 0}
        self.usage["count"] = int(self.usage.get("count", 0)) + 1
        self._save()

    def today_count(self) -> int:
        if self.usage.get("date") != dt_util.now().date().isoformat():
            return 0
        return int(self.usage.get("count", 0))

    def set_button(self, key: str, item: dict[str, Any]) -> None:
        self.buttons[key] = item
        self._save()

    def del_button(self, key: str) -> None:
        self.buttons.pop(key, None)
        self._save()
