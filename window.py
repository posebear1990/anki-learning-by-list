from __future__ import annotations

import html
import re
from collections.abc import Callable

from anki.sound import SoundOrVideoTag
from aqt import mw
from aqt.browser.previewer import Previewer
from aqt.qt import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFontMetrics,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextLayout,
    QTextOption,
    Qt,
    QVBoxLayout,
    QWidget,
    QStyleOptionViewItem,
)
from aqt.sound import av_player
from aqt.utils import qconnect

from .config_store import ConfigStore
from .data import CARD_STATE_ALL, CARD_STATE_OPTIONS, DeckListData, NoteEntry, load_deck_list_data

SOUND_TAG_RE = re.compile(r"\[sound:([^\]]+)\]")
STYLE_BLOCK_RE = re.compile(r"(?is)<style\b[^>]*>.*?</style>")
SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script>")
HTML_BREAK_RE = re.compile(r"(?i)<br\s*/?>|</div>|</p>")
HTML_OPEN_BLOCK_RE = re.compile(r"(?i)<div[^>]*>|<p[^>]*>")
HTML_TAG_RE = re.compile(r"<[^>]+>")
TECHNICAL_AUDIO_ERROR_RE = re.compile(
    r"(?is)(could not find a suitable tls ca certificate bundle|traceback|ssl|certificate bundle)"
)

ROW_NUMBER_COLUMN_LABEL = "#"
ROW_NUMBER_COLUMN_WIDTH = 60
TEXT_COLUMN_MIN_WIDTH = 96
TEXT_COLUMN_MAX_WIDTH = 340
AUDIO_COLUMN_MIN_WIDTH = 44
AUDIO_COLUMN_MAX_WIDTH = 74
TEXT_CELL_HORIZONTAL_PADDING = 8
TEXT_CELL_VERTICAL_PADDING = 6
MIN_ROW_HEIGHT = 34
MAX_ROW_LINES = 6
ROW_HEIGHT_PADDING = 14


class ClampedTextDelegate(QStyledItemDelegate):
    def __init__(self, max_lines: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_lines = max_lines

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        text = style_option.text

        style_option.text = ""
        style = style_option.widget.style() if style_option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, style_option, painter, style_option.widget)

        if not text:
            return

        text_rect = style_option.rect.adjusted(
            TEXT_CELL_HORIZONTAL_PADDING,
            TEXT_CELL_VERTICAL_PADDING // 2,
            -TEXT_CELL_HORIZONTAL_PADDING,
            -(TEXT_CELL_VERTICAL_PADDING // 2),
        )
        if text_rect.width() <= 0 or text_rect.height() <= 0:
            return

        font_metrics = QFontMetrics(style_option.font)
        line_texts = _clamp_text_lines(text, style_option.font, text_rect.width(), self._max_lines)
        if not line_texts:
            return

        line_height = font_metrics.lineSpacing()
        total_height = line_height * len(line_texts)
        baseline_y = text_rect.top() + max(0, (text_rect.height() - total_height) // 2) + font_metrics.ascent()

        painter.save()
        painter.setFont(style_option.font)
        if style_option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(style_option.palette.highlightedText().color())
        else:
            painter.setPen(style_option.palette.text().color())

        for line_text in line_texts:
            line_width = font_metrics.horizontalAdvance(line_text)
            alignment = style_option.displayAlignment
            if alignment & Qt.AlignmentFlag.AlignHCenter:
                x = text_rect.left() + max(0, (text_rect.width() - line_width) // 2)
            elif alignment & Qt.AlignmentFlag.AlignRight:
                x = text_rect.left() + max(0, text_rect.width() - line_width)
            else:
                x = text_rect.left()

            painter.drawText(x, baseline_y, line_text)
            baseline_y += line_height

        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # type: ignore[override]
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        base_size = super().sizeHint(style_option, index)
        text = style_option.text
        if not text:
            return base_size

        column_width = option.rect.width()
        if option.widget is not None and hasattr(option.widget, "columnWidth"):
            try:
                column_width = option.widget.columnWidth(index.column())
            except Exception:
                pass

        available_width = max(1, column_width - (TEXT_CELL_HORIZONTAL_PADDING * 2))
        line_texts = _clamp_text_lines(text, style_option.font, available_width, self._max_lines)
        line_height = QFontMetrics(style_option.font).lineSpacing()
        clamped_height = len(line_texts) * line_height + TEXT_CELL_VERTICAL_PADDING
        max_height = self._max_lines * line_height + TEXT_CELL_VERTICAL_PADDING
        return QSize(base_size.width(), min(max(base_size.height(), clamped_height), max_height))


class SingleCardPreviewer(Previewer):
    def __init__(self, card_id: int, on_close: Callable[[], None]) -> None:
        super().__init__(parent=None, mw=mw, on_close=on_close)
        self._card_id = card_id
        self._last_card_id = 0

    def card(self):  # type: ignore[override]
        if not mw.col:
            return None
        return mw.col.get_card(self._card_id)

    def card_changed(self) -> bool:
        card = self.card()
        if not card:
            return True

        changed = card.id != self._last_card_id
        self._last_card_id = card.id
        return changed


class LearningByListWindow(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Learning by List")
        self.resize(1200, 820)

        self._config_store = ConfigStore()
        self._deck_data: DeckListData | None = None
        self._deck_id: int | None = None
        self._page_size = 200
        self._current_page = 0
        self._status_filter = CARD_STATE_ALL
        self._show_row_numbers = True
        self._visible_columns: list[str] = []
        self._page_entries: list[NoteEntry] = []
        self._audio_field_hints: list[str] = []
        self._default_visible_column_count = 3
        self._page_size_max = 1000
        self._previewer: SingleCardPreviewer | None = None
        self._sidebar_visible = True
        self._sidebar_width = 150
        self._sidebar_collapsed_width = 28

        self._page_indicator_label = QLabel()
        self._page_size_spin = QSpinBox()
        self._prev_button = QPushButton("<")
        self._next_button = QPushButton(">")
        self._status_filter_combo = QComboBox()
        self._sidebar_toggle_button = QPushButton("☰")
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._left_panel = QFrame()
        self._column_panel = QWidget()
        self._column_layout = QVBoxLayout(self._column_panel)
        self._column_scroll = QScrollArea()
        self._bottom_right_spacer = QWidget()
        self._empty_state = QLabel()
        self._table = QTableWidget()
        self._text_delegate = ClampedTextDelegate(MAX_ROW_LINES, self)
        self._column_bulk_toggle_button = QPushButton("Show All")
        self._row_number_checkbox: QCheckBox | None = None
        self._column_checkboxes: dict[str, QCheckBox] = {}

        self._build_ui()

    def load_deck(self, deck_id: int) -> None:
        deck_state = self._config_store.deck_config(deck_id)
        config = deck_state["config"]

        self._deck_id = deck_id
        self._audio_field_hints = [str(item).lower() for item in config["audio_field_name_hints"]]
        self._default_visible_column_count = int(config["default_visible_column_count"])
        self._page_size_max = max(1, int(config["page_size_max"]))

        self._deck_data = load_deck_list_data(deck_id, list(config["system_columns"]))
        self._page_size = min(
            max(1, int(deck_state["deck_config"].get("page_size", config["page_size_default"]))),
            self._page_size_max,
        )
        self._page_size_spin.blockSignals(True)
        self._page_size_spin.setMaximum(self._page_size_max)
        self._page_size_spin.setValue(self._page_size)
        self._page_size_spin.blockSignals(False)

        self._status_filter = str(deck_state["deck_config"].get("status_filter", CARD_STATE_ALL))
        self._show_row_numbers = bool(deck_state["deck_config"].get("show_row_numbers", True))
        self._sync_status_filter_combo()

        requested_columns = list(deck_state["deck_config"].get("visible_columns", []))
        self._visible_columns = self._sanitize_visible_columns(requested_columns)
        self._current_page = 0

        self._rebuild_column_controls()
        self._render_page()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        self._splitter.setChildrenCollapsible(False)
        qconnect(self._splitter.splitterMoved, self._on_splitter_moved)

        self._left_panel.setObjectName("learningByListSidebar")
        self._left_panel.setMaximumWidth(self._sidebar_width)
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("<b>Filter</b>"))
        for state_key, label in CARD_STATE_OPTIONS:
            self._status_filter_combo.addItem(label, state_key)
        qconnect(self._status_filter_combo.currentIndexChanged, self._on_status_filter_changed)
        left_layout.addWidget(self._status_filter_combo)
        left_layout.addWidget(QLabel("<b>Columns</b>"))

        self._column_scroll.setWidgetResizable(True)
        self._column_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._column_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._column_scroll.setWidget(self._column_panel)
        self._column_layout.setContentsMargins(0, 0, 0, 0)
        self._column_layout.setSpacing(6)
        self._column_layout.addStretch(1)
        left_layout.addWidget(self._column_scroll, 1)

        qconnect(self._column_bulk_toggle_button.clicked, self._toggle_all_columns)
        left_layout.addWidget(self._column_bulk_toggle_button)

        self._splitter.addWidget(self._left_panel)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self._empty_state.setWordWrap(True)
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._empty_state.setMargin(18)
        self._empty_state.hide()
        right_layout.addWidget(self._empty_state)

        self._table.setColumnCount(0)
        self._table.setRowCount(0)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.setCornerButtonEnabled(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().hide()
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionsMovable(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setItemDelegate(self._text_delegate)
        qconnect(self._table.cellDoubleClicked, self._open_preview_for_row)
        right_layout.addWidget(self._table, 1)
        self._splitter.addWidget(right_panel)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([self._sidebar_width, 1050])
        root.addWidget(self._splitter, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)
        qconnect(self._prev_button.clicked, self._go_previous_page)
        qconnect(self._next_button.clicked, self._go_next_page)
        qconnect(self._sidebar_toggle_button.clicked, self._toggle_sidebar)
        self._page_size_spin.setRange(1, 1000)
        self._page_size_spin.setValue(self._page_size)
        self._page_size_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._page_size_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_size_spin.setFixedWidth(64)
        self._prev_button.setFixedWidth(28)
        self._next_button.setFixedWidth(28)
        self._page_indicator_label.setMinimumWidth(40)
        self._page_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_toggle_button.setFixedHeight(28)
        self._bottom_right_spacer.setFixedHeight(28)
        bottom_bar.addWidget(self._sidebar_toggle_button)
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(self._prev_button)
        bottom_bar.addWidget(self._page_indicator_label)
        bottom_bar.addWidget(self._next_button)
        bottom_bar.addSpacing(12)
        bottom_bar.addWidget(self._page_size_spin)
        bottom_bar.addWidget(QLabel("rows / page"))
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(self._bottom_right_spacer)
        qconnect(self._page_size_spin.valueChanged, self._on_page_size_changed)
        root.addLayout(bottom_bar)

        self.setStyleSheet(
            """
            QDialog {
                background: #f6f7f9;
            }
            QFrame#learningByListSidebar {
                background: #ffffff;
                border: 1px solid #d9dde3;
                border-radius: 12px;
            }
            QFrame#learningByListSidebar QCheckBox {
                spacing: 6px;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #d9dde3;
                border-radius: 12px;
                alternate-background-color: #fafbfc;
                gridline-color: transparent;
                padding: 4px;
            }
            QTableWidget::item {
                border: none;
                padding: 8px 10px;
            }
            QTableWidget::item:selected {
                background: rgba(80, 120, 255, 0.12);
                color: #1f2937;
            }
            QPushButton[audioButton="true"] {
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
                padding: 0;
                border: 1px solid #d0d7e2;
                border-radius: 9px;
                background: #ffffff;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton[audioButton="true"]:hover {
                background: #eef4ff;
            }
            """
        )
        self._sync_sidebar_toggle_button()

    def _rebuild_column_controls(self) -> None:
        while self._column_layout.count():
            item = self._column_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._column_checkboxes.clear()
        self._row_number_checkbox = None
        if not self._deck_data:
            self._update_column_bulk_button()
            self._column_layout.addStretch(1)
            return

        self._row_number_checkbox = QCheckBox(ROW_NUMBER_COLUMN_LABEL)
        self._row_number_checkbox.setChecked(self._show_row_numbers)
        qconnect(self._row_number_checkbox.toggled, self._toggle_row_numbers)
        self._column_layout.addWidget(self._row_number_checkbox)

        for column in self._deck_data.available_columns:
            checkbox = QCheckBox(self._format_column_caption(column))
            checkbox.setChecked(column in self._visible_columns)
            qconnect(checkbox.toggled, lambda checked, col=column: self._toggle_column(col, checked))
            self._column_layout.addWidget(checkbox)
            self._column_checkboxes[column] = checkbox

        self._column_layout.addStretch(1)
        self._update_column_bulk_button()

    def _toggle_row_numbers(self, checked: bool) -> None:
        self._show_row_numbers = checked
        self._persist_state()
        self._render_page()

    def _toggle_column(self, column: str, checked: bool) -> None:
        if checked and column not in self._visible_columns:
            self._visible_columns.append(column)
        elif not checked and column in self._visible_columns:
            self._visible_columns = [item for item in self._visible_columns if item != column]

        self._persist_state()
        self._render_page()

    def _toggle_all_columns(self) -> None:
        if not self._deck_data:
            return

        if self._all_columns_selected():
            self._show_row_numbers = False
            self._visible_columns = []
        else:
            self._show_row_numbers = True
            self._visible_columns = list(self._deck_data.available_columns)

        self._sync_column_checkboxes()
        self._persist_state()
        self._render_page()

    def _sync_column_checkboxes(self) -> None:
        if self._row_number_checkbox is not None:
            self._row_number_checkbox.blockSignals(True)
            self._row_number_checkbox.setChecked(self._show_row_numbers)
            self._row_number_checkbox.blockSignals(False)

        for column, checkbox in self._column_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(column in self._visible_columns)
            checkbox.blockSignals(False)

        self._update_column_bulk_button()

    def _on_page_size_changed(self, value: int) -> None:
        self._page_size = max(1, min(int(value), self._page_size_max))
        self._current_page = 0
        self._persist_state()
        self._render_page()

    def _on_status_filter_changed(self, index: int) -> None:
        state = self._status_filter_combo.itemData(index)
        if not state:
            return

        self._status_filter = str(state)
        self._current_page = 0
        self._persist_state()
        self._render_page()

    def _go_previous_page(self) -> None:
        if self._current_page <= 0:
            return
        self._current_page -= 1
        self._render_page()

    def _go_next_page(self) -> None:
        notes = self._filtered_notes()
        if not notes:
            return
        if (self._current_page + 1) * self._page_size >= len(notes):
            return
        self._current_page += 1
        self._render_page()

    def _render_page(self) -> None:
        if not self._deck_data:
            self._table.hide()
            self._empty_state.hide()
            return

        notes = self._filtered_notes()
        if not notes:
            self._show_empty_state("No notes match the selected status filter.")
            self._page_indicator_label.setText("0/0")
            self._prev_button.setEnabled(False)
            self._next_button.setEnabled(False)
            return

        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(notes))
        page_items = notes[start:end]
        self._page_entries = page_items

        if not self._show_row_numbers and not self._visible_columns:
            self._show_empty_state("No columns are visible. Enable at least one column on the left.")
        else:
            self._empty_state.hide()
            self._table.show()
            self._render_table(page_items, start)

        page_count = max(1, (len(notes) + self._page_size - 1) // self._page_size)
        self._page_indicator_label.setText(f"{self._current_page + 1}/{page_count}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(end < len(notes))

    def _render_table(self, entries: list[NoteEntry], start_index: int) -> None:
        display_columns = list(self._visible_columns)
        column_offset = 1 if self._show_row_numbers else 0

        self._table.clearContents()
        self._table.setColumnCount(column_offset + len(display_columns))
        self._table.setRowCount(len(entries))

        for row_index, entry in enumerate(entries):
            if self._show_row_numbers:
                number_item = QTableWidgetItem(str(start_index + row_index + 1))
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                self._table.setItem(row_index, 0, number_item)

            for column_index, column in enumerate(display_columns, start=column_offset):
                self._populate_cell(row_index, column_index, column, entry.column_value(column))

        if self._show_row_numbers:
            self._table.setColumnWidth(0, ROW_NUMBER_COLUMN_WIDTH)

        for column_index, column in enumerate(display_columns, start=column_offset):
            self._table.resizeColumnToContents(column_index)
            width = self._table.columnWidth(column_index)
            if self._is_audio_column(column):
                self._table.setColumnWidth(column_index, min(max(width, AUDIO_COLUMN_MIN_WIDTH), AUDIO_COLUMN_MAX_WIDTH))
            else:
                self._table.setColumnWidth(column_index, min(max(width, TEXT_COLUMN_MIN_WIDTH), TEXT_COLUMN_MAX_WIDTH))

        self._table.resizeRowsToContents()
        max_row_height = self._max_row_height()
        for row_index in range(self._table.rowCount()):
            self._table.setRowHeight(
                row_index,
                max(MIN_ROW_HEIGHT, min(self._table.rowHeight(row_index), max_row_height)),
            )

    def _populate_cell(self, row_index: int, column_index: int, column: str, raw_value: str) -> None:
        sounds, text = _parse_field_content(raw_value)
        if self._is_audio_column(column) and not sounds and _is_technical_audio_error(text):
            text = ""

        if not sounds:
            item = QTableWidgetItem(text or "—")
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row_index, column_index, item)
            return

        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        for sound in sounds:
            button = QPushButton("▶")
            button.setProperty("audioButton", True)
            button.setToolTip(sound)
            qconnect(button.clicked, lambda _checked=False, tag=sound: self._play_sound(tag))
            layout.addWidget(button)

        if text:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            label.setWordWrap(True)
            label.setMaximumHeight(self._max_row_height() - 4)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label, 1)
        else:
            layout.addStretch(1)

        self._table.setCellWidget(row_index, column_index, wrapper)

    def _show_empty_state(self, text: str) -> None:
        self._page_entries = []
        self._empty_state.setText(text)
        self._empty_state.show()
        self._table.hide()

    def _sanitize_visible_columns(self, columns: list[str]) -> list[str]:
        if not self._deck_data:
            return []

        available = set(self._deck_data.available_columns)
        sanitized = [column for column in columns if column in available]
        if sanitized:
            return sanitized
        return self._default_columns()

    def _default_columns(self) -> list[str]:
        if not self._deck_data:
            return []

        note_fields = list(self._deck_data.note_field_columns)
        if note_fields:
            return note_fields[: self._default_visible_column_count]
        return self._deck_data.available_columns[: self._default_visible_column_count]

    def _persist_state(self) -> None:
        if self._deck_id is None:
            return
        self._config_store.save_deck_state(
            self._deck_id,
            visible_columns=self._visible_columns,
            page_size=self._page_size,
            status_filter=self._status_filter,
            show_row_numbers=self._show_row_numbers,
        )

    def _play_sound(self, tag: str) -> None:
        av_player.play_tags([SoundOrVideoTag(tag)])

    def _format_column_caption(self, column: str) -> str:
        return column

    def _is_audio_column(self, column: str) -> bool:
        return any(hint in column.lower() for hint in self._audio_field_hints)

    def _all_columns_selected(self) -> bool:
        if not self._deck_data:
            return False
        return self._show_row_numbers and len(self._visible_columns) == len(self._deck_data.available_columns)

    def _update_column_bulk_button(self) -> None:
        self._column_bulk_toggle_button.setText("Invert" if self._all_columns_selected() else "Show All")

    def _max_row_height(self) -> int:
        return max(MIN_ROW_HEIGHT, self._table.fontMetrics().lineSpacing() * MAX_ROW_LINES + ROW_HEIGHT_PADDING)

    def _filtered_notes(self) -> list[NoteEntry]:
        if not self._deck_data:
            return []
        return [entry for entry in self._deck_data.notes if entry.matches_state(self._status_filter)]

    def _sync_status_filter_combo(self) -> None:
        index = self._status_filter_combo.findData(self._status_filter)
        if index < 0:
            self._status_filter = CARD_STATE_ALL
            index = self._status_filter_combo.findData(self._status_filter)
        self._status_filter_combo.blockSignals(True)
        self._status_filter_combo.setCurrentIndex(max(index, 0))
        self._status_filter_combo.blockSignals(False)

    def _open_preview_for_row(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._page_entries):
            return

        card_id = self._page_entries[row].preview_card_id(self._status_filter)
        if not card_id:
            return

        if self._previewer is not None:
            self._previewer.close()

        self._previewer = SingleCardPreviewer(int(card_id), self._on_previewer_closed)
        self._previewer.open()

    def _on_previewer_closed(self) -> None:
        self._previewer = None

    def _toggle_sidebar(self, _checked: bool = False) -> None:
        if self._sidebar_visible:
            self._sidebar_width = max(120, self._left_panel.width())
            self._left_panel.hide()
            self._splitter.setSizes([0, 1])
            self._sidebar_visible = False
        else:
            self._left_panel.show()
            self._left_panel.setMaximumWidth(self._sidebar_width)
            self._splitter.setSizes([self._sidebar_width, 1050])
            self._sidebar_visible = True

        self._sync_sidebar_toggle_button()

    def _sync_sidebar_toggle_button(self) -> None:
        width = self._sidebar_width if self._sidebar_visible else self._sidebar_collapsed_width
        self._sidebar_toggle_button.setFixedWidth(width)
        self._bottom_right_spacer.setFixedWidth(width)
        self._sidebar_toggle_button.setToolTip("Collapse panel" if self._sidebar_visible else "Expand panel")

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        if not self._sidebar_visible:
            return
        self._sidebar_width = max(120, self._left_panel.width())
        self._sync_sidebar_toggle_button()


def _parse_field_content(raw_value: str) -> tuple[list[str], str]:
    sounds = SOUND_TAG_RE.findall(raw_value)
    text = SOUND_TAG_RE.sub("", raw_value)
    text = STYLE_BLOCK_RE.sub("", text)
    text = SCRIPT_BLOCK_RE.sub("", text)
    text = HTML_BREAK_RE.sub("\n", text)
    text = HTML_OPEN_BLOCK_RE.sub("", text)
    text = html.unescape(HTML_TAG_RE.sub("", text))
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return sounds, text.strip()


def _is_technical_audio_error(text: str) -> bool:
    return bool(TECHNICAL_AUDIO_ERROR_RE.search(text))


def _clamp_text_lines(text: str, font, max_width: int, max_lines: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []

    layout = QTextLayout(normalized, font)
    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(text_option)

    line_ranges: list[tuple[int, int]] = []
    overflow = False

    layout.beginLayout()
    try:
        while True:
            line = layout.createLine()
            if not line.isValid():
                break

            line.setLineWidth(max_width)
            line_ranges.append((line.textStart(), line.textLength()))
            if len(line_ranges) > max_lines:
                overflow = True
                break
    finally:
        layout.endLayout()

    if not line_ranges:
        return []

    font_metrics = QFontMetrics(font)
    visible_ranges = line_ranges[:max_lines]
    clamped_lines: list[str] = []

    for index, (start, length) in enumerate(visible_ranges):
        if index == max_lines - 1 and overflow:
            remaining = normalized[start:].replace("\n", " ")
            clamped_lines.append(font_metrics.elidedText(remaining, Qt.TextElideMode.ElideRight, max_width))
            continue

        line_text = normalized[start : start + length].replace("\n", " ").strip()
        clamped_lines.append(line_text)

    return clamped_lines
