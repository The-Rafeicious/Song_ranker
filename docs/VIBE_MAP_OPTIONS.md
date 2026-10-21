# Vibe Map axis options

**V1.0.4.2 selects a new set:** Pace & mood, Sound & impact, Connection and
Perspective. See [the selected definitions and reset](VIBE_MAP_V1042.md). The
options below are the earlier design library, not the current live definitions.

These remain design choices for a future map change. Keep at most four maps per song. The options below draw on the catalogue's
existing tags and gaps in the present eight axes.

In the reviewed backup, tags include sad (88 songs), brake-up (66), past-love
(64), up-beat (56), melancholic (45), angry (32), acoustic (19), flirt (18),
build-up (16), hope (14), retrospective (14) and friendship (12). Counts describe
current tagging, not the true distribution of all songs: tagging is unfinished.
Romance, reflection and vulnerability already have strong coverage. Texture,
arrangement, groove and emotional resolution offer useful extra distinctions.

## Candidate two-axis maps

Each row is one possible map. The middle means balanced/mixed on an axis; choose
endpoints you can consistently judge for almost every song. Avoid treating a
missing theme as an extreme, especially now that the page has no N/A button.

| Map | X: left → right | Y: bottom → top | Useful distinction |
| --- | --- | --- | --- |
| Mood & energy | Sad → Happy | Gentle → Intense | Keep the current broad emotional anchor. Sad and intense can coexist. |
| Emotional weather | Heavy / bleak → Light / buoyant | Settled → Restless | Distinguish mood from agitation; an upbeat rhythm can still feel heavy. |
| Emotional release | Held back → Cathartic | Resigned → Hopeful | Quiet acceptance versus a big release; useful for build-up, crying-sad and hope. |
| Recovery | Hurt / overwhelmed → Healing / secure | Stuck → Moving forward | Distinguish heart-ache, hung-up, better-off and moving-on. |
| Attachment | Letting go → Holding on | Distant → Close | Broader than a chronological breakup-to-new-love axis. Works for friends/family too. |
| Relationships | Separation / ending → Beginning / new love | Guarded → Devoted | Keep the current romance map if that story distinction matters most. |
| Romantic tension | Content / secure → Longing / wanting | Innocent / tender → Sensual / charged | Separates crush, unrequited-love, flirt and sexy. Neutral for non-romantic songs. |
| Conflict | Forgiving / accepting → Accusing / confrontational | Restrained → Explosive | A gentle but bitter track differs from an angry, explosive one. |
| Agency | Powerless / uncertain → In control / determined | Self-protective → Open / exposed | Confidence and vulnerability need not be opposites. |
| Self & others | Vulnerable → Defiant | Inward / private → Outward / social | Keep the current self_social map when broad stance is enough. |
| Belonging | Isolated → Connected | Guarded → Reaching out | Adds friendship, loneliness and family without requiring romance. |
| Perspective | Looking back → Looking forward | Observing / reflecting → Acting / changing | Separate retrospective storytelling from determination. |
| Reality & escape | Grounded / everyday → Dreamlike / surreal | Intimate / personal → Cinematic / expansive | Particularly useful for soundtrack and atmospheric pop. |
| Texture & space | Acoustic / organic → Electronic / synthetic | Close / intimate → Spacious / expansive | Fills a major production gap; mixed production belongs near the centre. |
| Arrangement | Sparse / stripped → Dense / layered | Steady / even → Building / changing | Captures piano-ballad, acoustic and build-up without rating a song's quality. |
| Groove | Floating / free → Rhythmic / driving | Relaxed → Urgent | Separates slow, up-beat and dance without confusing pace with happiness. |
| Sound character | Soft / smooth → Rough / abrasive | Warm / rounded → Cool / sharp | Texture within pop/alternative rather than a genre selector. |
| Vocal presence | Breathier / restrained → Belted / forceful | Conversational / direct → Theatrical / dramatic | Useful across vocal-led pop; less useful for many instrumentals. |
| Narrative | Snapshot / impression → Story / sequence | Inner thoughts → Events / people | Goes beyond romance and matches story-telling/retrospective distinctions. |
| Emotional focus | Self / inner life → Other people / connection | Acceptance → Desire for change | A broad thematic replacement if romance-specific axes feel forced. |

Do not use speed and intensity as two supposedly independent maps: they overlap
and would double-count much of the same impression. Likewise, four romance maps
would miss how songs actually sound. Acoustic/electronic describes production,
not an artist's genre; confidence/hope describes this song, not its performer.

## Four-map sets to choose from

| Set | Four maps | Trade-off |
| --- | --- | --- |
| Keep the current focus | Mood & energy; Relationships; Self & others; Reflection & escape (current) | No remapping. Strong mood/story coverage, limited sound/arrangement coverage. |
| Balanced catalogue | Mood & energy; Attachment; Texture & space; Perspective | Broad emotional, interpersonal, sonic and narrative coverage with less forced romance. My first alternative to consider. |
| Lyrics and feelings | Emotional weather; Romantic tension; Recovery; Narrative | Strong for lyric-led breakup/love songs; weaker for instrumental similarity. |
| Sound and listening vibe | Mood & energy; Texture & space; Arrangement; Groove | Better for sonic neighbours; less information about lyrical themes. |
| Emotional journey | Emotional weather; Emotional release; Agency; Recovery | Distinguishes hurt, anger, release and moving on; expect correlated axes. |
| Atmosphere and drama | Mood & energy; Reality & escape; Sound character; Vocal presence | Good for cinematic, intimate and theatrical contrasts; vocals may not apply to every track. |

A smaller first experiment would keep three existing maps and replace only one
with Texture & space. Review whether the new distinction actually separates
songs you currently consider different before changing several at once.

## Changing a map later

Do not rename an existing axis and keep its coordinates. A point on
Breakup → New love cannot become an Acoustic → Electronic measurement.
Meaning changes need a new stable map key/definition version and fresh points,
with a backed-up migration and an explicit decision about retiring old slots.
Cosmetic wording that preserves the same meaning is different from changing the
measurement. Existing round receipts and similarity comparisons must use matching
map definitions; incompatible versions must never be compared as if identical.

No configurable map picker, new schema, retagging or remapping is added by this
patch. Choose the axes first; implement and migrate that choice in a later update.
