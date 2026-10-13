"""Percentile and adaptive participation regressions. Pure data, no DB writes."""
import copy
import json
import math
import unittest
from unittest.mock import patch
import overall
from services import app


def population_data(count=20, plays=2):
    data=dict(songs=[],artists=[],albums=[dict(id=10,title='First'),dict(id=20,title='Second')],tags=[])
    for i in range(count):
        sid=i+1;rate=i/(count-1) if count>1 else .5
        data['songs'].append(dict(id=sid,title=f'Song {sid}',audio_url='preview',
            album_id=10 if i<count//2 else 20,track_number=i+1,
            artist_ids=[1000+sid],tag_ids=[2000+sid],elo_score=1000+400*rate,highest_elo=1000+400*rate,
            matches_played=2*plays,
            voting=dict(matches=2*plays,standard_matches=plays,standard_wins=plays*rate,
                        blind_matches=plays,blind_wins=plays*rate),
            new_attempts=plays,title_correct=plays*rate,artist_correct=plays*rate,
            album_attempts=plays,album_correct=plays*rate,
            tournament_wins=plays*rate,tournament_losses=plays*(1-rate),tournament_appearances=plays,
            guess_attempts=plays,guess_correct=plays*rate,
            shelf_attempts=plays,shelf_order_pairs=4*plays,shelf_order_right=4*plays*rate,
            shelf_album_correct=plays*rate))
        data['artists'].append(dict(id=1000+sid,name=f'Artist {sid}'))
        data['tags'].append(dict(id=2000+sid,name=f'Tag {sid}'))
    return data


def result(data,details=False):
    return overall.evaluate(data,details=details)


def modes(data):
    return {m['key']:m for m in result(data)['calibration']['modes']}


def set_guesses(data,played_ids,plays):
    for song in data['songs']:
        song['guess_attempts']=plays if song['id'] in played_ids else 0
        song['guess_correct']=song['guess_attempts']/2


class PercentileTests(unittest.TestCase):
    def test_adjusted_percentiles_keep_a_wide_range_and_center_at_fifty(self):
        rows=[dict(composite_score=n) for n in range(10,21)]
        overall.apply_percentiles(rows)
        for i,row in enumerate(rows):
            self.assertAlmostEqual(row['score'],2+9.6*i)
            self.assertAlmostEqual(row['rank_percentile'],10*i)
        self.assertEqual(stat_mean(rows),50)

    def test_ties_share_midrank_and_do_not_depend_on_names(self):
        rows=[dict(composite_score=n) for n in [10,10,20]]
        overall.apply_percentiles(rows)
        self.assertEqual([r['score'] for r in rows],[26,26,98])
        self.assertEqual(stat_mean(rows),50)

    def test_single_or_completely_tied_population_is_fifty(self):
        for scores in [[20],[20,20,20]]:
            rows=[dict(composite_score=n) for n in scores]
            overall.apply_percentiles(rows)
            self.assertTrue(all(r['score']==50 for r in rows))

    def test_untested_and_ineligible_records_do_not_distort_percentiles(self):
        rows=[dict(composite_score=0),dict(composite_score=100),dict(composite_score=None),
              dict(composite_score=1000,eligible=False)]
        overall.apply_percentiles(rows)
        self.assertEqual([r['score'] for r in rows],[0,100,None,None])
        self.assertTrue(all(r['percentile_population']==2 for r in rows))

    def test_all_unmeasured_population_stays_unknown(self):
        rows=[dict(composite_score=None),dict(composite_score=None)]
        overall.apply_percentiles(rows)
        self.assertTrue(all(r['score'] is None and r['percentile_population']==0 for r in rows))

    def test_consistently_bad_and_good_songs_land_in_outer_deciles(self):
        rows=result(population_data())['entities']['songs']
        by_id={r['id']:r for r in rows}
        self.assertLessEqual(by_id[2]['score'],10)
        self.assertGreaterEqual(by_id[19]['score'],90)
        self.assertEqual(by_id[1]['score'],2)
        self.assertEqual(by_id[20]['score'],98)
        self.assertAlmostEqual(stat_mean(rows),50)

    def test_each_entity_category_has_its_own_centered_cohort(self):
        for kind,rows in result(population_data())['entities'].items():
            with self.subTest(kind=kind):
                measured=[r for r in rows if r['score'] is not None]
                self.assertEqual(min(r['score'] for r in measured),2)
                self.assertEqual(max(r['score'] for r in measured),98)
                self.assertAlmostEqual(stat_mean(measured),50)

    def test_percentiles_are_stable_under_catalogue_reordering(self):
        data=population_data();old=result(data)
        for key in ('songs','artists','albums','tags'):data[key].reverse()
        new=result(data)
        for kind in old['entities']:
            self.assertEqual({r['id']:r['score'] for r in old['entities'][kind]},
                             {r['id']:r['score'] for r in new['entities'][kind]})


class EvidenceTests(unittest.TestCase):
    def test_average_half_average_and_high_reference_have_expected_evidence(self):
        ref=overall.exposure_reference([1,2,3,4,5])
        self.assertAlmostEqual(overall.relative_evidence(ref['average_appearances']/2,ref),.25)
        self.assertAlmostEqual(overall.relative_evidence(ref['average_appearances'],ref),.5)
        self.assertEqual(overall.relative_evidence(ref['high_appearances'],ref),1)
        self.assertEqual(overall.relative_evidence(0,ref),0)
        self.assertEqual(overall.relative_evidence(1000,ref),1)

    def test_relative_evidence_scales_from_one_or_two_to_ten_or_twenty(self):
        young=overall.exposure_reference([1,2]);mature=overall.exposure_reference([10,20])
        for n in [0,1,1.5,2,3]:
            self.assertAlmostEqual(overall.relative_evidence(n,young),overall.relative_evidence(10*n,mature))

    def test_flat_population_has_finite_average_centered_evidence(self):
        ref=overall.exposure_reference([1]*20)
        self.assertEqual(overall.relative_evidence(1,ref),.5)
        self.assertEqual(overall.relative_evidence(2,ref),1)
        self.assertEqual(overall.relative_evidence(0,overall.exposure_reference([])),0)

    def test_a_song_left_behind_loses_relative_evidence(self):
        data=population_data(20,2);old=result(data)
        old_evidence=next(r for r in old['entities']['songs'] if r['id']==1)['evidence']
        mature=population_data(20,20);mature['songs'][0]=data['songs'][0]
        new_evidence=next(r for r in result(mature)['entities']['songs'] if r['id']==1)['evidence']
        self.assertLess(new_evidence,old_evidence/3)

    def test_low_exposure_shrinks_both_good_and_bad_results_towards_neutral(self):
        for raw in [0,1]:
            ref=dict(kind='rate',mean=.5,average_appearances=10,high_appearances=20)
            low,e_low=overall.metric_score(overall.feature(raw,1),ref)
            high,e_high=overall.metric_score(overall.feature(raw,20),ref)
            self.assertLess(abs(low-.5),abs(high-.5))
            self.assertLess(e_low,e_high)

    def test_uniform_growth_keeps_relative_evidence_and_weights(self):
        young=result(population_data(20,2));mature=result(population_data(20,20))
        for old,new in zip(young['entities']['songs'],mature['entities']['songs']):
            self.assertEqual(old['id'],new['id'])
            self.assertAlmostEqual(old['evidence'],new['evidence'])
            self.assertAlmostEqual(old['composite_score'],new['composite_score'])
            self.assertEqual(old['score'],new['score'])
        for old,new in zip(young['calibration']['modes'],mature['calibration']['modes']):
            self.assertAlmostEqual(old['weight'],new['weight'])


class AdaptiveWeightTests(unittest.TestCase):
    def test_voting_base_shares_form_one_twenty_percent_family(self):
        data=population_data();m=modes(data)
        self.assertEqual(sum(m[k]['base_weight'] for k in ['elo','standard','blind']),20)
        for key in ['trivia','tournament','guesser','shelves']:self.assertEqual(m[key]['base_weight'],20)
        self.assertLessEqual(sum(m[k]['weight'] for k in ['elo','standard','blind']),30+1e-9)
        self.assertAlmostEqual(sum(row['weight'] for row in m.values()),100)

    def test_sparse_game_gains_weight_as_more_eligible_songs_play_it(self):
        data=population_data(20,10);set_guesses(data,{1},1);low=modes(data)['guesser']['weight']
        set_guesses(data,set(range(1,21)),1);broad=modes(data)['guesser']['weight']
        set_guesses(data,set(range(1,21)),10);deep=modes(data)['guesser']['weight']
        self.assertLess(low,broad)
        self.assertLess(broad,deep)

    def test_a_mode_that_is_left_behind_loses_weight_as_other_modes_grow(self):
        young=population_data(20,2);before=modes(young)['guesser']['weight']
        mature=population_data(20,20);set_guesses(mature,set(range(1,21)),2)
        self.assertLess(modes(mature)['guesser']['weight'],before)

    def test_heavy_voting_cannot_take_over_all_five_games(self):
        data=population_data()
        for song in data['songs']:
            song['matches_played']=20000
            song['voting']=dict(matches=20000,standard_matches=10000,standard_wins=5000,
                                blind_matches=10000,blind_wins=5000)
        m=modes(data)
        self.assertLessEqual(sum(m[k]['weight'] for k in ['elo','standard','blind']),30+1e-9)
        self.assertAlmostEqual(sum(row['weight'] for row in m.values()),100)

    def test_no_result_game_has_zero_weight(self):
        data=population_data()
        set_guesses(data,set(),0)
        m=modes(data)
        self.assertEqual(m['guesser']['weight'],0)
        self.assertFalse(m['guesser']['active'])
        self.assertAlmostEqual(sum(row['weight'] for row in m.values()),100)

    def test_family_caps_still_apply_after_an_ineligible_game_is_omitted(self):
        data=population_data();data['songs'][0]['album_id']=None
        for song in data['songs']:
            song['matches_played']=20000
            song['voting']=dict(matches=20000,standard_matches=10000,standard_wins=5000,
                                blind_matches=10000,blind_wins=5000)
        song=next(row for row in result(data)['entities']['songs'] if row['id']==1)
        voting=sum(c['weight'] for c in song['contributions'] if c['key'] in ('elo','standard','blind'))
        self.assertLessEqual(voting,35+1e-9)
        self.assertAlmostEqual(sum(c['weight'] for c in song['contributions']),100)

    def test_all_unplayed_library_has_no_active_modes_or_percentiles(self):
        data=population_data(20,0);r=result(data)
        self.assertEqual(r['summary']['active_modes'],0)
        self.assertTrue(all(m['weight']==0 for m in r['calibration']['modes']))
        self.assertTrue(all(s['score'] is None for s in r['entities']['songs']))

    def test_one_new_play_refreshes_weights_without_a_threshold_delay(self):
        data=population_data();old=result(data)
        data['songs'][0]['guess_attempts']+=1
        new=result(data)
        self.assertNotEqual(old['calibration']['id'],new['calibration']['id'])
        self.assertNotEqual(old['calibration']['modes'][5]['weight'],new['calibration']['modes'][5]['weight'])

    def test_unchanged_snapshot_can_reuse_the_same_calibration(self):
        data=population_data();old=result(data)['calibration'];new=result(data)['calibration']
        self.assertIs(old,new)


class EligibilityAndCollectionTests(unittest.TestCase):
    def test_no_album_song_omits_shelves_and_album_recognition_and_keeps_full_allocation(self):
        data=population_data();data['songs'][0]['album_id']=None
        song=next(s for s in result(data,True)['entities']['songs'] if s['id']==1)
        self.assertNotIn('shelves',[c['key'] for c in song['contributions']])
        metrics=[m for c in song['contributions'] for m in c['metrics']]
        self.assertNotIn('trivia_album',[m['key'] for m in metrics])
        self.assertAlmostEqual(sum(m['weight'] for m in metrics),100)
        self.assertAlmostEqual(sum(m['weight']*m['adjusted']/100 for m in metrics),song['composite_score'])

    def test_ineligible_album_stats_cannot_change_the_song_score(self):
        data=population_data();data['songs'][0]['album_id']=None;old=result(data)
        data['songs'][0].update(album_attempts=10000,album_correct=10000,
            shelf_attempts=10000,shelf_album_correct=10000,shelf_order_pairs=10000,shelf_order_right=10000)
        new=result(data)
        self.assertEqual(next(s['composite_score'] for s in old['entities']['songs'] if s['id']==1),
                         next(s['composite_score'] for s in new['entities']['songs'] if s['id']==1))

    def test_single_unknown_album_missing_slots_and_duplicate_slots_are_ineligible_for_shelves(self):
        data=population_data()
        data['albums'][0]['title']='First - Single'
        ids=overall.shelf_eligible_ids(data)
        self.assertTrue(all(s['id'] not in ids for s in data['songs'][:10]))
        data['albums'][0]['title']='Unknown Album'
        self.assertTrue(all(s['id'] not in overall.shelf_eligible_ids(data) for s in data['songs'][:10]))
        data['albums'][0]['title']='First';data['songs'][0]['track_number']=None
        data['songs'][1]['track_number']=data['songs'][2]['track_number']
        ids=overall.shelf_eligible_ids(data)
        self.assertTrue(all(sid not in ids for sid in [1,2,3]))

    def test_shelves_participation_denominator_excludes_ineligible_songs(self):
        data=population_data();data['songs'][0]['album_id']=None
        m=modes(data)['shelves']
        self.assertEqual(m['eligible_songs'],19)
        self.assertEqual(m['tested_songs'],19)
        self.assertEqual(m['participation'],1)

    def test_no_audio_song_omits_blind_and_trivia(self):
        data=population_data();data['songs'][0]['audio_url']=''
        song=next(s for s in result(data,True)['entities']['songs'] if s['id']==1)
        self.assertNotIn('blind',[c['key'] for c in song['contributions']])
        self.assertNotIn('trivia',[c['key'] for c in song['contributions']])
        m=modes(data);self.assertEqual(m['trivia']['eligible_songs'],19)
        self.assertEqual(m['blind']['eligible_songs'],19)

    def test_collection_members_can_have_different_eligible_modes(self):
        data=population_data();data['songs'][0]['album_id']=None
        data['songs'][0]['artist_ids']=[1002]
        artist=next(r for r in result(data,True)['entities']['artists'] if r['id']==1002)
        self.assertEqual(artist['track_count'],2)
        shelves=next(c for c in artist['contributions'] if c['key']=='shelves')
        self.assertEqual(shelves['applicable_tracks'],1)
        self.assertTrue(math.isfinite(artist['composite_score']))

    def test_unplayed_tracks_use_neutral_composites_not_an_artificially_bad_percentile(self):
        data=population_data();data['songs'].append(dict(id=100,title='Untested',artist_ids=[1001],tag_ids=[],album_id=None))
        artist=next(r for r in result(data,True)['entities']['artists'] if r['id']==1001)
        unknown=next(r for r in artist['linked_songs'] if r['id']==100)
        self.assertIsNone(unknown['score']);self.assertEqual(unknown['counted_score'],50)
        self.assertAlmostEqual(artist['mean_score'],sum(s['counted_score'] for s in artist['linked_songs'])/2)

    def test_session_contains_only_a_small_calibration_marker(self):
        data=population_data();client=app.test_client()
        with patch.object(overall,'collection',return_value=data):
            response=client.get('/api/overall')
        self.assertEqual(response.status_code,200)
        with client.session_transaction() as session:
            marker=session['overall_calibration']
            self.assertEqual(set(marker),{'id','version','generated_at'})
            self.assertLess(len(json.dumps(marker)),150)
        self.assertLess(len(response.headers.get('Set-Cookie','')),500)


def stat_mean(rows):
    return sum(r['score'] for r in rows)/len(rows)


if __name__=='__main__':unittest.main()
