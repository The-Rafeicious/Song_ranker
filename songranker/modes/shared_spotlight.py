"""Shared Spotlight's compact, subjective preference-strength rules."""
KEY = 'spotlight'
NAME = 'Shared Spotlight'
COLOR = '#7F91FF'  # Blue-violet, well apart from Blind's #55D6C2 mint.
SONGS = 4
POINTS = 12
RULES_VERSION = 2
MAX_ROUND_POINTS = 24


def allocate(positions):
    """Integer arithmetic gives identical half-up rounding in Python and JS."""
    if not isinstance(positions, list) or len(positions) != SONGS or any(
            type(x) is not int or not 0 <= x <= 100 for x in positions):
        raise ValueError('Place all four songs on the connecting bar (0 to 100).')
    total = sum(positions)
    return [max(0, min(POINTS, (14*x - 2*total + 50)//100)) for x in positions]


def validate(payload):
    if payload.get('rules_version', 1) == 2:
        positions = payload.get('positions')
        return dict(positions=positions, allocations=allocate(positions))
    return validate_legacy(payload)


def validate_legacy(payload):
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
