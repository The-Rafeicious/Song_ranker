# Song Ranker V3.1.2 patch

Apply this patch over V3.1.1. It contains six changed application files.

## Install

1. Stop the local server.
2. Copy the included `pages.py` into your existing `Song_ranker` folder.
3. Merge the included `templates` and `static` folders into the matching folders, replacing the included files.
4. Restart normally and refresh the browser. The shared CSS and JavaScript now use V3.1.2 cache versioning.

The patch includes no database file, migration or new dependency.

## Changes

- **Tag Leaderboard:** the orange banner link opens `/tags`, with the ten highest-impact tags. Tags also appear alongside Songs, Artists and Albums in the ranking navigation.
- **Tag profiles:** clicking a tag opens its own page at `/tag/<name>`, using the shared song/artist/album layout. It includes impact, global rank, average Elo, track count, song highlights, recognisability, tournament results, related tags, proper albums and the complete ranked track list with previews.
- **Tag search:** results match the tag name or related songs, including their title, artist and album. A blank query still browses all tags; the top-ten limit only applies to the leaderboard. Search results and the developer explorer show tag impact scores, and the developer tag table has an Impact column.
- **Song, artist and album rankings:** each page shows at most twenty entries. The Top twenty / Bottom twenty switch sits below the centred title and category selectors. Bottom twenty shows the lowest scores first, keeps the overall rank numbers and preserves the selection when changing ranking categories or reopening its URL.

## Tag impact

Tags use the same calculation as artists and albums:

`1200 + sum(each linked song's Elo - 1200)`

Each song contributes once per tag. Scores are calculated from the current collection rather than saved as duplicate database values. An unused tag has the neutral impact of 1200. Singles still contribute to their tags, but single releases are excluded from album rankings and album totals.

## Validation

- 26 Python backend tests passed, including the existing database/import/track-number checks.
- 86 new interface assertions passed for tag pages, shared impact, related search, ranking limits, switching, reloads, empty tags and small libraries.
- 206 existing interface assertions passed for voting, search, developer tools, profiles, album playback, stats, trivia and tournament completion.
- Python compilation and JavaScript syntax checks passed.

All write tests used copies of the database. Playback tests mocked audio; graphical browser rendering and live audio were not verified here.
