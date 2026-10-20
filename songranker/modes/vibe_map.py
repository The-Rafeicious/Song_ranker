"""Several independent maps, inspired by the catalogue's existing tag meanings.

Placements describe the heard preview, not objective quality or a correct answer.
Tag metadata is never inferred or overwritten by playing this mode.
"""
KEY = 'vibe'
NAME = 'Vibe Map'
COLOR = '#FF3B3B'
SONGS = 1
RULES_VERSION = 1
MAPS = (
    dict(key='mood', label='Mood and energy',
         x=dict(key='emotional_tone', label='Emotional tone', low='Heavy / dark', high='Hopeful / bright'),
         y=dict(key='energy', label='Energy', low='Calm / slow', high='Driving / upbeat'),
         inspired_by=['sad', 'melancholic', 'hope', 'angry', 'slow', 'up-beat', 'dance', 'sad-pop']),
    dict(key='sound', label='Sound and delivery',
         x=dict(key='production', label='Production', low='Acoustic / organic', high='Electronic / produced'),
         y=dict(key='vocal_intensity', label='Vocal delivery', low='Restrained / soft', high='Powerful / intense'),
         inspired_by=['acoustic', 'piano-ballad', 'electronic', 'dark-pop', 'low-pop', 'duet']),
    dict(key='craft', label='Build and hook',
         x=dict(key='build', label='Build', low='Steady / immediate', high='Big gradual build'),
         y=dict(key='hook', label='Hook strength', low='Subtle / understated', high='Instant earworm'),
         inspired_by=['build-up', 'catchy', 'chorus', 'bridge']),
)
MAP_KEYS = {m['key'] for m in MAPS}
SCALE = (0, 4)
MAX_THEMES = 8


def validate(payload):
    maps = payload.get('maps')
    if not isinstance(maps, list) or not 1 <= len(maps) <= len(MAPS):
        raise ValueError('Place one to three maps; leave anything you cannot hear unanswered.')
    result = []; seen = set()
    for item in maps:
        if not isinstance(item, dict) or set(item) != {'map', 'x', 'y'}:
            raise ValueError('A map needs its map key, x and y.')
        key = item['map']
        if not isinstance(key, str) or key not in MAP_KEYS or key in seen:
            raise ValueError('Choose distinct supported vibe maps.')
        if any(type(item[k]) is not int or not 0 <= item[k] <= 4 for k in ('x', 'y')):
            raise ValueError('Map coordinates must be whole numbers from 0 to 4.')
        seen.add(key); result.append(dict(map=key, x=item['x'], y=item['y']))
    answer = dict(maps=sorted(result, key=lambda r: r['map']))
    if 'themes' in payload:
        tags = payload['themes']
        if (not isinstance(tags, list) or len(tags) > MAX_THEMES
                or any(type(t) is not int or not 0 < t <= 9223372036854775807 for t in tags)
                or len(set(tags)) != len(tags)):
            raise ValueError('Choose up to eight distinct existing catalogue tags.')
        answer['themes'] = sorted(tags)  # An empty reviewed list differs from unasked.
    return answer
