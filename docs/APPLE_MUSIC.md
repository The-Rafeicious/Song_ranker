# Apple Music adding and requests — V5.0.3.3

## Add a song or album

In Dev → Apple Music, paste a link and press Search.
A song link containing `?i=TRACK_ID` looks up that recording only.
An album link without `i` looks up its tracks and opens Add album.
New tracks are checked; existing library matches are unchecked. Untick unwanted
songs, then choose Add selected songs. Cancel/close before saving makes no changes.
Album imports retain album placement even if the individual-add Single option is on.
Selected tags apply to every imported track, alongside Apple's genre.

Songs save one at a time using the existing verified-source add route. A failure
stops the remaining saves and reports how many succeeded; saved tracks are
unchecked/disabled when retrying. Repeating an exact saved Apple identity reuses
the existing song. Title/artist matches need deliberate selection to add separately.
Track-position conflicts remain errors, rather than overwriting another song.
Multi-disc releases keep source disc/track information but leave local positions blank.

New Apple metadata removes only a trailing “ - EP” (case insensitive) from the
local album title. EPs then use ordinary album placement. The original Apple
release name stays in the source observation. Existing albums are not renamed
automatically. Schema remains 15; this patch does not migrate the database.

## What each developer area requests

| Area/action | Apple request and local effect |
| --- | --- |
| Apple Music text search | iTunes Search, music/song, up to 100 results, explicit results enabled, selected two-letter store. Results alone do not save songs. |
| Song link search | iTunes Lookup for the `i` track ID; the link's country overrides the store field. |
| Album link search | iTunes Lookup for the collection ID, entity song, limit 200. Collection wrapper rows are excluded; valid song results appear in the selection popup. Releases exceeding the returned results are not paginated. |
| Add / Add selected songs | Signed, browser-bound offers from the search are verified locally; saving those offers needs no new Apple lookup per track. Names, preview URL, artwork URL, dates, genre and source identity are stored using the normal add workflow. |
| Manual song add/edit with an exact Apple link or ID | Resolves and verifies the source when no signed offer is supplied. Ordinary manual fields without Apple source intent do not request Apple. An album link is not a substitute for selecting a recording in a single-song editor. |
| Song → Source | Reads the saved source locally. Find source performs search/lookup; choosing alone saves nothing. Save source defaults to source-only; metadata refresh and source album/position require their separate options. |
| Bulk edits → Review Apple sources | Searches for each song, or reuses one release lookup for the optional album link. Review/skip then save the chosen sources as a group. This links existing songs; it does not import the album. |
| Missing-information fill | Uses its scan/review/apply workflow and conservative Apple matching. Fills eligible missing metadata/source fields; retains existing artwork, previews, album placement and tag links. |
| Album tracks, Singles moves, tags and catalogue tables | Read/edit local data; these actions do not search Apple merely by opening them. |
| Preview playback | Requests preview media separately from metadata lookup, when playback/preparation asks for it. Saving a preview URL does not download the audio file. |

Metadata requests use HTTPS to `itunes.apple.com/search` or `/lookup`, not
scraping the pasted Music page. Identical lookup URLs have a ten-minute RAM
cache (up to 128 entries). Uncached metadata calls share a local limit of
12 starts/minute, at least five seconds apart, with one lookup loading at a time.
Cache hits do not consume another upstream lookup. Local throttling returns a
retry message; repeated clicking does not bypass it.

HTTP 429 observes Retry-After (60 seconds fallback). Refused 401/403 responses
pause access separately; server/network failures also pause briefly. Errors are
shown rather than treated as an empty successful import. Preview requests have
a separate gate (18 starts/minute, at least half a second apart); complete clips
can be cached in page-scoped RAM, up to ten for ten minutes. These are app limits,
not a claim about Apple's service quota. No automatic source-edit backups are added.

Restart the app and hard-refresh after updating. The footer should show V5.0.3.3.
