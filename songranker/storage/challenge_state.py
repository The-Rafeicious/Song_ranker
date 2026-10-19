"""Pure schema-12 transport upgrade. Historical quiz rows remain classic facts."""
from copy import deepcopy

ADDITIONS = {
    'trivia_rounds': (
        ('run_id', None), ('rules_version', 1), ('streak_before', None),
        ('streak_rule', None), ('streak_passed', None), ('answer_snapshot', None)),
    'elo_guess_rounds': (
        ('run_id', None), ('rules_version', 1), ('streak_before', None),
        ('target_quantile', None), ('streak_after', None), ('user_score_after', None)),
}


def upgrade_state(original):
    if original['user_version'] >= 12:
        return original
    state = deepcopy(original)
    if 'challenge_runs' in state['tables']:
        raise ValueError('A pre-12 extension uses challenge_runs; a dedicated migration is required. No data was discarded.')
    for name, additions in ADDITIONS.items():
        target = state['tables'].get(name)
        if target:
            for column, default in additions:
                if column in target['columns']:
                    raise ValueError(f'A pre-12 extension uses {name}.{column}; a dedicated migration is required.')
                target['columns'].append(column)
                for row in target['rows']:
                    row.append(default)
    state['user_version'] = 12
    return state
