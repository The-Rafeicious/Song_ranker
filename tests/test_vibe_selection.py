"""Coverage-first Vibe Map draws; no results or counters are written."""
import math
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from songranker.modes.selection import (choose_vibe_song, vibe_probabilities,
    exposure_probabilities)
from songranker.modes.selection import vibe_song
from songranker.storage.database import initialize_database
from songranker.storage.database_io import capture


class VibeSelectionTests(unittest.TestCase):
    def songs(self, counts):
        return [dict(id=i+1, vibe_attempts=count, added_at=0)
                for i,count in enumerate(counts)]

    def test_single_unmapped_song_keeps_priority_in_a_large_seen_catalogue(self):
        songs = self.songs([0]+[1]*500+[2]*500)
        weights = vibe_probabilities(songs)
        self.assertGreaterEqual(weights[0],.95)
        self.assertTrue(all(w>0 and math.isfinite(w) for w in weights))
        self.assertAlmostEqual(sum(weights),1)

    def test_one_and_two_visits_cannot_crowd_out_untouched_songs(self):
        songs = self.songs([0,1,2])
        weights = vibe_probabilities(songs)
        self.assertGreater(weights[0],20*weights[1])
        self.assertGreater(weights[0],20*weights[2])
        self.assertGreater(weights[1],0)
        self.assertGreater(weights[2],0)

    def test_later_passes_still_favour_the_least_visited_group(self):
        songs = self.songs([1]+[2]*100+[3]*100)
        weights = vibe_probabilities(songs)
        self.assertGreaterEqual(weights[0],.75)
        self.assertTrue(all(w>0 for w in weights))
        self.assertAlmostEqual(sum(weights),1)

    def test_equal_coverage_uses_the_existing_adaptive_distribution(self):
        songs = self.songs([2,2,2])
        songs[0]['added_at']=1000000
        actual = vibe_probabilities(songs,now=1000000)
        expected = exposure_probabilities([2,2,2],[1000000,0,0],now=1000000)
        for a,b in zip(actual,expected):self.assertAlmostEqual(a,b)
        self.assertGreater(actual[0],actual[1])

    def test_soft_recency_never_excludes_the_only_unmapped_song(self):
        songs = self.songs([0,1,2])
        self.assertGreaterEqual(vibe_probabilities(songs,previous=1)[0],.95)
        equal = vibe_probabilities(self.songs([0,0,0]),previous=1)
        self.assertGreater(equal[0],0)
        self.assertLess(equal[0],equal[1])

    def test_empty_single_duplicate_and_unrated_pools(self):
        self.assertIsNone(choose_vibe_song([]))
        self.assertEqual(vibe_probabilities([]),[])
        song=dict(id=1,title='No preview or Elo needed')
        self.assertEqual(choose_vibe_song([song,song,dict(title='No ID')]),song)
        self.assertEqual(vibe_probabilities([song]),[1])

    def test_counts_are_mode_specific_and_inputs_are_unchanged(self):
        songs=self.songs([0,2,1]);before=[dict(s) for s in songs]
        for s in songs:s.update(matches_played=999,attempts=999,elo_score=-999)
        self.assertGreaterEqual(vibe_probabilities(songs)[0],.95)
        weights=vibe_probabilities(songs,counts={1:2,2:0,3:1})
        self.assertGreaterEqual(weights[1],.95)
        choose_vibe_song(songs,random.Random(1))
        self.assertEqual([{k:s[k] for k in before[0]} for s in songs],before)

    def test_seeded_draws_cover_a_pass_without_leaving_a_large_tail(self):
        songs=self.songs([0]*100)
        for seed in range(10):
            rng=random.Random(seed);counts=dict.fromkeys(range(1,101),0)
            previous=None
            for draw in range(120):
                chosen=choose_vibe_song(songs,rng,counts=counts,previous=previous)
                counts[chosen['id']]+=1;previous=chosen['id']
                if min(counts.values())>0:break
            self.assertGreater(min(counts.values()),0,(seed,counts))
            self.assertLessEqual(max(counts.values()),4)


class VibeSelectionDataTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'songs.db';initialize_database(self.path)
        self.conn=sqlite3.connect(self.path);self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON');self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO songs(id,title) VALUES(1,'Untouched'),(2,'Partial'),(3,'Complete')")
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=0,y=0,updated_at=1 WHERE song_id=2 AND map_id='pace_mood'")
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=.2,y=.4,updated_at=1 WHERE song_id=3")
        self.conn.execute("UPDATE song_vibe_positions SET status='not_applicable',x=NULL,y=NULL WHERE song_id=3 AND map_id='sound_impact'")
        self.conn.commit()

    def test_reader_counts_only_resolved_passes_and_hydrates_the_chosen_song(self):
        from songranker.modes import selection
        before=capture(self.conn)
        with patch.object(selection,'choose_vibe_song',return_value=dict(id=1)) as choose:
            result=vibe_song(self.conn,previous=3,rng=random.Random(1))
        self.assertEqual(choose.call_args.kwargs['counts'],{1:0,2:0,3:1})
        self.assertEqual(choose.call_args.kwargs['previous'],3)
        self.assertEqual(result['title'],'Untouched')
        self.assertEqual(len(result['vibe_maps']),4)
        self.assertEqual(capture(self.conn),before)

    def test_explicit_repeat_counts_override_only_supplied_entries(self):
        from songranker.modes import selection
        with patch.object(selection,'choose_vibe_song',return_value=dict(id=3)) as choose:
            vibe_song(self.conn,counts={3:2})
        self.assertEqual(choose.call_args.kwargs['counts'],{1:0,2:0,3:2})

    def test_real_draws_do_not_mark_songs_seen_or_change_results(self):
        before=capture(self.conn)
        rng=random.Random(42)
        results=[vibe_song(self.conn,rng=rng)['id'] for _ in range(200)]
        self.assertGreater(sum(sid in (1,2) for sid in results),180)
        self.assertEqual(capture(self.conn),before)

    def test_empty_database_returns_none(self):
        self.conn.execute('DELETE FROM songs');self.conn.commit()
        self.assertIsNone(vibe_song(self.conn))


if __name__=='__main__':unittest.main()
