from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from anki.consts import (
    CARD_TYPE_LRN,
    CARD_TYPE_RELEARNING,
    CARD_TYPE_REV,
    QUEUE_TYPE_DAY_LEARN_RELEARN,
    QUEUE_TYPE_LRN,
    QUEUE_TYPE_MANUALLY_BURIED,
    QUEUE_TYPE_NEW,
    QUEUE_TYPE_REV,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
)
from aqt import mw

CARD_STATE_ALL = "all"
CARD_STATE_NEW = "new"
CARD_STATE_LEARNING = "learning"
CARD_STATE_RELEARNING = "relearning"
CARD_STATE_REVIEW = "review"
CARD_STATE_SUSPENDED = "suspended"
CARD_STATE_BURIED = "buried"

CARD_STATE_OPTIONS: list[tuple[str, str]] = [
    (CARD_STATE_ALL, "All"),
    (CARD_STATE_NEW, "New"),
    (CARD_STATE_LEARNING, "Learning"),
    (CARD_STATE_RELEARNING, "Relearning"),
    (CARD_STATE_REVIEW, "Review"),
    (CARD_STATE_SUSPENDED, "Suspended"),
    (CARD_STATE_BURIED, "Buried"),
]


@dataclass(frozen=True)
class NoteEntry:
    note_id: int
    note_type: str
    deck_name: str
    card_template: str
    tags: str
    fields: OrderedDict[str, str]
    card_ids: tuple[int, ...]
    card_states: tuple[str, ...]

    def column_value(self, column: str) -> str:
        if column == "Note Type":
            return self.note_type
        if column == "Deck":
            return self.deck_name
        if column == "Tags":
            return self.tags
        if column == "Card Template":
            return self.card_template
        return self.fields.get(column, "")

    def matches_state(self, state: str) -> bool:
        return state == CARD_STATE_ALL or state in self.card_states

    def preview_card_id(self, state: str) -> int | None:
        if state == CARD_STATE_ALL:
            return self.card_ids[0] if self.card_ids else None

        for card_id, card_state in zip(self.card_ids, self.card_states):
            if card_state == state:
                return card_id

        return self.card_ids[0] if self.card_ids else None


@dataclass(frozen=True)
class DeckListData:
    deck_id: int
    deck_name: str
    notes: list[NoteEntry]
    available_columns: list[str]
    note_field_columns: list[str]


def load_deck_list_data(deck_id: int, system_columns: list[str]) -> DeckListData:
    deck = mw.col.decks.get(deck_id)
    deck_name = str(deck["name"])
    search = _search_for_deck(deck_name)
    card_ids = mw.col.find_cards(search)

    notes: list[NoteEntry] = []
    note_positions: dict[int, int] = {}
    field_columns: list[str] = []
    known_field_columns: set[str] = set()

    for card_id in card_ids:
        card = mw.col.get_card(card_id)
        note = mw.col.get_note(card.nid)
        state = _card_state(card)

        if note.id in note_positions:
            entry = notes[note_positions[note.id]]
            notes[note_positions[note.id]] = NoteEntry(
                note_id=entry.note_id,
                note_type=entry.note_type,
                deck_name=entry.deck_name,
                card_template=entry.card_template,
                tags=entry.tags,
                fields=entry.fields,
                card_ids=(*entry.card_ids, int(card.id)),
                card_states=(*entry.card_states, state),
            )
            continue

        model = mw.col.models.get(note.mid)
        note_fields = OrderedDict()
        for field in model["flds"]:
            field_name = str(field["name"])
            note_fields[field_name] = note[field_name]
            if field_name not in known_field_columns:
                known_field_columns.add(field_name)
                field_columns.append(field_name)

        actual_deck = mw.col.decks.get(card.did)
        note_positions[note.id] = len(notes)
        notes.append(
            NoteEntry(
                note_id=note.id,
                note_type=str(model["name"]),
                deck_name=str(actual_deck["name"]),
                card_template=str(card.template()["name"]),
                tags=" ".join(note.tags),
                fields=note_fields,
                card_ids=(int(card.id),),
                card_states=(state,),
            )
        )

    available_columns = list(system_columns) + field_columns
    return DeckListData(
        deck_id=deck_id,
        deck_name=deck_name,
        notes=notes,
        available_columns=available_columns,
        note_field_columns=field_columns,
    )


def _search_for_deck(deck_name: str) -> str:
    escaped = deck_name.replace("\\", "\\\\").replace('"', '\\"')
    return f'deck:"{escaped}"'


def _card_state(card: object) -> str:
    queue = int(card.queue)
    card_type = int(card.type)

    if queue == int(QUEUE_TYPE_SUSPENDED):
        return CARD_STATE_SUSPENDED
    if queue in (int(QUEUE_TYPE_MANUALLY_BURIED), int(QUEUE_TYPE_SIBLING_BURIED)):
        return CARD_STATE_BURIED
    if card_type == int(CARD_TYPE_RELEARNING) or queue == int(QUEUE_TYPE_DAY_LEARN_RELEARN):
        return CARD_STATE_RELEARNING
    if card_type == int(CARD_TYPE_LRN) or queue == int(QUEUE_TYPE_LRN):
        return CARD_STATE_LEARNING
    if card_type == int(CARD_TYPE_REV) or queue == int(QUEUE_TYPE_REV):
        return CARD_STATE_REVIEW
    if queue == int(QUEUE_TYPE_NEW):
        return CARD_STATE_NEW
    return CARD_STATE_NEW
