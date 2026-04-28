# Learning by List

An Anki add-on that adds a `Learning by List` button to the deck overview page.

## Current behavior

- Injects a `Learning by List` button into the bottom-right corner of the deck overview screen.
- Opens a separate list-style page for the current deck.
- Shows configurable columns with live hide/show checkboxes.
- Renders audio fields as compact `▶` play buttons when `[sound:...]` tags are present.
- Defaults to 200 rows per page and persists per-deck page size and visible columns.
- Uses a table-like list view without visible grid lines.

## Install locally

On macOS/Linux, you can symlink this folder into:

`~/Library/Application Support/Anki2/addons21/ankilearningbylist`

Then restart Anki.

## Notes

- The list is note-based, not card-based. Multiple cards from the same note are collapsed into one row.
- Fields are shown in a table-like list rather than stacked cards.
