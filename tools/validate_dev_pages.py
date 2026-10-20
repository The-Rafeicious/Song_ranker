"""Run all Dev screens against a disposable fixture, with mocked Apple transport.

Requires the app dependencies, Node and jsdom. No active database is opened.
This is DOM/HTTP integration, not browser-paint or real-device validation.
"""
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    with tempfile.TemporaryDirectory(prefix='.dev_check_', dir=ROOT) as folder:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, SONG_RANKER_QA_URL=f'http://127.0.0.1:{port}')
        server = subprocess.Popen([sys.executable, __file__, '--serve', str(Path(folder)/'test.db'), str(port)],
                                  cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError('Fixture server stopped before validation.')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.2):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Fixture server could not start.')
            return subprocess.run(['node', 'tests/test_dev_pages.js'], cwd=ROOT, env=env).returncode
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':
        import os
        import sys
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        os.environ['SONG_RANKER_DB']=str(Path(sys.argv[2]))
        os.environ['SONG_RANKER_PIN']='qa-test-pin'
        os.environ['SONG_RANKER_SECRET']='isolated-local-ui-test-secret-000000000000'
        from songranker.storage.database import initialize_database
        initialize_database(os.environ['SONG_RANKER_DB'])
        from songranker import services
        c=services.get_db_connection()
        if not c.execute('SELECT 1 FROM songs').fetchone():
            for i in range(1,17):
                c.execute('INSERT INTO albums(id,title,release_date) VALUES(?,?,?)',(i,('An extraordinarily long album title to check wrapping across screens' if i==1 else f'Album {i}'),'2026-01-01'))
                c.execute('INSERT INTO artists(id,name) VALUES(?,?)',(i,f'Artist {i} with a long name' if i==1 else f'Artist {i}'))
                c.execute('INSERT INTO genres(id,name,description) VALUES(?,?,?)',(i,f'Tag {i}',f'Tag {i} description and listening notes'))
            for i in range(1,81):
                c.execute('INSERT INTO songs(id,title,album_id,track_number) VALUES(?,?,?,?)',(i,'A very long song title that should stay readable and bounded on phones' if i==1 else f'Song {i}',(i-1)//5+1,(i-1)%5+1))
                c.execute('INSERT INTO song_artists VALUES(?,?)',(i,(i-1)//5+1))
                if i%3:c.execute('INSERT INTO song_genres VALUES(?,?)',(i,(i-1)%16+1))
            c.commit()
        c.close()
        import main
        from songranker.developer import dev
        # Only the Apple lookup transport is mocked; imports still use the real DB route.
        def lookup(url):
            return {'results':[{'kind':'song','trackId':9000+i,'collectionId':8001,'artistId':7001,'trackName':f'New import {i}','artistName':'Test artist','collectionName':'Import album - EP','trackNumber':i,'discNumber':1,'discCount':1,'releaseDate':'2026-01-01T00:00:00Z','trackViewUrl':f'https://music.apple.com/us/album/test/8001?i={9000+i}','collectionViewUrl':'https://music.apple.com/us/album/test/8001','trackExplicitness':'notExplicit'} for i in range(1,6)]}
        dev.apple_lookup=lookup
        main.app.run(host='127.0.0.1',port=int(sys.argv[3]),use_reloader=False,threaded=True)
    else:
        raise SystemExit(run())
