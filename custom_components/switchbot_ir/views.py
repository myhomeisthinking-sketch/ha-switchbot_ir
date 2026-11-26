"""HTTP API for the SwitchBot IR panel (admin only)."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .errors import ManagerError
from .manager import SwitchBotManager

_LOGGER = logging.getLogger(__name__)
BASE = f"/api/{DOMAIN}"


def _err(message: str, status: int = 400, **extra: Any) -> web.Response:
    return web.json_response({"error": message, "message": message, **extra}, status=status)


def _area(body: dict[str, Any]) -> str | None:
    """area_id: キーなし=変更しない / 空文字=解除 / ID=そのエリア"""
    return None if body.get("area_id") is None else str(body["area_id"])


class _Base(HomeAssistantView):
    requires_auth = True

    async def _run(self, request: web.Request, handler):  # noqa: ANN001
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return _err("管理者権限が必要です", 403)
        hass: HomeAssistant = request.app["hass"]
        mgr: SwitchBotManager | None = hass.data.get(DOMAIN, {}).get("manager")
        if mgr is None:
            return _err("SwitchBot IRが読み込まれていません", 503)
        try:
            return await handler(hass, mgr)
        except ManagerError as err:
            return _err(str(err), err.status, **err.extra)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("SwitchBot IR APIでエラーが発生しました")
            return _err("内部エラーが発生しました(HAのログを確認してください)", 500)

    @staticmethod
    async def _body(request: web.Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}


class StatusView(_Base):
    url = f"{BASE}/status"
    name = f"api:{DOMAIN}:status"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response(mgr.status())

        return await self._run(request, h)


class FetchView(_Base):
    url = f"{BASE}/fetch"
    name = f"api:{DOMAIN}:fetch"

    async def post(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response(await mgr.fetch())

        return await self._run(request, h)


class CredentialsView(_Base):
    url = f"{BASE}/credentials"
    name = f"api:{DOMAIN}:credentials"

    async def put(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            await mgr.update_credentials(
                str(body.get("token", "")), str(body.get("secret", ""))
            )
            return web.json_response(mgr.status())

        return await self._run(request, h)


class RemotesView(_Base):
    url = f"{BASE}/remotes"
    name = f"api:{DOMAIN}:remotes"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"remotes": await mgr.list_remotes()})

        return await self._run(request, h)


class TestSendView(_Base):
    url = f"{BASE}/test_send"
    name = f"api:{DOMAIN}:test_send"

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            await mgr.test_send(
                str(body.get("device_id", "")),
                str(body.get("command_type", "")),
                str(body.get("command", "")),
                str(body.get("parameter") or ""),
            )
            return web.json_response({"ok": True})

        return await self._run(request, h)


class ButtonsView(_Base):
    url = f"{BASE}/buttons"
    name = f"api:{DOMAIN}:buttons"

    async def get(self, request: web.Request) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"buttons": await mgr.list_buttons()})

        return await self._run(request, h)

    async def post(self, request: web.Request) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            result = await mgr.add_button(
                str(body.get("device_id", "")),
                str(body.get("command_type", "")),
                str(body.get("command", "")),
                str(body.get("parameter") or ""),
                str(body.get("slug", "")),
                str(body.get("alias", "")),
                str(body.get("icon") or ""),
                area_id=_area(body),
            )
            return web.json_response(result)

        return await self._run(request, h)


class ButtonItemView(_Base):
    url = f"{BASE}/buttons/{{key}}"
    name = f"api:{DOMAIN}:button_item"

    async def put(self, request: web.Request, key: str) -> web.Response:
        body = await self._body(request)

        async def h(hass, mgr):  # noqa: ANN001
            result = await mgr.update_button(
                key,
                str(body.get("alias", "")),
                str(body.get("icon") or ""),
                str(body.get("device_id", "")),
                str(body.get("command_type", "")),
                str(body.get("command", "")),
                str(body.get("parameter") or ""),
                area_id=_area(body),
            )
            return web.json_response(result)

        return await self._run(request, h)

    async def delete(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response(await mgr.delete_button(key))

        return await self._run(request, h)


class ButtonRefsView(_Base):
    url = f"{BASE}/buttons/{{key}}/references"
    name = f"api:{DOMAIN}:button_refs"

    async def get(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            return web.json_response({"references": await mgr.button_references(key)})

        return await self._run(request, h)


class ButtonSendView(_Base):
    url = f"{BASE}/buttons/{{key}}/send"
    name = f"api:{DOMAIN}:button_send"

    async def post(self, request: web.Request, key: str) -> web.Response:
        async def h(hass, mgr):  # noqa: ANN001
            await mgr.press_button(key)
            return web.json_response({"ok": True})

        return await self._run(request, h)


ALL_VIEWS = (
    StatusView,
    FetchView,
    CredentialsView,
    RemotesView,
    TestSendView,
    ButtonsView,
    ButtonItemView,
    ButtonRefsView,
    ButtonSendView,
)
