"""Schema-20 retirement only: discard former telemetry, preserve every other fact."""
from copy import deepcopy
import re

LEGACY_COLUMNS=('id','mode','reference','song_key','song_id','seconds','decision_ms','selected','recorded_at')
OWNED={'listening_observations','listening_song_mode'}


def upgrade_state(original):
    if original['user_version']>=20:return original
    # Unknown views/triggers/FKs must not quietly become invalid extensions.
    for obj in original['objects']:
        if obj['name'] not in OWNED and re.search(r'\blistening_observations\b',obj['sql'],re.I):
            raise ValueError('An extension depends on retired listening data; review it before upgrading. No data was changed.')
    old=original['tables'].get('listening_observations')
    if old and tuple(old['columns'])!=LEGACY_COLUMNS:
        raise ValueError('Unsupported listening table columns; no data was discarded.')
    state=deepcopy(original)
    state['tables'].pop('listening_observations',None)
    state['sequences'].pop('listening_observations',None)
    state['objects']=[o for o in state['objects'] if o['name'] not in OWNED]
    state['user_version']=20
    return state
