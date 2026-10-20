"""Convenience launcher: always resume the isolated safe test database."""
import os
import runpy
from pathlib import Path

if __name__=='__main__':
    os.environ['SONG_RANKER_SAFE_MODE']='1'
    runpy.run_path(str(Path(__file__).with_name('main.py')),run_name='__main__')
