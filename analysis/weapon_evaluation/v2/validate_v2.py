import json,math,pathlib,hashlib,statistics
from evaluate_v2 import HERE,ROOT,AXES,read,scores,semantic_sha,tier_for_score,overall_raw_score,OVERALL_CONFIG
from scenarios import sequence_time,paint_task
from workload_sequence import run_workload

def check():
    x=read(HERE/'evaluation.json');current=read(ROOT/'data/weapon_data.json');before=read(HERE/OVERALL_CONFIG['publication_baseline'])
    manual=read(HERE/OVERALL_CONFIG['historical_manual_baseline'])
    assert len(x['weapons'])==71
    assert set(current['weapon'])==set(before['weapon'])
    ordinary_count=0;bear_count=0
    for r in x['weapons']:
        assert r['scores']==scores(r['raw'],x['calibration'])
        assert r['scores']==current['weapon'][r['id']]['rating']['dimensions']
        assert r['scores']==before['weapon'][r['id']]['rating']['dimensions']
        a=json.loads(json.dumps(current['weapon'][r['id']]))
        b=json.loads(json.dumps(before['weapon'][r['id']]))
        o=r['overall'];rating=current['weapon'][r['id']]['rating']
        assert o['original']==manual['weapon'][r['id']]['rating']['overall']
        assert o['original_tier']==manual['weapon'][r['id']]['rating']['tier']
        for scenario in o['scenarios']:
            raw=overall_raw_score(scenario['frames'],x['overall_calibration'][scenario['id']])
            assert scenario['raw_score']==raw and scenario['score']==round(raw,1)
            assert 1<=raw<=5
        raw_mean=statistics.mean(s['raw_score'] for s in o['scenarios'])
        assert o['raw_mean']==raw_mean and o['recommended']==round(raw_mean,1)
        assert o['model_tier']==tier_for_score(o['recommended'])
        assert o['published']==rating['overall'] and o['published_tier']==rating['tier']
        if r['is_bear']:
            bear_count+=1
            assert a==b,('bear_object_changed',r['id'])
            assert not o['applied_to_product']
        else:
            ordinary_count+=1
            assert rating['overall']==o['recommended'] and rating['tier']==o['model_tier']
            assert o['applied_to_product']
            b['rating']['overall']=o['recommended'];b['rating']['tier']=o['model_tier']
            assert a==b,('ordinary_outside_overall_tier_changed',r['id'])
        assert r['benchmarks']['boss']['frames']==sum(c['frames'] for c in r['benchmarks']['boss']['cases'])
        assert len(r['benchmarks']['boss']['cases'])==5
        assert r['benchmarks']['boss']['cases'][2]['phases']==[600,500]
        assert r['benchmarks']['mob']['layouts']['grid']['plan']['initial_hp']==[400,400,100,100,100,40,40,40]
        assert all(.5<=s<=5 and math.isfinite(s) for s in r['scores'].values())
        assert r['features']['ground_rate']==r['features']['wall_rate']
        eff=next(m for m in r['modes'] if m['name']==r['selected_modes']['Ink Efficiency']);assert not eff.get('rolling')
        for scenario in r['overall']['scenarios']:
            assert abs(sum(scenario['components_frames'].values())-scenario['frames'])<1e-6
            plans=scenario['task_plan']
            assert abs(plans[0]['initial_ink']-1)<1e-9
            for previous,nxt in zip(plans,plans[1:]):assert abs(previous['remaining_ink']-nxt['initial_ink'])<1e-8
            for plan in plans:
                assert plan['frames']>=1
                assert 0<=plan['remaining_ink']<=1
    for wid in x['excluded']:assert current['weapon'][wid]==before['weapon'][wid]
    assert ordinary_count==63 and bear_count==8 and len(x['excluded'])==2
    assert x['overall_policy']==OVERALL_CONFIG
    assert all(c['population']==63 and c['scale']==[1.0,5.0] and c['overall_version']==OVERALL_CONFIG['version'] for c in x['overall_calibration'].values())
    for path,digest in x['source_manifest'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    if 'source_semantic_manifest' in x:
        assert set(x['source_semantic_manifest'])==set(x['source_manifest'])
        for path,digest in x['source_semantic_manifest'].items():assert semantic_sha(ROOT/path)==digest,('source_semantic_hash',path)
    # A .35 charge is indivisible: five one-shot batches require two refills.
    m=dict(name='whole_batch_fixture',damage=100,interval=1,startup=10,recovery=2,
           ink=.35,batch_size=1,batch_charge=10,batch_recovery=2,release_to_swim_frames=2)
    p=run_workload([dict(kind='target',mode=m,phases=[100],label=str(i)) for i in range(5)])
    assert p['refill_count']==2
    assert sequence_time([dict(name='phase_fixture',damage=700,interval=10,startup=2,recovery=2,ink=.1)], [600,500])['actions']==2
    hydra=next(r for r in x['weapons'] if r['id']=='Spinner_Hyper_Coop');mode=next(m for m in hydra['modes'] if m['name']=='满蓄力')
    p=paint_task(mode,1,10);assert p['frames']>=mode['startup'] and p['ink_spent']>=.35-1e-9
    # Tier classification follows the final display score, with no ambiguous
    # shared endpoints between neighboring ranges.
    boundaries={1.0:'C',1.9:'C',2.0:'B',2.9:'B',3.0:'A',3.9:'A',4.0:'S',4.9:'S',5.0:'S+'}
    assert all(tier_for_score(value)==tier for value,tier in boundaries.items())
    assert round(4.96,1)==5.0 and tier_for_score(4.96)=='S+'
    raw_example=[4.94,4.94,4.99]
    assert round(statistics.mean(raw_example),1)==5.0
    assert round(statistics.mean(round(v,1) for v in raw_example),1)==4.9
    anchor=dict(log_low=math.log(1/100),log_high=math.log(1/10))
    assert overall_raw_score(100,anchor)==1 and overall_raw_score(10,anchor)==5
    assert abs(overall_raw_score(math.sqrt(1000),anchor)-3)<1e-12
    return dict(status='passed',weapons=71,dimensions=426,changes=x['changes'],source_hashes=len(x['source_manifest']),
                ordinary_overall_tier_applied=63,bear_objects_preserved=8,random_objects_preserved=2,
                dimensions_unchanged=426,overall_version=OVERALL_CONFIG['version'],
                overall_write_summary=x['overall_write_summary'],
                checks=['five_hp_sum','two_phase_no_overkill_carry','fixed_2_3_3_group','exclude_crush_ink_efficiency','same_skill_wall_equals_floor','source_hashes','shared_ink_carry','atomic_charge_refills','mode_specific_exits','cold_start_paint','product_write_scope','ordinary_only_overall_tier','bear_random_full_object_preservation','frozen_426_dimensions','unrounded_scenario_mean','one_to_five_scale','tier_boundaries_after_rounding'])

if __name__=='__main__':
    result=check();(HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
