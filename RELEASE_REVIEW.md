# Release Review

## Planned Release

- Version: `0.1.0`
- Display name: `Learning by List`
- Repository: <https://github.com/posebear1990/anki-learning-by-list>
- Release package: [dist/anki-learning-by-list.ankiaddon](/Users/posebear1990/workspace/anki-learning-by-list/dist/anki-learning-by-list.ankiaddon)

## Ready Now

- Clean packaging script exists: [package.sh](/Users/posebear1990/workspace/anki-learning-by-list/package.sh)
- AnkiWeb draft copy exists: [ANKIWEB_DESCRIPTION.md](/Users/posebear1990/workspace/anki-learning-by-list/ANKIWEB_DESCRIPTION.md)
- Changelog exists: [CHANGELOG.md](/Users/posebear1990/workspace/anki-learning-by-list/CHANGELOG.md)
- MIT license exists: [LICENSE](/Users/posebear1990/workspace/anki-learning-by-list/LICENSE)
- Local syntax check passes via `python3 -m py_compile`
- Release archive validation passes
- Local packaging verified on this machine
- Local Anki version detected: `25.02.7`

## Minimal Publish Steps

- Confirm the AnkiWeb listing title should be `Learning by List`
- Review the listing copy in [ANKIWEB_DESCRIPTION.md](/Users/posebear1990/workspace/anki-learning-by-list/ANKIWEB_DESCRIPTION.md)
- Confirm `posebear1990` is the desired public author name in [manifest.json](/Users/posebear1990/workspace/anki-learning-by-list/manifest.json:1)
- Upload [dist/anki-learning-by-list.ankiaddon](/Users/posebear1990/workspace/anki-learning-by-list/dist/anki-learning-by-list.ankiaddon) to AnkiWeb
- Paste the prepared listing copy from [ANKIWEB_DESCRIPTION.md](/Users/posebear1990/workspace/anki-learning-by-list/ANKIWEB_DESCRIPTION.md)
- Upload the prepared screenshots in the order documented in [screenshots/README.md](/Users/posebear1990/workspace/anki-learning-by-list/screenshots/README.md)

## Optional Manual Check

- Open Anki and verify the main flow if you want one last local sanity check:
  - the `Learning by List` button appears on the deck overview page
  - the list window opens for the current deck
  - visible columns can be changed
  - page size and filter state persist after reopening
  - audio play buttons work on notes with `[sound:...]`
- Review the prepared screenshots in [screenshots/README.md](/Users/posebear1990/workspace/anki-learning-by-list/screenshots/README.md)

## Notes

- The package intentionally excludes `meta.json`, `__pycache__`, `backups/`, and other local-only files.
- For local development, Anki still loads the add-on through the stable module path `ankilearningbylist`.
- On AnkiWeb installs, Anki will use the add-on ID folder name automatically.
- The screenshots are meant to be uploaded to the AnkiWeb listing separately, not embedded in the `.ankiaddon` package.
