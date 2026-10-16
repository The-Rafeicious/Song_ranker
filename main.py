"""Song Ranker entry point. Shared data helpers live in services and catalog;
page, game and developer routes are registered by their respective modules.
"""
from services import app, init_db, git_pull, ROOT
import apple_access  # Registers streamed preview diagnostics and request safeguards.
import pages  # Registers page and library routes.
import trivia  # Registers field-by-field trivia routes.
import special_modes  # Registers independent Elo Guesser and Album Shelves.
import overall  # Registers derived, calibrated Overall scores; no stored counters.
import games  # Registers voting and tournament routes.
import metadata_tools  # Registers fill-only metadata scans.
import dev    # Registers authenticated database tools.

init_db()

if __name__ == '__main__':
    if (ROOT / '.git').exists():
        git_pull()
        init_db()
    import os
    try:
        from waitress import serve
    except ImportError as error:
        raise SystemExit('Install the hosting dependency first: python -m pip install -r requirements.txt') from error
    host = os.environ.get('SONG_RANKER_HOST', '0.0.0.0')
    try:
        port = int(os.environ.get('SONG_RANKER_PORT', '5000'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as error:
        raise SystemExit('SONG_RANKER_PORT must be between 1 and 65535.') from error
    serve(app, host=host, port=port, threads=4, expose_tracebacks=False,
          clear_untrusted_proxy_headers=True, max_request_body_size=app.config['MAX_CONTENT_LENGTH'])
