from __future__ import annotations

from copy import deepcopy
from typing import Any

from aqt import mw

from . import ADDON_PACKAGE
from .data import CARD_STATE_ALL

DEFAULT_CONFIG: dict[str, Any] = {
    "page_size_default": 200,
    "page_size_max": 1000,
    "default_visible_column_count": 3,
    "audio_field_name_hints": ["audio", "sound", "pronunciation", "voice"],
    "system_columns": ["Note Type", "Deck", "Tags", "Card Template"],
    "per_deck": {},
}


class ConfigStore:
    def load(self) -> dict[str, Any]:
        config = mw.addonManager.getConfig(ADDON_PACKAGE) or {}
        merged = deepcopy(DEFAULT_CONFIG)
        merged.update(config)
        merged["per_deck"] = {**DEFAULT_CONFIG["per_deck"], **config.get("per_deck", {})}
        return merged

    def save(self, config: dict[str, Any]) -> None:
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)

    def deck_config(self, deck_id: int) -> dict[str, Any]:
        config = self.load()
        deck_key = str(deck_id)
        per_deck = config.setdefault("per_deck", {})
        if deck_key not in per_deck:
            per_deck[deck_key] = {
                "visible_columns": [],
                "page_size": int(config["page_size_default"]),
                "status_filter": CARD_STATE_ALL,
                "show_row_numbers": True,
            }
            self.save(config)
        return {
            "config": config,
            "deck_key": deck_key,
            "deck_config": dict(per_deck[deck_key]),
        }

    def save_deck_state(
        self,
        deck_id: int,
        *,
        visible_columns: list[str],
        page_size: int,
        status_filter: str,
        show_row_numbers: bool,
    ) -> None:
        config = self.load()
        deck_key = str(deck_id)
        config.setdefault("per_deck", {})
        config["per_deck"][deck_key] = {
            "visible_columns": visible_columns,
            "page_size": page_size,
            "status_filter": status_filter,
            "show_row_numbers": show_row_numbers,
        }
        self.save(config)
