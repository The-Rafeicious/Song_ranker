"""Song Ranker entry point. Shared data helpers live in services and catalog;
page, game and developer routes are registered by their respective modules.
"""
from services import app, init_db, git_pull, ROOT
import pages  # Registers page and library routes.
import games  # Registers voting, trivia and tournament routes.
import dev    # Registers authenticated database tools.

init_db()

if __name__ == '__main__':
    if (ROOT / '.git').exists():
        git_pull()
        init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
