"""Constants for SwitchBot IR (cloud)."""
from __future__ import annotations

import re

DOMAIN = "switchbot_ir"

API_BASE = "https://api.switch-bot.com"
DAILY_LIMIT = 10000  # SwitchBot API v1.1 の1日あたりの呼び出し上限(公式README)

SLUG_RE = re.compile(r"^[a-z0-9_]{1,40}$")
ICON_RE = re.compile(r"^[a-z0-9_-]+:[a-z0-9_-]+$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
COMMAND_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")  # 標準コマンド名(turnOn など)

CMD_CUSTOM = "customize"  # SwitchBotアプリで学習させたボタン(ボタン名をそのまま送る)
CMD_STANDARD = "command"  # 標準コマンド(turnOn など)
COMMAND_TYPES = (CMD_CUSTOM, CMD_STANDARD)

SLUG_PREFIX = "switchbot_"

PANEL_URL = "switchbot-ir"
STATIC_URL = "/switchbot_ir_static"
PANEL_VERSION = "1.0.0"

STORAGE_KEY = DOMAIN

STORAGE_VERSION = 1
