"""Album track positions: gaps and blanks are valid; occupied slots are not."""
import re


class TrackNumberConflict(ValueError):
    pass


def parse_track_number(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value).strip()):
        raise ValueError('Track number must be a positive whole number, or left blank.')
    number = int(str(value).strip())
    if number > 9223372036854775807:
        raise ValueError('Track number is too large.')
    return number


def check_track_position(conn, album_id, number, song_id=None):
    if album_id is None or number is None:
        return
    other = conn.execute('''SELECT s.id,s.title,a.title AS album FROM songs s
        JOIN albums a ON a.id=s.album_id
        WHERE s.album_id=? AND s.track_number=? AND s.id!=? LIMIT 1''',
        (album_id, number, song_id if song_id is not None else -1)).fetchone()
    if other:
        raise TrackNumberConflict(
            f"Track {number} is already used by '{other['title']}' on '{other['album']}'.")


def track_position_conflicts(conn):
    """Report old duplicates/invalid positions without guessing replacement numbers."""
    return [dict(row) for row in conn.execute('''
        SELECT s.id,s.title,s.album_id,a.title AS album,s.track_number,
          CASE WHEN typeof(s.track_number)!='integer' OR s.track_number<1
            THEN 'Invalid track number' ELSE 'Duplicate album track number' END AS issue
        FROM songs s LEFT JOIN albums a ON a.id=s.album_id
        WHERE s.track_number IS NOT NULL AND
          (typeof(s.track_number)!='integer' OR s.track_number<1 OR EXISTS
            (SELECT 1 FROM songs other WHERE other.album_id=s.album_id
             AND other.track_number=s.track_number AND other.id!=s.id))
        ORDER BY a.title COLLATE NOCASE,s.track_number,s.id''')]


def ensure_track_position_checks(conn):
    """Guard every SQLite write, while allowing databases with old conflicts to open."""
    for event, name, exclusion in [
        ('INSERT', 'songs_track_position_insert', ''),
        ('UPDATE OF album_id,track_number', 'songs_track_position_update', 'AND s.id!=NEW.id')
    ]:
        conn.execute(f'''CREATE TRIGGER IF NOT EXISTS {name}
            BEFORE {event} ON songs BEGIN
            SELECT RAISE(ABORT,'Track number must be a positive whole number or NULL.')
              WHERE NEW.track_number IS NOT NULL
              AND (typeof(NEW.track_number)!='integer' OR NEW.track_number<1);
            SELECT RAISE(ABORT,'Track number is already used in this album.')
              WHERE NEW.album_id IS NOT NULL AND NEW.track_number IS NOT NULL
              AND EXISTS (SELECT 1 FROM songs s WHERE s.album_id=NEW.album_id
                  AND s.track_number=NEW.track_number {exclusion});
            END''')
