"""Song Ranker entry point. Shared data helpers live in services and catalog;
page, game and developer routes are registered by their respective modules.
"""
from services import app, init_db, git_pull, ROOT
import apple_access  # Registers streamed preview diagnostics and request safeguards.
import pages  # Registers page and library routes.
import trivia  # Registers field-by-field trivia routes.
import games  # Registers voting and tournament routes.
import metadata_tools  # Registers fill-only metadata scans.
import dev    # Registers authenticated database tools.

init_db()

if __name__ == '__main__':
    if (ROOT / '.git').exists():
        git_pull()
        init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
