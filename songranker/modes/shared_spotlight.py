"""Shared Spotlight's compact, subjective preference-strength rules."""
KEY = 'spotlight'
NAME = 'Shared Spotlight'
COLOR = '#7F91FF'  # Blue-violet, well apart from Blind's #55D6C2 mint.
SONGS = 4
POINTS = 12
RULES_VERSION = 1


def validate(payload):
    values = payload.get('allocations')
    if not isinstance(values, list) or len(values) != SONGS:
        raise ValueError('Allocate points to each of the four offered slots, in order.')
    if any(type(v) is not int or not 0 <= v <= POINTS for v in values):
        raise ValueError('Spotlight points must be whole numbers from 0 to 12.')
    if sum(values) != POINTS:
        raise ValueError('Allocate exactly 12 spotlight points. Ties and zeroes are allowed.')
    return dict(allocations=values)


def support(points):
    """Song's points versus the mean of its three peers. Equal shares = 0.5.

    This preserves strength above six points, rather than clipping strong choices.
    One four-song round is ONE observation per song, never six invented votes.
    Public Elo remains a projection of real preference matches only.
    """
    return 3 * points / (POINTS + 2 * points)
