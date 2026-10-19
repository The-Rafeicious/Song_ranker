"""Lossless schema-13 upgrade: unknown legacy source identities/dates stay unknown."""
from copy import deepcopy

ADDITIONS = (('release_date',None),('release_date_origin',None))


def upgrade_state(original):
    if original['user_version']>=13:
        return original
    state=deepcopy(original)
    if 'song_sources' in state['tables']:
        raise ValueError('A pre-13 extension uses song_sources; a dedicated migration is required. No data was discarded.')
    songs=state['tables'].get('songs')
    if songs:
        for column,default in ADDITIONS:
            if column in songs['columns']:
                raise ValueError(f'A pre-13 extension uses songs.{column}; a dedicated migration is required.')
            songs['columns'].append(column)
            for row in songs['rows']:row.append(default)
    state['user_version']=13
    return state
