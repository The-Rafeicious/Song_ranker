"""Song Ranker entry point. Shared data helpers live in services and catalog;
page, game and developer routes are registered by their respective modules.
"""
# Source updates must finish before importing Flask/routes/schema helpers.
import os
import sys
from pathlib import Path

if __name__ == '__main__':
    from songranker.developer.git_sync import GitSync
    startup_root = Path(__file__).resolve().parent
    from songranker.storage.competition import configured_paths
    updater = GitSync(startup_root, str(configured_paths(startup_root)[0]))
    handoff = os.environ.pop('SONG_RANKER_BOOT_COMMIT', '')
    if not handoff or updater.status().get('head') != handoff:
        update = updater.startup()
        print(update['message'], flush=True)
        if update.get('stop_startup'):
            raise SystemExit('Startup stopped so Git can be checked before loading the app.')
        if update.get('code') == 'updated':
            os.environ['SONG_RANKER_BOOT_COMMIT'] = update['head']
            os.execv(sys.executable, [sys.executable, *sys.argv])
            raise SystemExit(0)  # execv does not return in normal use.

from songranker.services import (app, init_db)
from songranker import apple_access  # Registers streamed preview diagnostics and request safeguards.
from songranker import pages  # Registers page and library routes.
from songranker.modes import trivia  # Registers field-by-field trivia routes.
from songranker.modes import special_modes  # Registers independent Elo Guesser and Album Shelves.
from songranker import overall  # Registers derived, calibrated Overall scores; no stored counters.
from songranker.modes import games  # Registers voting and tournament routes.
from songranker.developer import metadata_tools  # Registers fill-only metadata scans.
from songranker.developer import dev    # Registers authenticated database tools.
from songranker.developer import dev_catalog  # Registers verified source review, album inspection and Singles moves.
from songranker.developer import dev_tags  # Registers reviewed tag membership changes; no game facts are edited.
from songranker.developer import dev_system  # Registers dashboard, Git status and reviewed recovery tools.
from songranker.developer import dev_shutdown  # Registers fresh-PIN, acknowledged shutdown.

# WSGI imports bootstrap without running Git or hot-swapping loaded code.
init_db()

if __name__ == '__main__':
    # Also runs when Git was pulled manually or there was no incoming code update.
    database_update = updater.reconcile_database()
    print(database_update['message'], flush=True)
    try:
        from waitress import create_server
    except ImportError as error:
        raise SystemExit('Install the hosting dependency first: python -m pip install -r requirements.txt') from error
    host = os.environ.get('SONG_RANKER_HOST', '0.0.0.0')
    try:
        port = int(os.environ.get('SONG_RANKER_PORT', '5000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as error:
        raise SystemExit('SONG_RANKER_PORT must be between 1 and 65535.') from error
    server = create_server(app, host=host, port=port, threads=4, expose_tracebacks=False,
          clear_untrusted_proxy_headers=True, max_request_body_size=app.config['MAX_CONTENT_LENGTH'])

    from songranker.hosting import register_waitress_shutdown
    register_waitress_shutdown(server, app.extensions['song_ranker_stop'])
    server.run()
