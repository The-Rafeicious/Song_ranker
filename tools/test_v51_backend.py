"""One synthetic decision per new mode, always in a fresh safe-mode test copy.

Run from the app folder: python tools/test_v51_backend.py
No live-result switch is provided. This checks contracts, not audio playback.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import sqlite3
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['SONG_RANKER_SAFE_MODE']='1'  # Must precede every app import.

import main
from songranker import services


def run():
    if not services.runtime.safe:raise RuntimeError('This tool only runs in safe mode.')
    # Keep synthetic smoke results out of the persistent user test database too.
    with tempfile.TemporaryDirectory(prefix='.backend_smoke_',dir=services.runtime.run_dir) as folder:
        candidate=Path(folder)/'smoke.db'
        source=sqlite3.connect(services.DB_NAME);target=sqlite3.connect(candidate)
        try:source.backup(target)
        finally:target.close();source.close()
        with patch.object(services,'DB_NAME',str(candidate)):
            return _run()


def _run():
    client=main.app.test_client();report=dict(runtime=services.runtime.status(paths=True),modes=[])
    for slug in ('shared-spotlight','vibe-map'):
        response=client.post('/api/'+slug+'/round',json={})
        if response.status_code!=200:
            report['modes'].append(dict(mode=slug,status='unavailable',message=response.get_json().get('message')))
            continue
        offered=response.get_json()
        answer=dict(token=offered['token'],rules_version=offered['rules_version'])
        if slug=='shared-spotlight':
            if offered['rules_version']==2:answer['positions']=[80,60,40,20]
            else:answer['allocations']=[5,4,2,1]
        elif slug=='vibe-map':answer['maps']=[dict(map='mood',x=2,y=2)]
        response=client.post('/api/'+slug+'/answer',json=answer)
        if response.status_code!=200:raise RuntimeError(response.get_json())
        retried=client.post('/api/'+slug+'/answer',json=answer)
        if retried.status_code!=200 or not retried.get_json()['replayed']:raise RuntimeError('Receipt retry failed.')
        stats=client.get('/api/'+slug+'/stats')
        if stats.status_code!=200:raise RuntimeError('Statistics failed.')
        report['modes'].append(dict(mode=slug,status='passed',summary=stats.get_json()['summary']))
    overall=client.get('/api/overall')
    if overall.status_code!=200:raise RuntimeError('Overall projection failed.')
    report['overall']=overall.get_json()['summary']
    report['synthetic_results']='Test copy only. Never imported or pushed into the main database.'
    return report


if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
