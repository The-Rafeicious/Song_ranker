"""Schema 17: retire Sound Twins facts, preserving all other stored values.

The normal migration writes a verified pre-upgrade backup before calling this
pure transform. The retired mode can still be recovered from that backup.
"""
from copy import deepcopy


def upgrade_state(original):
    if original['user_version'] >= 17:
        return original
    state = deepcopy(original)
    rounds = state['tables'].get('judgement_rounds')
    retired = set()
    if rounds:
        columns = rounds['columns']
        retired = {r[columns.index('id')] for r in rounds['rows']
                   if r[columns.index('mode')] == 'twins'}

    def keep(name, predicate):
        data = state['tables'].get(name)
        if data is None:
            return
        indices = [i for i, row in enumerate(data['rows']) if predicate(dict(zip(data['columns'], row)))]
        data['rows'] = [data['rows'][i] for i in indices]
        if 'rowids' in data:
            data['rowids'] = [data['rowids'][i] for i in indices]

    keep('judgement_rounds', lambda r: r['id'] not in retired)
    for name in ('judgement_items', 'spotlight_allocations', 'vibe_placements', 'vibe_themes'):
        keep(name, lambda r: r['round_id'] not in retired)
    keep('listening_observations', lambda r: r['mode'] != 'twins')
    state['tables'].pop('twins_choices', None)
    state['sequences'].pop('twins_choices', None)
    state['objects'] = [o for o in state['objects']
                        if o['name'] not in ('twins_choices', 'twins_open_answer')
                        and o['table'] != 'twins_choices']
    # This derived view intentionally loses the retired mode's exposures only.
    if retired:
        state['view_hashes'].pop('mode_exposures', None)
    state['user_version'] = 17
    return state
