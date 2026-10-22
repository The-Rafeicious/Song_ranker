"""Pure versioned streak rules shared by the server and offline checks."""


RULES_VERSION = 2
TRIVIA_LABELS = {
    'any': 'Any correct answer keeps the streak going.',
    'title_or_album': 'Song or album required to keep the streak.',
    'title_and_album': 'Song and album required to keep the streak.',
    'title': 'Song required to keep the streak; no album to guess.',
}


def trivia_rule(streak, album_available):
    if streak < 10:
        return 'any'
    if not album_available:
        return 'title'
    return 'title_or_album' if streak < 25 else 'title_and_album'


def trivia_passed(row):
    title, artist, album = (row[f+'_correct'] == 1 for f in ('title','artist','album'))
    return {'any': title or artist or bool(row['album_available']) and album,
            'title_or_album': title or album, 'title_and_album': title and album,
            'title': title}[row['streak_rule']]


def guess_target(streak):
    return .60 / (1 + max(0, streak) / 10)
