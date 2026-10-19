"""Read-only old/new Impact comparison on a supplied SQLite catalogue."""
import argparse
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from impact import calibrate,measure


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--database',required=True);args=parser.parse_args()
    conn=sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    try:
        songs={r['id']:dict(r) for r in conn.execute('SELECT id,elo_score FROM songs')}
        queries={'artists':'SELECT a.id,a.name,s.id song_id FROM artists a JOIN song_artists l ON l.artist_id=a.id JOIN songs s ON s.id=l.song_id',
            'albums':"SELECT a.id,a.title name,s.id song_id FROM albums a JOIN songs s ON s.album_id=a.id WHERE TRIM(a.title)!='' AND LOWER(TRIM(a.title))!='unknown album' AND LOWER(TRIM(a.title)) NOT LIKE '% - single'",
            'tags':'SELECT a.id,a.name,s.id song_id FROM genres a JOIN song_genres l ON l.genre_id=a.id JOIN songs s ON s.id=l.song_id'}
        for kind,query in queries.items():
            groups={}
            for row in conn.execute(query):groups.setdefault(row['id'],dict(name=row['name'],songs={} ))['songs'][row['song_id']]=songs[row['song_id']]
            context=calibrate(songs.values(),[g['songs'].values() for g in groups.values()]);rows=[]
            for g in groups.values():
                values=list(g['songs'].values());result=measure(values,context)
                rows.append(dict(name=g['name'],n=len(values),old=1200+sum(s['elo_score']-1200 for s in values),**result))
            print(kind,':',len(rows),'groups; typical tracks',context['prior_tracks'],'; baseline',round(context['baseline'],2))
            if not rows:
                print('No rated groups.');continue
            print('Old range',round(min(r['old'] for r in rows),2),round(max(r['old'] for r in rows),2),'New range',round(min(r['impact_score'] for r in rows),2),round(max(r['impact_score'] for r in rows),2))
            for r in sorted(rows,key=lambda r:-r['impact_score'])[:5]:print(f"  {r['name']} | {r['n']} tracks | old {r['old']:.2f} | average {r['impact_average']:.2f} | Impact {r['impact_score']:.2f}")
    finally:conn.close()

if __name__=='__main__':main()
