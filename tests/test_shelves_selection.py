"""Soft album-first Shelves balance across capacity, artists and exposure."""
import random
import unittest
from collections import Counter
from songranker.modes.selection import draw_shelves, shelf_album_weights


def groups(*sizes):
    return {aid: [dict(id=aid*100+i, album_id=aid) for i in range(size)]
            for aid, size in enumerate(sizes, 1)}


class ShelvesSelectionTests(unittest.TestCase):
    def test_size_preference_is_stronger_in_two_album_rounds(self):
        pool=groups(3,8,20)
        two=shelf_album_weights(pool, {}, {}, 2)
        three=shelf_album_weights(pool, {}, {}, 3)
        self.assertGreater(two[3],two[2]); self.assertGreater(two[2],two[1])
        self.assertGreater(two[3]/two[1],three[3]/three[1])
        self.assertAlmostEqual(sum(two.values()),1)
        self.assertGreater(min(two.values()),0)
        # Once the large album's songs are well tested, untouched albums recover.
        counts={s['id']:100 for s in pool[3]}
        caught_up=shelf_album_weights(pool,{3:400},counts,2)
        self.assertLess(caught_up[3],caught_up[2])

    def test_formats_remain_even_and_all_draws_are_unique_and_feasible(self):
        pool=groups(2,4,8,16);rng=random.Random(781);formats=Counter()
        for _ in range(1200):
            albums,tracks=draw_shelves(pool,{}, {}, [],rng=rng)
            formats[len(albums)]+=1
            self.assertEqual(len(tracks),10)
            self.assertEqual(len({s['id'] for s in tracks}),10)
            self.assertTrue(all(sum(s['album_id']==aid for s in tracks)>=2 for aid in albums))
        self.assertTrue(.46 < formats[2]/1200 < .54,formats)
        self.assertIsNone(draw_shelves(groups(2,2),{}, {}, []))
        self.assertEqual(len(draw_shelves(groups(3,3,4),{}, {}, [],rng=random.Random(1))[0]),3)

    def test_artist_affinity_is_soft_and_previous_albums_are_not_banned(self):
        pool=groups(8,8,8,8);artists={1:{1},2:{1},3:{2},4:{2}};rng=random.Random(241)
        paired=mixed=repeated=0
        for _ in range(1600):
            albums,_=draw_shelves(pool,{}, {}, [[1,2]],count=2,rng=rng,album_artists=artists)
            paired+=bool(artists[albums[0]] & artists[albums[1]])
            mixed+=not bool(artists[albums[0]] & artists[albums[1]])
            repeated+=bool(set(albums)&{1,2})
        self.assertGreater(paired,1600/3)
        self.assertGreater(mixed,100)
        self.assertGreater(repeated,100)

    def test_tracks_favour_low_exposure_without_a_fixed_order_or_quota(self):
        pool=groups(12,12);counts={s['id']:50 if i<6 else 0 for tracks in pool.values() for i,s in enumerate(tracks)}
        selected=Counter();rng=random.Random(709)
        for _ in range(700):
            _,tracks=draw_shelves(pool,{},counts,[],count=2,rng=rng)
            selected.update(s['id'] for s in tracks)
        low=sum(n for sid,n in selected.items() if counts[sid]==0)
        high=sum(n for sid,n in selected.items() if counts[sid]>0)
        self.assertGreater(low,high*1.5)
        self.assertTrue(all(selected[s['id']]>0 for tracks in pool.values() for s in tracks))
