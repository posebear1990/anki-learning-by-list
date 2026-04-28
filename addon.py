from __future__ import annotations

from typing import Any

import aqt
from aqt import gui_hooks, mw
from aqt.utils import showWarning

from .window import LearningByListWindow

BUTTON_COMMAND = "learning-by-list:open"
_window: LearningByListWindow | None = None


def register_addon() -> None:
    gui_hooks.webview_will_set_content.append(_inject_button)
    gui_hooks.webview_did_receive_js_message.append(_handle_js_message)


def _inject_button(web_content: aqt.webview.WebContent, context: Any) -> None:
    if not isinstance(context, aqt.overview.OverviewBottomBar):
        return

    web_content.head += BUTTON_CSS
    web_content.body += BUTTON_HTML


def _handle_js_message(
    handled: tuple[bool, Any],
    message: str,
    context: Any,
) -> tuple[bool, Any]:
    if message != BUTTON_COMMAND:
        return handled

    if not mw.col:
        showWarning("Please open a profile and collection first.")
        return (True, None)

    _open_learning_by_list()
    return (True, None)


def _open_learning_by_list() -> None:
    global _window

    current_deck = mw.col.decks.current()
    deck_id = int(current_deck["id"])

    if _window is None:
        _window = LearningByListWindow(parent=mw)

    _window.load_deck(deck_id)
    _window.show()
    _window.raise_()
    _window.activateWindow()


BUTTON_HTML = f"""
<div class="learning-by-list-anchor">
  <button
    id="learning-by-list-button"
    class="learning-by-list-button"
    onclick="pycmd('{BUTTON_COMMAND}')"
  >
    Learning by List
  </button>
</div>
"""

BUTTON_CSS = """
<style>
.learning-by-list-anchor {
  position: absolute;
  right: 16px;
  bottom: 14px;
  z-index: 999;
}

.learning-by-list-button {
  min-height: 28px;
  padding: 0 12px;
  border: 1px solid var(--border, #909090);
  border-radius: 999px;
  background: var(--canvas, #ffffff);
  color: inherit;
  cursor: pointer;
  font-weight: 600;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.learning-by-list-button:hover {
  background: rgba(80, 120, 255, 0.08);
}
</style>
"""
