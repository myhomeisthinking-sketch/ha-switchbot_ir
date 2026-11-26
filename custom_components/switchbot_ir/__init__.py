"""SwitchBot IR (cloud): register SwitchBot infrared remote buttons as HA button entities (sidebar panel)."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CMD_CUSTOM, COMMAND_TYPES, DOMAIN, PANEL_URL, PANEL_VERSION, STATIC_URL
from .errors import ManagerError
from .manager import SwitchBotManager
from .views import ALL_VIEWS

_LOGGER = logging.getLogger(__name__)

SEND_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("command"): cv.string,
        vol.Optional("command_type", default=CMD_CUSTOM): vol.In(COMMAND_TYPES),
        vol.Optional("parameter", default="default"): cv.string,
    }
)
JS_FILE = "switchbot-ir-panel.js"
PLATFORMS = ["button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {})

    mgr = SwitchBotManager(hass)
    await mgr.async_setup()
    domain_data["manager"] = mgr
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- HTTP API と静的ファイル(再読込で重複登録しないよう1回だけ)
    if not domain_data.get("http_registered"):
        for view in ALL_VIEWS:
            hass.http.register_view(view())
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    f"{STATIC_URL}/{JS_FILE}",
                    str(Path(__file__).parent / "frontend" / JS_FILE),
                    False,
                )
            ]
        )
        domain_data["http_registered"] = True

    # --- サイドバーのパネル(管理者のみ)
    # JSを差し替えたとき、ブラウザの古いキャッシュを使わないよう、更新時刻をURLに含める
    js_file = Path(__file__).parent / "frontend" / JS_FILE
    js_mtime = await hass.async_add_executor_job(lambda: int(js_file.stat().st_mtime))
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="switchbot-ir-panel",
        frontend_url_path=PANEL_URL,
        module_url=f"{STATIC_URL}/{JS_FILE}?v={PANEL_VERSION}-{js_mtime}",
        sidebar_title="SwitchBot IR",
        sidebar_icon="mdi:remote",
        require_admin=True,
        config={},
    )
    entry.async_on_unload(lambda: frontend.async_remove_panel(hass, PANEL_URL))

    # --- サービス
    async def _handle_send(call: ServiceCall) -> None:
        try:
            await mgr.send(
                str(call.data["device_id"]),
                str(call.data["command"]),
                call.data["command_type"],
                str(call.data["parameter"]),
            )
        except ManagerError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(DOMAIN, "send", _handle_send, schema=SEND_SCHEMA)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "send"))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        mgr = hass.data.get(DOMAIN, {}).pop("manager", None)
        if mgr is not None:
            mgr.hub.detach()
    return ok
