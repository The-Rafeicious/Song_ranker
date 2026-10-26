"""Pure preference replay and schema-8/9 transport upgrade; no Flask imports."""

from bisect import bisect_right, insort
from copy import deepcopy
import json
import math
import hashlib

LEGACY_COLUMNS = ('id', 'winner_id', 'loser_id', 'mode', 'created_at',
                  'winner_before', 'winner_after', 'loser_before', 'loser_after')
EVENT_COLUMNS = LEGACY_COLUMNS + ('offer_token', 'origin', 'rules_version',
                                  'winner_snapshot', 'loser_snapshot')
ELO_RULES_VERSION = 2


def calculate_new_elo(winner, loser, k_factor=32, scale=400):
    """Conserve a pair's rating total, with stable arithmetic for very wide gaps.

    The default is the historical policy, retained for transport verification.
    Current writers and replay supply the population's adaptive scale explicitly.
    """
    if (
        not all(math.isfinite(v) for v in (winner, loser, k_factor, scale))
        or scale <= 0
        or k_factor < 0
    ):
        raise ValueError(
            "Finite ratings, nonnegative K and a positive scale are required."
        )
    exponent = (loser / scale - winner / scale) * math.log(10)
    tail = math.exp(-abs(exponent))
    loss_probability = 1 / (1 + tail) if exponent >= 0 else tail / (1 + tail)
    change = k_factor * loss_probability
    return winner + change, loser - change



class EloPopulation:
    """Incremental tested-only distribution shared by replay and live updates.

    Scale target = clamp(8 * IQR, 200, 400). Blend from 400 with maturity
    mean completed appearances / (mean + 4); unplayed catalogue additions have
    no effect. Counts include eligible first-round tournaments, including scoped
    appearances (their Elo budget, rather than evidence count, is halved).
    """

    def __init__(self, rows=()):
        self.ratings = {}
        self.counts = {}
        self.ordered = []
        self.appearances = 0
        for sid, rating, count in rows:
            if not math.isfinite(rating) or not math.isfinite(count) or count < 0:
                raise ValueError("Invalid Elo population evidence.")
            if count > 0:
                self.ratings[sid] = rating
                self.counts[sid] = count
        self.ordered = sorted((rating, sid) for sid, rating in self.ratings.items())
        self.appearances = math.fsum(self.counts.values())

    def set(self, sid, rating, count):
        """Replace one tested rating/count without sorting the whole catalogue."""
        if not math.isfinite(rating) or not math.isfinite(count) or count < 0:
            raise ValueError("Invalid Elo population evidence.")
        if sid in self.ratings:
            old = (self.ratings.pop(sid), sid)
            self.ordered.pop(bisect_right(self.ordered, old) - 1)
            self.appearances -= self.counts.pop(sid)
        if count > 0:
            self.ratings[sid] = rating
            self.counts[sid] = count
            self.appearances += count
            insort(self.ordered, (rating, sid))

    def scale(self):
        """Use interpolated quartiles before the next event, with a sparse fallback."""
        size = len(self.ordered)
        if size < 4:
            return 400.0

        def quantile(fraction):
            position = (size - 1) * fraction
            lower = int(position)
            upper = min(lower + 1, size - 1)
            return self.ordered[lower][0] * (1 - position + lower) + self.ordered[
                upper
            ][0] * (position - lower)

        spread = quantile(0.75) - quantile(0.25)
        target = min(400.0, max(200.0, 8 * spread))
        mean = self.appearances / size
        return 400 + mean / (mean + 4) * (target - 400)



def live_elo_scale(conn, mode=None):
    """Read a current public or independent-mode distribution, never match history.

    The caller holds the preference write transaction. Persisted projections
    supply the same completed appearances used by the sequential replay.
    """
    state = conn.execute(
        "SELECT rules_version FROM preference_replay_state WHERE id=1"
    ).fetchone()
    if state is None or state[0] == 1:
        return 400.0
    if state[0] != ELO_RULES_VERSION:
        raise ValueError("Elo policy needs a newer app.")
    if mode is None:
        rows = conn.execute("""SELECT s.id,s.elo_score,
            s.matches_played + COALESCE(SUM(m.tournament_matches),0)
            FROM songs s LEFT JOIN preference_mode_ratings m ON m.song_id=s.id
            GROUP BY s.id""")
    else:
        rows = conn.execute(
            "SELECT song_id,elo,matches FROM preference_mode_ratings WHERE mode=?",
            (mode,),
        )
    return EloPopulation(rows).scale()



def compact(value):
    """Serialise deterministic compact JSON for preference snapshots and replay
    hashes.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def records(state, name):
    """Decode one captured table into column-keyed records, tolerating absent
    historical tables.
    """
    table = state['tables'].get(name, {'columns': [], 'rows': []})
    return [dict(zip(table['columns'], row)) for row in table['rows']]


def table(columns, rows, key=None):
    """Build a deterministically ordered captured table, optionally retaining
    explicit row IDs.
    """
    rows = sorted(rows, key=lambda row: compact(row).encode('utf-8'))
    result = {'columns': list(columns), 'rows': rows}
    if key is not None:
        result.update(rowids=[row[key] for row in rows], rowid_alias='rowid')
    return result


def catalogue_snapshots(state):
    """Freeze each song's catalogue identity and linked artists into deterministic
    JSON snapshots.
    """
    songs = {row['id']: row for row in records(state, 'songs')}
    albums = {row['id']: row for row in records(state, 'albums')}
    artists = {row['id']: row for row in records(state, 'artists')}
    links = {}
    for row in records(state, 'song_artists'):
        links.setdefault(row['song_id'], []).append(row['artist_id'])
    result = {}
    for song_id, song in songs.items():
        artist_ids = sorted(links.get(song_id, []))
        album = albums.get(song.get('album_id'), {})
        result[song_id] = compact({'id': song_id, 'title': song['title'], 'album_id': song.get('album_id'),
            'album': album.get('title', ''), 'cover_url': album.get('cover_url'),
            'audio_url': song.get('audio_url'), 'artist_ids': artist_ids,
            'artist': ', '.join(artists[a]['name'] for a in artist_ids if a in artists),
            'artist_links': [{'id': a, 'name': artists[a]['name']} for a in artist_ids if a in artists]})
    return result


def verified_legacy(songs, events):
    """Replay legacy votes and verify every saved before/after rating and final song
    count before migration.
    """
    ratings = {s['id']: 1200.0 for s in songs}
    counts = {s['id']: 0 for s in songs}
    for event in sorted(events, key=lambda row: row['id']):
        w, l = event['winner_id'], event['loser_id']
        if w not in ratings or l not in ratings or w == l or event['mode'] not in ('standard', 'blind'):
            return False
        a, b = ratings[w], ratings[l]
        na, nb = calculate_new_elo(a, b)
        expected = (a, na, b, nb)
        if any(event.get(key) is None or not math.isclose(event[key], value, rel_tol=0, abs_tol=1e-8)
               for key, value in zip(LEGACY_COLUMNS[5:], expected)):
            return False
        ratings[w], ratings[l] = na, nb
        counts[w] += 1; counts[l] += 1
    return all(s.get('elo_score') is not None and s.get('matches_played') == counts[s['id']]
               and math.isclose(s['elo_score'], ratings[s['id']], rel_tol=0, abs_tol=1e-8)
               for s in songs)


def _upgrade_history(original):
    """Map the old physical history to immutable events; preserve all original cells."""
    if 'history' not in original['tables']:
        return original
    if original['user_version'] > 10:
        raise ValueError('Database needs a newer app.')
    if 'preference_events' in original['tables']:
        raise ValueError('Both old history and preference events exist; a dedicated migration is required.')
    old = original['tables']['history']
    if set(old['columns']) != set(LEGACY_COLUMNS):
        raise ValueError('Unsupported legacy history columns; no data was discarded.')
    if 'rowids' in old and old['rowids'] != [row[old['columns'].index('id')] for row in old['rows']]:
        raise ValueError('Unsupported legacy history ID layout; no data was discarded.')
    state = deepcopy(original)
    events = records(state, 'history')
    songs = records(state, 'songs')
    verified = verified_legacy(songs, events)
    boundary = max((event['id'] for event in events), default=0)
    snapshots = catalogue_snapshots(state)
    rows = []
    for event in events:
        rows.append([event[name] for name in LEGACY_COLUMNS] + [None, 'legacy', 0,
            snapshots.get(event['winner_id'], compact({'id': event['winner_id'], 'title': 'Deleted song'})),
            snapshots.get(event['loser_id'], compact({'id': event['loser_id'], 'title': 'Deleted song'}))])
    state['tables']['preference_events'] = table(EVENT_COLUMNS, rows, key=0)
    del state['tables']['history']
    state['tables']['preference_rating_projection'] = table(
        ('event_id', 'winner_before', 'winner_after', 'loser_before', 'loser_after'),
        [[event['id'], *[event[key] for key in LEGACY_COLUMNS[5:]]] for event in events], key=0)
    state['tables']['preference_rating_seeds'] = table(
        ('song_id', 'elo', 'matches', 'highest_elo', 'highest_rank'),
        [[song['id'], 1200.0 if verified else song['elo_score'], 0 if verified else song['matches_played'],
          song.get('highest_elo') or song['elo_score'], song.get('highest_rank') or 9999] for song in songs], key=0)
    state['tables']['preference_replay_state'] = table(
        ('id', 'cutoff_event_id', 'legacy_boundary', 'baseline_kind', 'rules_version'),
        [[1, 0 if verified else boundary, boundary, 'verified_replay' if verified else 'legacy_anchor', 1]], key=0)
    if 'history' in state['sequences']:
        state['sequences']['preference_events'] = state['sequences'].pop('history')
    # Older extension views may read history; its compatible view retains all nine fields.
    state['user_version'] = 10
    return state


def effective_events(state):
    """Apply the latest correction revision to each event without discarding its
    historical identity.
    """
    latest = {}
    for row in sorted(records(state, 'preference_corrections'), key=lambda r: r['id']):
        latest[row['event_id']] = row
    result = []
    for row in records(state, 'preference_events'):
        row.update(active=1, revision=0)
        if row['id'] in latest:
            correction = latest[row['id']]
            row.update({key: correction[key] for key in ('winner_id','loser_id','mode','active')})
            row['revision'] = correction['id']
        result.append(row)
    return result


def mode_replay(songs, events, rules_version=1):
    """Independent streams; each mode owns its population and evidence scale."""
    if rules_version not in (1, ELO_RULES_VERSION):
        raise ValueError('Elo policy needs a newer app.')
    result = {
        (s["id"], mode): dict(elo=1200.0, matches=0, tournament_matches=0)
        for s in songs
        for mode in ("standard", "blind")
    }
    populations = {mode: EloPopulation() for mode in ("standard", "blind")}
    for event in sorted(events, key=lambda row: row["id"]):
        w, l, mode = event["winner_id"], event["loser_id"], event["mode"]
        if (
            not event.get("active", 1)
            or w == l
            or (w, mode) not in result
            or (l, mode) not in result
        ):
            continue
        first, second = result[w, mode], result[l, mode]
        population = populations[mode]
        scale = population.scale() if rules_version == ELO_RULES_VERSION else 400
        first["elo"], second["elo"] = calculate_new_elo(
            first["elo"], second["elo"], 32 * event.get("rating_weight", 1), scale
        )
        for sid, row in ((w, first), (l, second)):
            row["matches"] += 1
            row["tournament_matches"] += int(event["origin"] == "tournament")
            if rules_version == ELO_RULES_VERSION:
                population.set(sid, row["elo"], row["matches"])
    return result



def _upgrade_to_11(original):
    """Normalize 8/9/10 transports to 11 without rewriting existing stored facts."""
    state = _upgrade_history(original)
    if state['user_version'] >= 11:
        return state
    state = deepcopy(state)
    if 'preference_mode_ratings' in state['tables']:
        raise ValueError('A pre-11 extension uses preference_mode_ratings; a dedicated migration is required. No data was discarded.')
    for name, additions in (
        ('preference_events', (('rating_weight', 1.0), ('tournament_id', None), ('tournament_match_id', None))),
        ('tournaments', (('elo_policy_version', 0), ('elo_weight', 0.0))),
    ):
        target = state['tables'].get(name)
        if target:
            for column, default in additions:
                if column in target['columns']:
                    raise ValueError(f'A pre-11 extension uses {name}.{column}; a dedicated migration is required.')
                target['columns'].append(column)
                for row in target['rows']:
                    row.append(default)
    modes = mode_replay(records(state, 'songs'), effective_events(state))
    state['tables']['preference_mode_ratings'] = table(
        ('song_id','mode','elo','matches','tournament_matches'),
        [[sid, mode, row['elo'], row['matches'], row['tournament_matches']]
         for (sid, mode), row in modes.items()])
    # A composite-key SQLite table still has a hidden rowid. Persist deterministic IDs.
    target = state['tables']['preference_mode_ratings']
    target.update(rowids=list(range(1, len(target['rows']) + 1)), rowid_alias='rowid')
    # Verify the old view contract before accounting for its three new columns.
    if 'preference_effective' in state['view_hashes']:
        keys = ('id','offer_token','origin','rules_version','created_at',
                'winner_id','loser_id','mode','active','revision')
        rows = [[row[key] for key in keys] for row in effective_events(state)]
        def view_hash(values):
            """Hash deterministically sorted view rows to verify the migrated
            preference projection.
            """
            return hashlib.sha256(compact(sorted(values, key=lambda row: compact(row).encode('utf-8'))).encode('utf-8')).hexdigest()
        if view_hash(rows) != state['view_hashes']['preference_effective']:
            raise ValueError('Unsupported preference_effective view; no stored data was changed.')
        rows = [row[:5] + [1.0, None, None] + row[5:] for row in rows]
        state['view_hashes']['preference_effective'] = view_hash(rows)
    state['user_version'] = 11
    return state


def upgrade_state(original):
    """Apply lossless upgrades; recognize complete known SQL-dump layouts."""
    if original['user_version']==0:
        from songranker.storage.database_schema import table_columns
        from songranker.storage.schema_compat import CHALLENGE_ADDITIONS as quiz_additions
        from songranker.storage.schema_compat import SOURCE_ADDITIONS as song_additions
        current={name:set(columns) for name,columns in table_columns().items()}
        from songranker.storage.vibe_state import TABLES as vibe_tables
        # Layout 18/19 is identical; definition generation disambiguates dumps.
        maps=original['tables'].get('vibe_maps',{})
        columns=maps.get('columns',[])
        generation=(19 if 'definition_version' in columns and maps.get('rows') and
                    all(row[columns.index('definition_version')]==2 for row in maps['rows']) else 18)
        from songranker.storage.schema_compat import LISTENING_COLUMNS as listening_columns
        pre_shelves={name:columns-({'shelves_excluded'} if name=='albums' else set()) for name,columns in current.items()}
        pre_discs={name:columns-({'disc_number'} if name in ('songs','album_shelf_items') else set()) for name,columns in pre_shelves.items()}
        legacy_current=dict(pre_discs,listening_observations=set(listening_columns))
        layouts=[(22,current),(21,pre_shelves),(20,pre_discs),(generation,legacy_current)]
        current=legacy_current
        seventeen={name:set(columns) for name,columns in current.items() if name not in ('song_vibe_progress','vibe_rounds')}
        seventeen['song_vibe_positions']-={'sample_count','not_applicable_count'}
        layouts.append((17,seventeen))
        sixteen={name:columns for name,columns in current.items() if name not in vibe_tables}
        # Pre-17 SQL dumps share the older 14-16 column layout; retain its
        # established transport adapters when the version pragma was omitted.
        layouts.append((14,sixteen))
        thirteen={name:set(columns) for name,columns in sixteen.items() if name not in ('song_details','competition_state','listening_observations')}
        layouts.append((13,thirteen))
        twelve={name:set(columns) for name,columns in thirteen.items() if name!='song_sources'}
        twelve['songs']-={name for name,_ in song_additions}
        layouts.append((12,twelve))
        eleven={name:set(columns) for name,columns in twelve.items() if name!='challenge_runs'}
        for name,additions in quiz_additions.items():eleven[name]-={column for column,_ in additions}
        layouts.append((11,eleven))
        ten={name:set(columns) for name,columns in eleven.items() if name!='preference_mode_ratings'}
        ten['preference_events']-={'rating_weight','tournament_id','tournament_match_id'}
        ten['tournaments']-={'elo_policy_version','elo_weight'}
        layouts.append((10,ten))
        for version,layout in layouts:
            if (set(original['tables'])&set(current)==set(layout) and
                all(set(original['tables'][name]['columns'])==columns for name,columns in layout.items())):
                original=deepcopy(original);original['user_version']=version;break
    from songranker.storage.schema_compat import upgrade_challenges as upgrade_challenges
    from songranker.storage.schema_compat import upgrade_sources as upgrade_sources
    from songranker.storage.source_storage import upgrade_state as upgrade_storage
    from songranker.storage.tag_limits import upgrade_state as upgrade_tags
    from songranker.storage.vibe_state import upgrade_state as upgrade_vibes
    from songranker.storage.schema_compat import retire_listening as retire_listening
    from songranker.storage.schema_compat import upgrade_album_discs, upgrade_album_shelves
    return upgrade_album_shelves(upgrade_album_discs(retire_listening(upgrade_vibes(upgrade_tags(upgrade_storage(upgrade_sources(upgrade_challenges(_upgrade_to_11(original)))))))))


def replay(songs, seeds, events, overrides, cutoff, boundary, rules_version=1):
    """Return current ratings/counts and effective snapshots from immutable inputs."""
    if rules_version not in (1, ELO_RULES_VERSION):
        raise ValueError('Elo policy needs a newer app.')
    result = {s["id"]: dict(seeds[s["id"]]) for s in songs}
    ordered = sorted((row["elo"], sid) for sid, row in result.items())
    adaptive = rules_version == ELO_RULES_VERSION
    population = EloPopulation(
        (sid, row["elo"], row["matches"]) for sid, row in result.items()
    )
    if adaptive and cutoff == 0:
        # Old recorded peaks belong to the old calculation. Rebuild peaks from
        # the known baseline and every effective event, including legacy events.
        for sid, row in result.items():
            row["highest_elo"] = row["elo"]
            row["highest_rank"] = 9999
    projected = {}
    adjustments = sorted(overrides, key=lambda row: (row["after_event_id"], row["id"]))
    index = 0

    def set_rating(sid, value):
        """Update one replayed song's Elo while keeping the sorted rating index
        consistent.
        """
        if sid not in result:
            return
        old = (result[sid]["elo"], sid)
        pos = bisect_right(ordered, old) - 1
        if pos < 0 or ordered[pos] != old:
            raise ValueError("Rating projection is inconsistent.")
        ordered.pop(pos)
        insort(ordered, (value, sid))
        result[sid]["elo"] = value
        if adaptive:
            population.set(sid, value, population.counts.get(sid, 0))

    def apply_before(event_id):
        """Apply saved manual rating adjustments that precede the next replayed
        preference event.
        """
        nonlocal index
        while (
            index < len(adjustments) and adjustments[index]["after_event_id"] < event_id
        ):
            row = adjustments[index]
            set_rating(row["song_id"], row["new_elo"])
            index += 1

    for event in sorted(events, key=lambda row: row["id"]):
        if event["id"] <= cutoff:
            continue
        apply_before(event["id"])
        w, l = event["winner_id"], event["loser_id"]
        if not event["active"] or w not in result or l not in result or w == l:
            continue
        a, b = result[w]["elo"], result[l]["elo"]
        scale = population.scale() if adaptive else 400
        na, nb = calculate_new_elo(a, b, 32 * event.get("rating_weight", 1), scale)
        set_rating(w, na)
        set_rating(l, nb)
        if adaptive:
            for sid in (w, l):
                population.set(
                    sid, result[sid]["elo"], population.counts.get(sid, 0) + 1
                )
        if event["origin"] in ("legacy", "ordinary"):
            result[w]["matches"] += 1
            result[l]["matches"] += 1
        projected[event["id"]] = (a, na, b, nb)
        if event["id"] > boundary or (adaptive and cutoff == 0):
            for sid in (w, l):
                value = result[sid]["elo"]
                result[sid]["highest_elo"] = max(result[sid]["highest_elo"], value)
                rank = len(ordered) - bisect_right(ordered, (value, float("inf"))) + 1
                result[sid]["highest_rank"] = min(result[sid]["highest_rank"], rank)
    apply_before(float("inf"))
    return result, projected



def rebuild_preference_ratings(conn):
    """Replace derived Elo projections inside the caller's transaction, without Flask.

    Immutable events, corrections, overrides and seed anchors remain untouched.
    Legacy anchors with missing early history retain their cutoff and old peaks.
    """
    settings = dict(
        conn.execute("SELECT * FROM preference_replay_state WHERE id=1").fetchone()
    )
    version = settings["rules_version"]
    if version not in (1, ELO_RULES_VERSION):
        raise ValueError("Elo policy needs a newer app.")
    songs = [dict(r) for r in conn.execute("SELECT id FROM songs")]
    seeds = {
        r["song_id"]: dict(r)
        for r in conn.execute("SELECT * FROM preference_rating_seeds")
    }
    events = [
        dict(r) for r in conn.execute("SELECT * FROM preference_effective ORDER BY id")
    ]
    overrides = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM preference_rating_overrides ORDER BY after_event_id,id"
        )
    ]
    ratings, projected = replay(
        songs,
        seeds,
        events,
        overrides,
        settings["cutoff_event_id"],
        settings["legacy_boundary"],
        version,
    )
    conn.execute(
        "DELETE FROM preference_rating_projection WHERE event_id>?",
        (settings["cutoff_event_id"],),
    )
    conn.executemany(
        "INSERT INTO preference_rating_projection VALUES(?,?,?,?,?)",
        ((event_id, *values) for event_id, values in projected.items()),
    )
    conn.executemany(
        "UPDATE songs SET elo_score=?,matches_played=?,highest_elo=?,highest_rank=? WHERE id=?",
        (
            (row["elo"], row["matches"], row["highest_elo"], row["highest_rank"], sid)
            for sid, row in ratings.items()
        ),
    )
    conn.executemany(
        """INSERT INTO preference_mode_ratings VALUES(?,?,?,?,?)
        ON CONFLICT(song_id,mode) DO UPDATE SET elo=excluded.elo,
        matches=excluded.matches,tournament_matches=excluded.tournament_matches""",
        (
            (sid, mode, row["elo"], row["matches"], row["tournament_matches"])
            for (sid, mode), row in mode_replay(songs, events, version).items()
        ),
    )
    return len(projected)
