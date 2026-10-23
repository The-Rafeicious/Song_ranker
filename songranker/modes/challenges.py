"""Server-owned quiz runs. Frozen round rules govern progress, never cookie counters."""

import secrets
import sqlite3
import time
from flask import session
from songranker.modes.challenge_rules import RULES_VERSION as RULES_VERSION, TRIVIA_LABELS as TRIVIA_LABELS, trivia_rule as trivia_rule, trivia_passed as trivia_passed, guess_target as guess_target


TABLES = {'trivia': 'trivia_rounds', 'guesser': 'elo_guess_rounds'}

def browser_owner():
    """Create or reuse the session identity that owns persisted challenge runs."""
    owner = session.get('challenge_owner')
    if not owner:
        owner = secrets.token_urlsafe(32)
        session['challenge_owner'] = owner
    return owner


def active_run(conn, mode):
    """Caller holds BEGIN IMMEDIATE; one active run per browser and mode."""
    owner = browser_owner()
    run = conn.execute('SELECT * FROM challenge_runs WHERE owner=? AND mode=? AND ended_at IS NULL',
                       (owner, mode)).fetchone()
    if not run:
        cur = conn.execute('INSERT INTO challenge_runs(owner,mode,rules_version,created_at) VALUES(?,?,?,?)',
                           (owner, mode, RULES_VERSION, time.time()))
        run = conn.execute('SELECT * FROM challenge_runs WHERE id=?', (cur.lastrowid,)).fetchone()
    return run


def owns_round(conn, row, mode):
    """Check that a saved round belongs to this browser's run for the requested
    challenge mode.
    """
    if row is None or row['run_id'] is None:
        return False
    return conn.execute('SELECT 1 FROM challenge_runs WHERE id=? AND owner=? AND mode=?',
                        (row['run_id'], session.get('challenge_owner'), mode)).fetchone() is not None


def pending_round(conn, run, mode):
    """Read the unfinished round for the current persisted challenge run."""
    return conn.execute('SELECT * FROM '+TABLES[mode]+' WHERE run_id=? AND completed_at IS NULL',
                        (run['id'],)).fetchone()


def progress(conn, run_id, mode):
    """Resolve streak and score from the last completed round, starting new runs at
    zero.
    """
    row = conn.execute('SELECT streak_after,user_score_after FROM '+TABLES[mode]+
                       ' WHERE run_id=? AND completed_at IS NOT NULL ORDER BY id DESC LIMIT 1',
                       (run_id,)).fetchone()
    return dict(streak=int(row['streak_after']) if row else 0,
                score=float(row['user_score_after']) if row else 0.0)


def close_on_miss(conn, run_id, passed, now):
    if not passed:
        conn.execute('UPDATE challenge_runs SET ended_at=MAX(created_at,?) WHERE id=? AND ended_at IS NULL',
                     (now, run_id))


def records(conn, mode):
    """Separate progressive records, derived from completed results only; no owner IDs."""
    table = TABLES[mode]
    try:
        result = dict(conn.execute('SELECT COUNT(*) rounds,COALESCE(MAX(streak_after),0) best_streak,'
            'COALESCE(MAX(user_score_after),0) best_score,COUNT(DISTINCT run_id) runs,'
            'COALESCE((SELECT streak_after FROM '+table+' WHERE rules_version=2 AND completed_at IS NOT NULL '
            'ORDER BY completed_at DESC,id DESC LIMIT 1),0) streak FROM '+table+
            ' WHERE rules_version=2 AND completed_at IS NOT NULL').fetchone())
    except sqlite3.OperationalError:
        # Isolated old-schema reporting/reconciliation must stay read-only too.
        if 'rules_version' not in {r[1] for r in conn.execute('PRAGMA table_info('+table+')')}:
            return dict(rounds=0,best_streak=0,best_score=0.0,rules_version=RULES_VERSION,runs=0,streak=0)
        raise
    result.update(rules_version=RULES_VERSION, streak=int(result['streak']),
                  best_streak=int(result['best_streak']), best_score=round(result['best_score'], 4))
    return result
