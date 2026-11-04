"""Pure current-policy tournament points and advancement; never rewrites match facts."""

POLICY_VERSION = 2
BRACKET_ROUNDS = {8: 3, 16: 4, 32: 5}
MAX_ROUNDS = max(BRACKET_ROUNDS.values())
MAX_POINTS = sum(range(1, MAX_ROUNDS + 1))


def rounds(size):
    """Return knockout depth for supported public bracket sizes, or no policy."""
    return BRACKET_ROUNDS.get(size)


def round_points(size, stage, kind='bracket'):
    """Award 1,2,... points by round; bronze earns half a semi-final win."""
    depth = rounds(size)
    if depth is None or not isinstance(stage, int) or not 1 <= stage <= depth:
        return None
    if kind == 'third_place':
        return (depth - 1) / 2
    if kind != 'bracket':
        return None
    return float(stage)


def scored_match(match, bracket):
    """Project historical and new decided matches through one points policy.

    Stored points remain archival facts. Invalid/unsupported legacy rounds keep
    their saved value; pending rounds never receive projected win points.
    """
    result = dict(match)
    winner, loser = result.get('winner_id'), result.get('loser_id')
    participants = (result.get('song1_id'), result.get('song2_id'))
    if (result.get('status') != 'completed' or winner is None or loser is None
            or winner == loser or (None not in participants and set(participants) != {winner, loser})):
        return result
    points = round_points(bracket.get('size'), result.get('round_number'), result.get('match_type', 'bracket'))
    if points is not None:
        result['points_awarded'] = points
    return result


def scored_matches(matches, brackets):
    """Return new display records; accept a bracket mapping or list."""
    by_id = brackets if isinstance(brackets, dict) else {t['id']: t for t in brackets}
    return [scored_match(m, by_id.get(m['tournament_id'], {})) for m in matches]


def entry_results(data):
    """One outcome per song/completed bracket, with no consolation-loss penalty.

    Reaching a recorded knockout stage proves earlier advancement even if old
    rounds are missing. Raw match counts and recorded titles remain separate.
    Achievement gives 1/.75/.55/.4 credit for places 1–4, multiplied by the
    bracket's depth / 5. Advancement and points share fixed 32-track ceilings.
    """
    brackets = {t['id']: t for t in data.get('tournaments', [])
                if t.get('status') == 'completed' and rounds(t.get('size'))}
    results = {}
    finishes={tid:{key:bracket.get(key) for key in ('champion_id','runner_up_id','third_place_id','fourth_place_id')} for tid,bracket in brackets.items()}
    def ensure(sid, tid):
        if sid is None:
            return None
        return results.setdefault((sid, tid), dict(advanced=0, points=0, achievement=0))
    for entry in data.get('tournament_entries', []):
        if entry['tournament_id'] in brackets:
            ensure(entry['song_id'], entry['tournament_id'])
    for raw in data.get('tournament_matches', []):
        tid = raw['tournament_id']
        if tid not in brackets or raw.get('status') != 'completed':
            continue
        winner, loser = raw.get('winner_id'), raw.get('loser_id')
        pair = (raw.get('song1_id'), raw.get('song2_id'))
        if winner is None or loser is None or winner == loser or (None not in pair and set(pair) != {winner, loser}):
            continue
        depth = rounds(brackets[tid]['size'])
        stage = raw.get('round_number')
        points = round_points(brackets[tid]['size'], stage, raw.get('match_type', 'bracket'))
        if points is None:
            continue
        if raw.get('match_type','bracket')=='third_place':
            keys=('third_place_id','fourth_place_id')
        elif stage==depth and raw.get('match_number',1)==1:
            keys=('champion_id','runner_up_id')
        else:
            keys=None
        if keys and finishes[tid][keys[0]] in (None,winner):
            if finishes[tid][keys[0]] is None:finishes[tid][keys[0]]=winner
            if finishes[tid][keys[1]] is None:finishes[tid][keys[1]]=loser
        win, loss = ensure(winner, tid), ensure(loser, tid)
        win['points'] += points
        if raw.get('match_type', 'bracket') == 'bracket':
            win['advanced'] = max(win['advanced'], stage)
            loss['advanced'] = max(loss['advanced'], stage - 1)
    for tid, bracket in brackets.items():
        depth = rounds(bracket['size'])
        for key, credit, won in [('champion_id', 1, depth), ('runner_up_id', .75, depth-1),
                                  ('third_place_id', .55, depth-2), ('fourth_place_id', .4, depth-2)]:
            outcome = ensure(finishes[tid].get(key), tid)
            if outcome is not None:
                outcome['achievement'] = max(outcome['achievement'], credit * depth / MAX_ROUNDS)
                outcome['advanced'] = max(outcome['advanced'], won)
    return results
