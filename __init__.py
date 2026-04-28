from __future__ import annotations

from aqt import mw

ADDON_PACKAGE = mw.addonManager.addonFromModule(__name__)

from .addon import register_addon

register_addon()
