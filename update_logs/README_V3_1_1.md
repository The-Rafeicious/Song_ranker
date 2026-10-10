# Song Ranker V3.1.1 patch

Install this on top of V3.1. It contains seven application files, including the backend checks; it is not just a template update.

## Install

1. Stop your local server.
2. Copy `dev.py`, `services.py` and the new `track_numbers.py` into your existing `Song_ranker` folder.
3. Merge the included `templates` and `static` folders into the existing folders, replacing the matching files.
4. Start the server normally and refresh the browser. The asset URLs now use V3.1.1 cache versioning.

No database file or new dependency is included. Restarting installs the SQLite checks automatically. Existing songs, scores and brackets are retained.

## Track numbers

Use the original album's track positions. For example, keeping tracks 1, 2, 4 and 7 is fine; do not renumber them to 1, 2, 3 and 4. Both the track list and album preview queue support gaps.

Numbers must be positive whole numbers, or blank when unknown. Several unknown positions can be blank. A numbered position can belong to only one song within the same album. The same number is allowed on a different album. The API checks additions, edits and moves between albums in one transaction; SQLite also guards direct inserts and updates. Failed edits retain the existing song and its links.

Old duplicate or invalid positions are not guessed, deleted or silently renumbered. Open **Dev → Database → Database integrity** to see affected songs and edit them. Existing conflicting databases can still start.

Multi-disc releases need a separate disc field to preserve positions such as Disc 1 / Track 1 and Disc 2 / Track 1. This patch deliberately leaves the imported position blank for multi-disc releases rather than invent an album-wide numbering scheme. The import result shows the source disc/track information. An existing explicitly supplied position is retained when Apple cannot supply an unambiguous album-wide position.

## Apple import

The previous import saved only these five values: song title, artist name, album name, artwork URL and preview URL. Adding a song created/linked its album and artists; it did not import the entire album.

This patch also saves the following into existing fields when Apple returns them:

| Apple value | Saved location |
|---|---|
| Track position, for single-disc releases | Song track number |
| Release date | Album release date, only when it is blank |
| Primary genre | Linked tag |

Album links now return the album's song suggestions. Use the existing Add buttons to choose the songs you want; leaving out disliked tracks does not alter the remaining numbers. Country-specific Apple Music links retain their country during lookup. Search results show the extra metadata before adding. Pasting a single-song Apple link into the song editor also refreshes this metadata while retaining custom tags.

Useful future additions are separate disc numbers, track duration and Apple song/album IDs for more precise matching or updating existing songs. No prices, currency, sales data or unused metadata columns were added.

Apple documentation: [Search result fields](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/UnderstandingSearchResults.html) and [album/track lookups](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/LookupExamples.html).

## Interface fixes

- Album preview navigation is on the cover edges. The centre controls play/pause. Arrows appear on hover or keyboard focus and remain visible on touch devices.
- Global Stats and Match History have green dropdown links matching their pages.
- Tournament category selections use salmon pink.
- The tournament game uses the shared two-card voting layout, cover playback, artist/album/song links and shared volume. Blind votes reveal identities and results inline. All bracket sizes, scopes, saved tournaments, resume, points, champions and archive links remain available. Tournament votes do not change regular Elo.
- Duplicate track-number errors appear inside the song editor so the conflict is visible while editing.

## Validation

Passed 26 backend tests and 215 interface assertions, including SQLite enforcement, numbering gaps, rollback on conflicting edits, original metadata preservation, full eight-track tournament completion, standard/blind resume, link targets and album preview navigation. JavaScript syntax also passed.

Tests used separate database copies. Remote Apple responses and media playback were simulated; live Apple imports/audio and full browser visual rendering were not verified.
