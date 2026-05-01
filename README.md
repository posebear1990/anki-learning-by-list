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

On macOS/Linux, symlink this project into Anki's add-ons folder under the stable module name:

`~/Library/Application Support/Anki2/addons21/ankilearningbylist`

Then restart Anki.

Example:

```bash
ln -s /absolute/path/to/anki-learning-by-list \
  ~/Library/Application\ Support/Anki2/addons21/ankilearningbylist
```

## Packaging

This project keeps three names separate on purpose:

- Repository name: `anki-learning-by-list`
- Display name: `Learning by List`
- Stable module/package name: `ankilearningbylist`

To build a local release package:

```bash
./package.sh
```

The script creates `dist/anki-learning-by-list.ankiaddon` and only includes release files. It excludes local state like `meta.json`, `__pycache__`, and development-only folders.

## Release Materials

- Listing draft: [ANKIWEB_DESCRIPTION.md](./ANKIWEB_DESCRIPTION.md)
- Review checklist: [RELEASE_REVIEW.md](./RELEASE_REVIEW.md)
- Changelog: [CHANGELOG.md](./CHANGELOG.md)
- License: [LICENSE](./LICENSE)
- Screenshots: [screenshots/README.md](./screenshots/README.md)

## Notes

- The list is note-based, not card-based. Multiple cards from the same note are collapsed into one row.
- Fields are shown in a table-like list rather than stacked cards.
