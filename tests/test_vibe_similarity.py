"""Bounded similarity, adaptive coverage and hotspot-aware production draws."""
from copy import deepcopy
import math
import random
import unittest
from unittest.mock import patch

from songranker.modes import selection as S
from songranker.modes.vibe_similarity import (SongVibeBias, AlbumVibeBias,
    positions, MAX_BIAS)
from songranker.storage.vibe_state import MAPS


def song(sid, x=None, y=None, maps=4, **extra):
    return dict(id=sid, elo_score=1200+sid, added_at=0, **extra,
        vibe_maps={key:dict(status='placed',x=x,y=y) if x is not None and i<maps
                   else dict(status='unmapped',x=None,y=None)
                   for i,(key,*_) in enumerate(MAPS)})


class VibeSimilarityTests(unittest.TestCase):
    def test_close_and_far_weights_are_gentle_and_bounded(self):
        rows=[song(1,-1,-1),song(2,-1,-1),song(3,1,1)]
        bias=SongVibeBias(rows)
        self.assertEqual(bias.coverage,1)
        self.assertAlmostEqual(bias.multiplier(1,2),1.15)
        self.assertGreaterEqual(bias.multiplier(1,3),.85)
        self.assertLess(bias.multiplier(1,3),1)
        self.assertLessEqual(bias.multiplier(1,2)/bias.multiplier(1,3),1.15/.85)

    def test_coverage_and_shared_evidence_scale_smoothly(self):
        dense=SongVibeBias([song(1,0,0),song(2,0,0)])
        sparse=SongVibeBias([song(1,0,0),song(2,0,0)]+[song(i) for i in range(3,103)])
        partial=SongVibeBias([song(1,0,0,maps=1),song(2,0,0,maps=1)])
        self.assertLess(sparse.strength,dense.strength)
        self.assertGreater(sparse.multiplier(1,2),1)
        self.assertLess(sparse.multiplier(1,2),dense.multiplier(1,2))
        self.assertAlmostEqual(partial.multiplier(1,2),1+MAX_BIAS/16)

    def test_unknown_and_not_applicable_are_neutral_not_centre_points(self):
        rows=[song(1,0,0),song(2)]
        self.assertEqual(SongVibeBias(rows).multiplier(1,2),1)
        for point in rows[1]['vibe_maps'].values():point['status']='not_applicable'
        self.assertEqual(positions(rows[1]),{})
        self.assertEqual(SongVibeBias(rows).multiplier(1,2),1)
        self.assertEqual(SongVibeBias([]).strength,0)

    def test_invalid_or_partial_coordinates_are_not_evidence(self):
        for x,y in ((math.nan,0),(math.inf,0),(0,None),(2,0),(True,0),('0',0)):
            self.assertEqual(positions(song(1,x,y)),{})

    def test_album_hotspots_do_not_collapse_to_a_false_centre(self):
        groups={1:[song(1,-1,-1),song(2,1,1)],
                2:[song(3,-1,-1),song(4,1,1)],
                3:[song(5,0,0),song(6,0,0)]}
        bias=AlbumVibeBias(groups)
        self.assertGreater(bias.multiplier(1,2),bias.multiplier(1,3))
        self.assertAlmostEqual(bias.multiplier(1,2),1.15)
        self.assertGreaterEqual(bias.multiplier(1,3),.85)

    def test_album_size_does_not_turn_duplicated_hotspots_into_extra_strength(self):
        groups={1:[song(1,-1,-1),song(2,1,1)],
                2:[song(3,-1,-1),song(4,1,1),song(5,-1,-1),song(6,1,1)]}
        self.assertAlmostEqual(AlbumVibeBias(groups).multiplier(1,2),1.15)
        groups[2].append(song(7))
        self.assertLess(AlbumVibeBias(groups).multiplier(1,2),1.15)

    def test_all_unmapped_draws_are_identical_to_missing_profiles(self):
        rows=[song(i) for i in range(1,13)]
        plain=[{k:v for k,v in row.items() if k!='vibe_maps'} for row in rows]
        for seed in range(20):
            for fn in (S.choose_match,S.choose_guess_pair):
                self.assertEqual([s['id'] for s in fn(rows,random.Random(seed))],
                                 [s['id'] for s in fn(plain,random.Random(seed))])
            self.assertEqual([s['id'] for s in S.tournament_tracks(rows,8,random.Random(seed))],
                             [s['id'] for s in S.tournament_tracks(plain,8,random.Random(seed))])

    def captured(self,fn,rows):
        calls=[]
        def choose(weights,rng):
            calls.append(list(weights))
            return next(i for i,w in enumerate(weights) if w>0)
        with patch.object(S,'weighted_index',side_effect=choose):
            fn(rows)
        return calls

    def test_pair_and_tournament_paths_leave_first_draw_unbiased(self):
        rows=[song(i,-1 if i%2 else 1,-1 if i%2 else 1) for i in range(1,13)]
        plain=[{k:v for k,v in row.items() if k!='vibe_maps'} for row in rows]
        for fn in (lambda p:S.choose_match(p,random.Random(1)),
                   lambda p:S.choose_guess_pair(p,random.Random(1)),
                   lambda p:S.draw_entries(p,8,random.Random(1))):
            base=self.captured(fn,plain);adjusted=self.captured(fn,rows)
            self.assertEqual(base[0],adjusted[0])
            for old,new in zip(base[1:],adjusted[1:]):
                for a,b in zip(old,new):
                    if a:self.assertTrue(.85-1e-12 <= b/a <= 1.15+1e-12)
                    else:self.assertEqual(b,0)
                # After normalisation even the most dissimilar candidate retains
                # at least 0.85/1.15 of its previous conditional probability.
                for a,b in zip(old,new):
                    if a:self.assertGreaterEqual(b/sum(new),(.85/1.15)*a/sum(old)-1e-12)

    def test_shelves_keep_capacity_and_apply_album_bias_once(self):
        groups={aid:[song(aid*10+i,-1 if aid%2 else 1,-1 if aid%2 else 1)
                     for i in range(6)] for aid in range(1,5)}
        plain={aid:[{k:v for k,v in s.items() if k!='vibe_maps'} for s in tracks]
               for aid,tracks in groups.items()}
        fn=lambda g:S.draw_shelves(g,{}, {},[],count=2,rng=random.Random(1))
        old=self.captured(fn,plain);new=self.captured(fn,groups)
        self.assertEqual(old[0],new[0])
        self.assertTrue(any(abs(a-b)>1e-9 for a,b in zip(old[1],new[1])))
        for a,b in zip(old[1],new[1]):self.assertTrue(.85<=b/a<=1.15+1e-12)
        for seed in range(30):
            albums,tracks=S.draw_shelves(groups,{}, {},[],count=3,rng=random.Random(seed))
            self.assertEqual(len(albums),3);self.assertEqual(len(tracks),10)
            self.assertEqual(len({s['id'] for s in tracks}),10)
            self.assertTrue(all(sum(s['id']//10==aid for s in tracks)>=2 for aid in albums))

    def test_cross_vibe_pairs_still_occur_frequently(self):
        rows=[song(i,-1 if i<4 else 1,-1 if i<4 else 1) for i in range(8)]
        for row in rows:row['elo_score']=1200
        rng=random.Random(1102);cross=0
        for _ in range(4000):
            a,b=S.choose_match(rows,rng)
            cross+=(a['id']<4)!=(b['id']<4)
        self.assertGreater(cross/4000,.45)
        self.assertLess(cross/4000,.55)

    def test_selection_does_not_change_input_profiles(self):
        rows=[song(i,0,0) for i in range(12)];before=deepcopy(rows)
        S.choose_match(rows,random.Random(1));S.choose_guess_pair(rows,random.Random(2))
        S.tournament_tracks(rows,8,random.Random(3))
        self.assertEqual(rows,before)


class AlbumVibeDataTests(unittest.TestCase):
    def setUp(self):
        import test_preferences as fixture
        fixture.PreferenceTests.setUp(self)

    def connect(self):
        import test_preferences as fixture
        return fixture.PreferenceTests.connect(self)

    def test_shelves_profile_includes_unnumbered_songs_without_drawing_them(self):
        from songranker.modes.selection import album_vibe_groups
        from songranker.modes.shelves import shelf_candidates
        from songranker.storage.database_io import capture
        self.conn.execute("INSERT INTO songs(id,title,album_id) VALUES(11,'Unnumbered',1)")
        self.conn.execute("UPDATE song_vibe_positions SET status='placed',x=-1,y=-1,updated_at=1 WHERE song_id=11")
        self.conn.commit();before=capture(self.conn)
        profiles=album_vibe_groups(self.conn,[1,2])
        self.assertEqual(len(profiles[1]),6)
        self.assertEqual(len(profiles[2]),5)
        self.assertIn(11,{s['id'] for s in profiles[1]})
        self.assertGreater(AlbumVibeBias(profiles).coverage,0)
        albums,tracks=shelf_candidates(self.conn,2)
        self.assertEqual(set(albums),{1,2})
        self.assertNotIn(11,{s['id'] for s in tracks})
        self.assertEqual(len(tracks),10)
        self.assertEqual(capture(self.conn),before)


if __name__=='__main__':unittest.main()
