"""Optional NumPy QA: rerun the accepted experiments using deployed selectors.

This imports only the pure selection module, never Flask or the app database.
It writes results.json in this folder. NumPy is a QA-only dependency.
"""
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import selection as deployed
import reference as lab

_original_pair = lab.pair
_original_guess = lab.guess_pair
_original_entries = lab.draw_entries
_original_shelf = lab.shelf_draw
_original_weights = lab.weights


def rows(counts, ratings=None):
    return [dict(id=i, elo_score=float(ratings[i]) if ratings is not None else 1200.0)
            for i in range(len(counts))]


def pair(rng, counts, ratings, policy, previous=()):
    if policy != 'deficit':
        return _original_pair(rng, counts, ratings, policy, previous)
    first, second = deployed.choose_match(rows(counts, ratings), rng,
        counts=dict(enumerate(counts)), previous=previous)
    return None if first is None else (first['id'], second['id'])


def guess(rng, counts, ratings, streak, policy='deficit', previous=()):
    if policy != 'deficit':
        return _original_guess(rng, counts, ratings, streak, policy, previous)
    # Streak stages remain offline here; classic live play uses target=0.60.
    first, second = deployed.choose_guess_pair(rows(counts, ratings), rng,
        counts=dict(enumerate(counts)), previous=previous, target=0.60 / (1 + streak / 10))
    return None if first is None else (first['id'], second['id'])


def entries(rng, counts, size, policy):
    if policy != 'deficit':
        return _original_entries(rng, counts, size, policy)
    chosen = deployed.draw_entries(rows(counts), size, rng, counts=dict(enumerate(counts)))
    return None if chosen is None else [s['id'] for s in chosen]


def shelf(rng, groups, album_counts, track_counts, history, policy, count=0):
    if policy != 'deficit':
        return _original_shelf(rng, groups, album_counts, track_counts, history, policy, count)
    grouped = {aid: [dict(id=sid) for sid in ids] for aid, ids in groups.items()}
    chosen = deployed.draw_shelves(grouped, album_counts, dict(enumerate(track_counts)), history, count, rng)
    return None if chosen is None else (chosen[0], [s['id'] for s in chosen[1]])


def weights(counts, policy):
    return lab.np.asarray(deployed.exposure_probabilities(counts)) if policy == 'deficit' else _original_weights(counts, policy)


def parity():
    """Independent prototype vs production with changing counts and recency."""
    ratings = lab.np.asarray(lab.DATA['ratings'], float)
    for name in ('pair', 'guess', 'entries', 'shelf'):
        a = random.Random(771); b = random.Random(771)
        counts = lab.np.asarray(lab.DATA['exposures']['public'], float).copy(); previous = ()
        groups = {int(k): v for k, v in lab.DATA['shelf_groups'].items()}
        ac = {int(k): v for k, v in lab.DATA['album_exposure'].items()}; history = []
        for step in range(100):
            if name == 'pair':
                expected = _original_pair(a, counts, ratings, 'deficit', previous)
                actual = pair(b, counts, ratings, 'deficit', previous)
                counts[list(actual)] += 1; previous = actual
            elif name == 'guess':
                expected = _original_guess(a, counts, ratings, 0, previous=previous)
                actual = guess(b, counts, ratings, 0, previous=previous)
                counts[list(actual)] += 1; previous = actual
            elif name == 'entries':
                expected = _original_entries(a, counts, 16, 'deficit')
                actual = entries(b, counts, 16, 'deficit')
                counts[actual] += 1
            else:
                expected = _original_shelf(a, groups, ac, counts, history, 'deficit')
                actual = shelf(b, groups, ac, counts, history, 'deficit')
                for aid in actual[0]: ac[aid] = ac.get(aid, 0) + 1
                counts[actual[1]] += 1; history.append(actual[0])
            lab.check(f'deployed {name} parity {step}', expected == actual)
    # Trivia uses the full eligible-pool baseline before removing the last item.
    a = random.Random(772); b = random.Random(772)
    counts = lab.np.asarray(lab.DATA['exposures']['trivia'], float).copy(); previous = None
    for step in range(100):
        w = _original_weights(counts, 'deficit')
        if previous is not None: w[previous] = 0
        expected = lab.choose(a, w)
        actual = deployed.choose_single(rows(counts), b, counts=dict(enumerate(counts)), previous=previous)['id']
        lab.check(f'deployed Trivia parity {step}', expected == actual)
        counts[actual] += 1; previous = actual


if __name__ == '__main__':
    parity()
    lab.weights = weights; lab.spread = deployed.rating_spread
    lab.pair = pair; lab.guess_pair = guess; lab.draw_entries = entries; lab.shelf_draw = shelf
    lab.main()
