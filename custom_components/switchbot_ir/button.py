"""Button platform: every registered item becomes a button entity."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .errors import ManagerError

_LOGGER = logging.getLogger(__name__)


DeviceFor = Callable[[dict[str, Any]], dict[str, Any]]
"""登録内容(item)から、そのボタンが属するデバイスの情報を返す関数。

返す辞書は {"identifiers": {(DOMAIN, id)}, "name": ..., "manufacturer": ..., "model": ...}。
"""


def unique_id(key: str) -> str:
    return f"{DOMAIN}_{key}"


class PanelButton(ButtonEntity):
    """パネルで登録した1件(信号・ボタン)に対応するボタンエンティティ。"""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(
        self,
        press: Callable[[str], Awaitable[None]],
        key: str,
        item: dict[str, Any],
        device: dict[str, Any],
    ) -> None:
        self._press = press
        self.key = key
        self._attr_unique_id = unique_id(key)
        self._apply(item, device)

    def _apply(self, item: dict[str, Any], device: dict[str, Any]) -> None:
        self._attr_name = item["alias"]
        self._attr_icon = item.get("icon") or None
        self._attr_device_info = DeviceInfo(**device)

    @callback
    def update_item(self, item: dict[str, Any], device: dict[str, Any]) -> None:
        self._apply(item, device)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_press(self) -> None:
        try:
            await self._press(self.key)
        except ManagerError as err:
            raise HomeAssistantError(str(err)) from err


class ButtonHub:
    """ボタンエンティティの追加・更新・削除をまとめて扱う。"""

    def __init__(
        self,
        hass: HomeAssistant,
        press: Callable[[str], Awaitable[None]],
        device_for: DeviceFor,
    ) -> None:
        self.hass = hass
        self._press = press
        self._device_for = device_for
        self._entry: ConfigEntry | None = None
        self._add: AddEntitiesCallback | None = None
        self.entities: dict[str, PanelButton] = {}

    # ---- プラットフォームとの接続 -------------------------------------
    def attach(
        self,
        entry: ConfigEntry,
        add_entities: AddEntitiesCallback,
        items: dict[str, dict[str, Any]],
    ) -> None:
        self._entry = entry
        self._add = add_entities
        for key, item in items.items():
            self._register(key, item)
        add_entities([self._make(key, item) for key, item in items.items()])

    def detach(self) -> None:
        self._entry = None
        self._add = None
        self.entities.clear()

    # ---- 内部 ------------------------------------------------------------
    def _register(self, key: str, item: dict[str, Any]) -> None:
        """エンティティIDが「button.<key>」になるよう、先にレジストリへ登録しておく。"""
        er.async_get(self.hass).async_get_or_create(
            "button",
            DOMAIN,
            unique_id(key),
            suggested_object_id=key,
            config_entry=self._entry,
            original_name=item["alias"],
        )

    def _make(self, key: str, item: dict[str, Any]) -> PanelButton:
        ent = PanelButton(self._press, key, item, self._device_for(item))
        self.entities[key] = ent
        return ent

    # ---- 操作 ------------------------------------------------------------
    def entity_id(self, key: str) -> str | None:
        """レジストリ上の実際のエンティティID(HAの画面で変更されていても追従する)。"""
        return er.async_get(self.hass).async_get_entity_id("button", DOMAIN, unique_id(key))

    def is_taken(self, object_id: str) -> bool:
        entity_id = f"button.{object_id}"
        return (
            er.async_get(self.hass).async_is_registered(entity_id)
            or self.hass.states.get(entity_id) is not None
        )

    # ---- エリア(エンティティレジストリのarea_idが、そのまま正) --------------------
    def area_exists(self, area_id: str) -> bool:
        return ar.async_get(self.hass).async_get_area(area_id) is not None

    def area_of(self, key: str) -> str:
        """現在のエリアID(HAの画面で変更されていても追従する)。未設定は空文字。"""
        registry = er.async_get(self.hass)
        entity_id = self.entity_id(key)
        entry = registry.async_get(entity_id) if entity_id else None
        return (entry.area_id if entry is not None else None) or ""

    def set_area(self, key: str, area_id: str | None) -> None:
        """エリアを設定する(空文字・Noneで解除)。"""
        registry = er.async_get(self.hass)
        entity_id = self.entity_id(key)
        entry = registry.async_get(entity_id) if entity_id else None
        desired = area_id or None
        if entry is not None and entry.area_id != desired:
            registry.async_update_entity(entity_id, area_id=desired)

    def add(self, key: str, item: dict[str, Any]) -> None:
        if self._add is None:
            raise ManagerError("ボタンのプラットフォームが読み込まれていません", 503)
        self._register(key, item)
        self._add([self._make(key, item)])

    def update(self, key: str, item: dict[str, Any]) -> None:
        ent = self.entities.get(key)
        if ent is not None:
            ent.update_item(item, self._device_for(item))
        self.sync_device(key, item)

    # ---- デバイス(ボタンを、家電・リモコンごとのデバイスにまとめる) -----------------
    def sync_device(self, key: str, item: dict[str, Any]) -> None:
        """ボタンが属するデバイスを、登録内容に合わせる(デバイス名の変更・付け替えにも対応)。"""
        if self._entry is None:
            return
        registry = er.async_get(self.hass)
        entity_id = self.entity_id(key)
        entry = registry.async_get(entity_id) if entity_id else None
        if entry is None:
            return
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self._entry.entry_id, **self._device_for(item)
        )
        previous = entry.device_id
        if previous != device.id:
            registry.async_update_entity(entity_id, device_id=device.id)
            self._drop_empty_device(previous)

    def sync_devices(self, items: dict[str, dict[str, Any]]) -> None:
        """全ボタンのデバイスを、登録内容に合わせる(取得結果・名称が変わったとき)。"""
        for key, item in items.items():
            ent = self.entities.get(key)
            if ent is not None:
                ent.update_item(item, self._device_for(item))
            self.sync_device(key, item)

    def _drop_empty_device(self, device_id: str | None) -> None:
        """エンティティが1つもなくなったデバイスは、削除する。"""
        if not device_id:
            return
        if er.async_entries_for_device(
            er.async_get(self.hass), device_id, include_disabled_entities=True
        ):
            return
        dr.async_get(self.hass).async_remove_device(device_id)

    def remove(self, key: str) -> str:
        """エンティティとレジストリ登録を削除する。戻り値: removed / absent"""
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("button", DOMAIN, unique_id(key))
        entry = registry.async_get(entity_id) if entity_id else None
        device_id = entry.device_id if entry is not None else None
        ent = self.entities.pop(key, None)
        result = "absent"
        if entity_id is not None:
            registry.async_remove(entity_id)  # 生きているエンティティも、これで取り除かれる
            self._drop_empty_device(device_id)
            result = "removed"
        elif ent is not None and ent.hass is not None:
            self.hass.async_create_task(ent.async_remove())
            result = "removed"
        return result


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    mgr = hass.data[DOMAIN]["manager"]
    mgr.hub.attach(entry, async_add_entities, mgr.ledger.buttons)
