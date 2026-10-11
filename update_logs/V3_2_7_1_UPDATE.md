# Song Ranker V3.2.7.1

Small layout hotfix for **V3.2.7**.

- Song, artist and album names return to the right of their artwork, above
  their metadata, with left alignment.
- Other page titles keep their centred layout. The tag profile is unchanged.
- Entity colours, long-name ellipses, cover playback and profile stats remain.
- The asset version changes so browsers load the corrected layout.

## Install

1. Stop Song Ranker.
2. Copy this ZIP's `Song_ranker` folder contents into your existing V3.2.7
   project, replacing matching files.
3. Start `python main.py` and hard-refresh the browser.

This ZIP includes only changed files. Keep your existing database and all
other project files. No database migration, reset or game changes are included.

## Verification

Checked rendered DOM placement and alignment for song, artist and album
profiles, including empty records and long names. Tag profiles and centred
page headings retain their existing layout. Shared CSS and JavaScript syntax
checks pass. The original database is unchanged. A graphical browser render
was unavailable; this patch has no new preview files.
