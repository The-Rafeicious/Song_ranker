"""Song tag policy and the explicit schema-16 membership cleanup."""
from copy import deepcopy
import unicodedata

MAX_SONG_TAGS = 8


def tag_names(value):
    names = {}
    for name in str(value or '').split(','):
        name = name.strip()
        if name:
            key = unicodedata.normalize('NFKC', name).casefold()
            names.setdefault(key, name)
    return list(names.values())


def check_count(count):
    if count > MAX_SONG_TAGS:
        raise ValueError(f'A song can have at most {MAX_SONG_TAGS} tags. Remove a tag before adding another.')


def upgrade_state(original):
    """Keep the first eight saved links; preserve unrelated data and link rowids."""
    if original['user_version'] >= 16:
        return original
    state = deepcopy(original)
    data = state['tables'].get('song_genres')
    if data:
        sid = data['columns'].index('song_id')
        tid = data['columns'].index('genre_id')
        rowids = data.get('rowids')
        order = sorted(range(len(data['rows'])), key=lambda i: rowids[i] if rowids else data['rows'][i][tid])
        counts, keep = {}, set()
        for i in order:
            song_id = data['rows'][i][sid]
            counts[song_id] = counts.get(song_id, 0) + 1
            if counts[song_id] <= MAX_SONG_TAGS:
                keep.add(i)
        data['rows'] = [r for i, r in enumerate(data['rows']) if i in keep]
        if rowids is not None:
            data['rowids'] = [r for i, r in enumerate(rowids) if i in keep]
    state['user_version'] = 16
    return state
