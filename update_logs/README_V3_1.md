# Song Ranker V3.1 update

This patch installs over the V3 project in Song_Ranker_Updated.zip.

## Install

1. Stop the local server.
2. Copy the included `templates` and `static` folders into your existing `Song_ranker` folder. Merge the folders and replace the included files. Include the new `templates/components.html` file.
3. Start the server normally and refresh the browser.

The patch contains 12 application files. It adds no dependencies and requires no Python or database changes. Your songs, scores, trivia results and tournaments stay in your existing database.

## Changes

- Global Stats: shared colourful cards, Elo distribution, collection records, rivalry thumbnails, album averages, trivia and tournament summaries, tags and recent activity. Album totals still exclude singles.
- Match History: compact square thumbnails and All / Blind / Non-blind filters.
- Recognisability: compact top and bottom lists, keeping the trivia high score and attempt/point counts.
- Tournament Stats: top and bottom ten tracks for Overall, Points, Win Rate, Championships and Appearances. Unplayed tracks are excluded from win-rate lists. The complete bracket archive remains below the highlights, including direct links to individual tournaments.
- Tags: integrated into Search. The Tags category matches only tag names; an empty query browses all tags. Selecting a tag shows its linked songs, with a clear-filter control and related tags. Old tag URLs open the same search interface.
- Dev maintenance: search by title, artist, album or #ID, then select a song to load its current Elo or trivia values. Enter in the search field selects a result; saving remains a separate action.
- Album and artist profiles: the song page's shared layout, entity colours, track highlights, recognisability and tournament records. Artists retain their albums and full ranked discography.
- Album cover player: cycles through available previews in track order, playing ten seconds per track. Includes pause, previous/next, current-track display, shared volume, unavailable-preview handling and individual track playback. Albums also have Ranked / Track order controls.
- Trivia: the hidden and revealed covers stay square.
- Shared CSS and JavaScript have V3.1 cache versioning.

## Validation

Passed 13 backend tests, 76 existing interface assertions, 87 V3.1 interface assertions and the JavaScript syntax check. Checks used a separate test database; preview playback was simulated. Full browser rendering and live remote audio playback were not verified.
