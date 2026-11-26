"""Core logic of SwitchBot IR (cloud)."""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from . import references
from .api import (
    SwitchBotApiError,
    SwitchBotAuthError,
    SwitchBotClient,
    SwitchBotConnectionError,
    SwitchBotError,
    SwitchBotRateLimitError,
)
from .const import (
    CMD_CUSTOM,
    CMD_STANDARD,
    COMMAND_RE,
    COMMAND_TYPES,
    DAILY_LIMIT,
    DEVICE_ID_RE,
    DOMAIN,
    ICON_RE,
    SLUG_PREFIX,
    SLUG_RE,
)

from .button import ButtonHub
from .errors import ManagerError
from .ledger import Ledger

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")

NOTIFICATION_ID = f"{DOMAIN}_auth"

_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_CRED_RE = re.compile(r"^[\x21-\x7e]{8,512}$")
MAX_REMOTES = 500


def _text(value: Any, limit: int = 100) -> str | None:
    """クラウドから受け取った文字列は、制御文字を除き、長さを制限して保存する。"""
    if value is None:
        return None
    return _CTRL.sub("", str(value)).strip()[:limit]

# SwitchBot API の statusCode(100以外)に添えるヒント
API_HINTS = {
    151: "デバイスの種類が合いません",
    152: "リモコン(デバイス)が見つかりません。「情報を取得」で一覧を更新してください",
    160: "このコマンドは、リモコンが対応していません。ボタン名・コマンド名を確認してください",
    161: "デバイスがオフラインです",
    171: "ハブがオフラインです",
    190: "デバイスの内部エラー、またはコマンドの形式(パラメータなど)が不正の可能性があります",
}


def remote_label(meta: dict[str, Any]) -> str:
    """'ハブ名 / リモコン名(種類)' 形式のラベル."""
    name = meta.get("name") or meta.get("device_id", "?")
    if meta.get("remote_type"):
        name = f"{name}({meta['remote_type']})"
    return f"{meta['hub_name']} / {name}" if meta.get("hub_name") else name


def default_command_type(remote_type: str | None) -> str:
    """学習させるタイプ(DIY・Others)はカスタムボタン、それ以外は標準コマンドを既定にする."""
    rt = (remote_type or "").strip()
    return CMD_CUSTOM if rt == "Others" or rt.startswith("DIY") else CMD_STANDARD


class SwitchBotManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.ledger = Ledger(hass)
        self.session = async_get_clientsession(hass)
        self.client = SwitchBotClient(
            self.session,
            lambda: (self.ledger.token, self.ledger.secret),
            self.ledger.count_request,
        )
        self.hub = ButtonHub(hass, self.press_button, self.device_for)
        self.auth_failed = False

    def device_for(self, item: dict[str, Any]) -> dict[str, Any]:
        """ボタンは、そのリモコンのデバイスにまとめる。"""
        did = item["device_id"]
        meta = self._remote_map().get(did) or {}
        return {
            "identifiers": {(DOMAIN, did)},
            "name": meta.get("name") or did,
            "manufacturer": "SwitchBot",
            "model": meta.get("remote_type") or "IR Remote",
        }

    async def async_setup(self) -> None:
        await self.ledger.async_load()

    # ------------------------------------------------------------ cloud access

    def _set_auth_failed(self, failed: bool) -> None:
        if failed == self.auth_failed:
            return
        self.auth_failed = failed
        if failed:
            persistent_notification.async_create(
                self.hass,
                "SwitchBotのトークンまたはシークレットが無効です(リセットされた可能性があります)。"
                "サイドバーの「SwitchBot IR」→「設定」から入力し直してください。",
                title="SwitchBot IR: 認証に失敗しました",
                notification_id=NOTIFICATION_ID,
            )
        else:
            persistent_notification.async_dismiss(self.hass, NOTIFICATION_ID)

    @staticmethod
    def _convert(err: SwitchBotError) -> ManagerError:
        if isinstance(err, SwitchBotRateLimitError):
            return ManagerError("APIのレート制限に達しました。しばらく待ってください", 502)
        if isinstance(err, SwitchBotConnectionError):
            return ManagerError(f"SwitchBotクラウドに接続できません: {err}", 502)
        if isinstance(err, SwitchBotApiError):
            hint = API_HINTS.get(err.code)
            text = f"SwitchBot APIがエラーを返しました(code {err.code}: {err.api_message})"
            return ManagerError(f"{hint}\n{text}" if hint else text, 502)
        return ManagerError(f"SwitchBot APIでエラーが発生しました: {err}", 502)

    async def _cloud(self, call: Callable[[], Awaitable[T]]) -> T:
        if not (self.ledger.token and self.ledger.secret):
            raise ManagerError("トークンとシークレットが未設定です。「設定」から入力してください")
        try:
            result = await call()
        except SwitchBotAuthError as err:
            self._set_auth_failed(True)
            raise ManagerError(
                "認証に失敗しました。トークン・シークレットが無効(リセットされた可能性)か、"
                f"1日の上限({DAILY_LIMIT}回)を超えた可能性があります。「設定」を確認してください",
                502,
            ) from err
        except SwitchBotError as err:
            raise self._convert(err) from err
        self._set_auth_failed(False)
        return result

    async def update_credentials(self, token: str, secret: str) -> None:
        token = (token or "").strip() or self.ledger.token
        secret = (secret or "").strip() or self.ledger.secret
        if not token or not secret:
            raise ManagerError("トークンとシークレットの両方を入力してください")
        if not (_CRED_RE.match(token) and _CRED_RE.match(secret)):
            raise ManagerError(
                "トークンまたはシークレットの形式が不正です(空白を含まない半角の英数字・記号、8〜512文字)"
            )
        probe = SwitchBotClient(
            self.session, lambda: (token, secret), self.ledger.count_request
        )
        try:
            await probe.get_devices()
        except SwitchBotAuthError as err:
            raise ManagerError("トークンまたはシークレットが無効です。入力を確認してください", 400) from err
        except SwitchBotError as err:
            raise self._convert(err) from err
        self.ledger.set_credentials(token, secret)
        self._set_auth_failed(False)

    # ------------------------------------------------------------ fetch (明示操作)

    def status(self) -> dict[str, Any]:
        cache = self.ledger.cache
        return {
            "configured": bool(self.ledger.token and self.ledger.secret),
            "auth_failed": self.auth_failed,
            "fetched_at": cache.get("fetched_at"),
            "count": len(cache.get("remotes") or []),
            "calls_today": self.ledger.today_count(),
            "daily_limit": DAILY_LIMIT,
        }

    async def fetch(self) -> dict[str, Any]:
        """クラウドから赤外線リモコンの一覧を取得する。パネルの「情報を取得」を押したときだけ呼ばれる。"""
        body = await self._cloud(lambda: self.client.get_devices())
        hubs = {d.get("deviceId"): d.get("deviceName") for d in body.get("deviceList") or []}
        remotes = [
            {
                "device_id": str(r["deviceId"]),
                "name": _text(r.get("deviceName")),
                "remote_type": _text(r.get("remoteType"), 40),
                "hub_name": _text(hubs.get(r.get("hubDeviceId"))),
            }
            for r in (body.get("infraredRemoteList") or [])[:MAX_REMOTES]
            if DEVICE_ID_RE.match(str(r.get("deviceId") or ""))
        ]
        self.ledger.set_cache({"fetched_at": dt_util.utcnow().isoformat(), "remotes": remotes})
        self.hub.sync_devices(self.ledger.buttons)  # リモコン名の変更を、デバイス名に反映する
        return self.status()

    def _remote_map(self) -> dict[str, dict[str, Any]]:
        return {r["device_id"]: r for r in self.ledger.cache.get("remotes") or []}

    # ------------------------------------------------------------- validation

    @staticmethod
    def _check_command(
        device_id: str, command_type: str, command: str, parameter: str
    ) -> tuple[str, str, str, str]:
        device_id = (device_id or "").strip()
        command_type = (command_type or "").strip()
        command = (command or "").strip()
        parameter = (parameter or "").strip() or "default"
        if not DEVICE_ID_RE.match(device_id):
            raise ManagerError("リモコンのIDが不正です")
        if command_type not in COMMAND_TYPES:
            raise ManagerError("種別が不正です")
        if not command or len(command) > 80 or _CTRL.search(command):
            raise ManagerError("ボタン名を入力してください(80文字以内)")
        if command_type == CMD_STANDARD and not COMMAND_RE.match(command):
            raise ManagerError("標準コマンドのボタン名は、半角英数字で入力してください(例 turnOn)")
        if command_type == CMD_CUSTOM:
            parameter = "default"
        if len(parameter) > 200 or _CTRL.search(parameter):
            raise ManagerError("パラメータが不正です(200文字以内)")
        return device_id, command_type, command, parameter

    @staticmethod
    def _check_fields(alias: str, icon: str) -> tuple[str, str]:
        alias = _CTRL.sub("", alias or "").strip()
        icon = (icon or "").strip()
        if not alias or len(alias) > 80:
            raise ManagerError("アクション名称を入力してください(80文字以内)")
        if icon and not ICON_RE.match(icon):
            raise ManagerError("アイコンの形式が不正です(例 mdi:television)")
        return alias, icon

    # ------------------------------------------------------------------ send

    async def send(self, device_id: str, command: str, command_type: str, parameter: str) -> None:
        d, t, c, p = self._check_command(device_id, command_type, command, parameter)
        await self._cloud(lambda: self.client.send_command(d, c, t, p))

    async def test_send(
        self, device_id: str, command_type: str, command: str, parameter: str
    ) -> None:
        if (device_id or "").strip() not in self._remote_map():
            raise ManagerError("リモコンが一覧にありません。「情報を取得」を押してください", 404)
        await self.send(device_id, command, command_type, parameter)

    # ----------------------------------------------------------------- remotes

    def _eid(self, key: str) -> str:
        return self.hub.entity_id(key) or f"button.{key}"

    async def list_remotes(self) -> list[dict[str, Any]]:
        remotes = self._remote_map()
        out = []
        for did, meta in remotes.items():
            out.append(
                {
                    "device_id": did,
                    "label": remote_label(meta),
                    "name": meta.get("name") or "",
                    "remote_type": meta.get("remote_type") or "",
                    "default_type": default_command_type(meta.get("remote_type")),
                    "buttons": [
                        {
                            "key": k,
                            "entity_id": self._eid(k),
                            "alias": b["alias"],
                            "command": b["command"],
                            "command_type": b["command_type"],
                        }
                        for k, b in self.ledger.buttons.items()
                        if b["device_id"] == did
                    ],
                }
            )
        return out

    # ------------------------------------------------------------------ buttons

    async def list_buttons(self) -> list[dict[str, Any]]:
        remotes = self._remote_map()
        out = []
        for key, b in self.ledger.buttons.items():
            meta = remotes.get(b["device_id"])
            out.append(
                {
                    "key": key,
                    "entity_id": self._eid(key),
                    "area_id": self.hub.area_of(key),
                    "alias": b["alias"],
                    "icon": b.get("icon") or "",
                    "device_id": b["device_id"],
                    "label": remote_label(meta) if meta else None,
                    "command_type": b["command_type"],
                    "command": b["command"],
                    "parameter": b["parameter"],
                }
            )
        return out

    @staticmethod
    def _same_button(b: dict[str, Any], d: str, t: str, c: str, p: str) -> bool:
        return (b["device_id"], b["command_type"], b["command"], b["parameter"]) == (d, t, c, p)

    def _check_area(self, area_id: str | None) -> str | None:
        """None=変更しない / 空文字=解除 / ID=そのエリア(存在を確認)。"""
        if area_id is None:
            return None
        area_id = area_id.strip()
        if area_id and not self.hub.area_exists(area_id):
            raise ManagerError("エリアが見つかりません", status=404)
        return area_id

    async def add_button(
        self,
        device_id: str,
        command_type: str,
        command: str,
        parameter: str,
        slug: str,
        alias: str,
        icon: str,
        area_id: str | None = None,
    ) -> dict[str, Any]:
        alias, icon = self._check_fields(alias, icon)
        area_id = self._check_area(area_id)
        if not SLUG_RE.match(slug or ""):
            raise ManagerError("IDは小文字英数字とアンダースコアで入力してください(40文字以内)")
        d, t, c, p = self._check_command(device_id, command_type, command, parameter)
        if d not in self._remote_map():
            raise ManagerError("リモコンが一覧にありません。「情報を取得」を押してください", 404)
        key = f"{SLUG_PREFIX}{slug}"
        if key in self.ledger.buttons or self.hub.is_taken(key):
            raise ManagerError(f"button.{key} は既に使われています", status=409)
        for k, b in self.ledger.buttons.items():
            if self._same_button(b, d, t, c, p):
                raise ManagerError(
                    f"同じボタンが {self._eid(k)} として登録済みです",
                    status=409,
                    extra={"match": {"key": k, "entity_id": self._eid(k)}},
                )
        item = {
            "alias": alias,
            "icon": icon,
            "device_id": d,
            "command_type": t,
            "command": c,
            "parameter": p,
        }
        self.ledger.set_button(key, item)
        self.hub.add(key, item)
        if area_id:
            self.hub.set_area(key, area_id)
        return {"key": key, "entity_id": self._eid(key)}

    async def update_button(
        self,
        key: str,
        alias: str,
        icon: str,
        device_id: str,
        command_type: str,
        command: str,
        parameter: str,
        area_id: str | None = None,
    ) -> dict[str, Any]:
        alias, icon = self._check_fields(alias, icon)
        area_id = self._check_area(area_id)
        d, t, c, p = self._check_command(device_id, command_type, command, parameter)
        current = self.ledger.buttons.get(key)
        if current is None:
            raise ManagerError(f"button.{key} が見つかりません", status=404)
        if d != current["device_id"] and d not in self._remote_map():
            raise ManagerError("リモコンが一覧にありません。「情報を取得」を押してください", 404)
        for k, b in self.ledger.buttons.items():
            if k != key and self._same_button(b, d, t, c, p):
                raise ManagerError(f"同じボタンが {self._eid(k)} として登録済みです", status=409)
        item = {
            "alias": alias,
            "icon": icon,
            "device_id": d,
            "command_type": t,
            "command": c,
            "parameter": p,
        }
        self.ledger.set_button(key, item)
        self.hub.update(key, item)
        if area_id is not None:
            self.hub.set_area(key, area_id)
        return {"key": key, "entity_id": self._eid(key)}

    async def delete_button(self, key: str) -> dict[str, Any]:
        if key not in self.ledger.buttons:
            raise ManagerError(f"button.{key} が見つかりません", status=404)
        result = self.hub.remove(key)
        self.ledger.del_button(key)
        return {"ok": True, "entity": result}

    async def button_references(self, key: str) -> list[dict[str, Any]]:
        return await self.hass.async_add_executor_job(
            references.search_references, self.hass.config.config_dir, self._eid(key)
        )

    async def press_button(self, key: str) -> None:
        b = self.ledger.buttons.get(key)
        if b is None:
            raise ManagerError("ボタンが見つかりません", status=404)
        await self.send(b["device_id"], b["command"], b["command_type"], b["parameter"])
