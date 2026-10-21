"""Serve disposable Vibe Map data for real-browser CI checks; never run Git sync."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from threading import Thread
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    chrome=next((shutil.which(name) for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if shutil.which(name)),None)
    if not chrome:raise SystemExit('A Chromium browser is required for this integration check.')
    with tempfile.TemporaryDirectory(prefix='vibe-browser-') as temporary:
        os.environ['SONG_RANKER_DB']=str(Path(temporary)/'vibe.db')
        from songranker.storage.database import initialize_database
        initialize_database(os.environ['SONG_RANKER_DB'])
        with sqlite3.connect(os.environ['SONG_RANKER_DB']) as conn:
            conn.execute("INSERT INTO albums(id,title,cover_url) VALUES(1,'A long album title for responsive testing','/vibe-test-art.svg')")
            conn.execute("INSERT INTO artists(id,name,cover_url) VALUES(1,'Artist with a longer name','/vibe-test-art.svg')")
            conn.execute("INSERT INTO genres(id,name) VALUES(1,'Melancholy'),(2,'Hopeful')")
            conn.execute("INSERT INTO albums(id,title,cover_url) VALUES(2,'Second album','/vibe-test-art.svg')")
            for sid in range(1,7):
                conn.execute('INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,?,?)',
                             (sid,'A song with a long title '+str(sid),1 if sid<=3 else 2,sid))
                conn.execute('INSERT INTO song_artists VALUES(?,1)',(sid,))
                conn.execute('INSERT INTO song_genres VALUES(?,?)',(sid,1 if sid<=3 else 2))
                if sid>1:
                    conn.execute("UPDATE song_vibe_positions SET x=?,y=?,status='placed',sample_count=1,updated_at=1 WHERE song_id=?",((sid-3)/3,(sid-4)/4,sid))
            conn.execute("INSERT INTO albums(id,title) VALUES(3,'Unmapped album')")
            conn.execute("INSERT INTO artists(id,name) VALUES(2,'Unmapped artist')")
            conn.execute("INSERT INTO genres(id,name) VALUES(3,'Unmapped tag')")
            conn.execute("INSERT INTO songs(id,title,album_id) VALUES(7,'Unmapped song',3)")
            conn.execute('INSERT INTO song_artists VALUES(7,2)')
            conn.execute('INSERT INTO song_genres VALUES(7,3)')
        import main as application  # WSGI import never launches the Git updater.
        from flask import Response
        from werkzeug.serving import make_server
        from songranker.modes import vibe_map
        vibe_map.READJUST_SECONDS=.3
        vibe_map.vibe_song=lambda conn,previous=None:dict(id=2 if previous==1 else 1)

        @application.app.get('/vibe-test-art.svg')
        def cover():
            return Response('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#8b465c"/><circle cx="200" cy="180" r="100" fill="#352f47"/></svg>',mimetype='image/svg+xml')

        server=make_server('127.0.0.1',0,application.app,threaded=True)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env=dict(os.environ,VIBE_TEST_URL=f'http://127.0.0.1:{server.server_port}',VIBE_TEST_CHROME=chrome)
            subprocess.run(['node','tools/vibe_browser_check.cjs'],cwd=ROOT,env=env,check=True)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':main()
