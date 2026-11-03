import json,math,pathlib,hashlib
from evaluate_v2 import HERE,ROOT,AXES,read,scores,semantic_sha
from scenarios import sequence_time,paint_task
from workload_sequence import run_workload

def check():
    x=read(HERE/'evaluation.json');current=read(ROOT/'data/weapon_data.json');before=read(HERE/'weapon_data.before_v2.json')
    assert len(x['weapons'])==71
    for r in x['weapons']:
        assert r['scores']==scores(r['raw'],x['calibration'])
        assert r['scores']==current['weapon'][r['id']]['rating']['dimensions']
        a=json.loads(json.dumps(current['weapon'][r['id']]))
        b=json.loads(json.dumps(before['weapon'][r['id']]))
        a['rating'].pop('dimensions');b['rating'].pop('dimensions');assert a==b
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
    return dict(status='passed',weapons=71,dimensions=426,changes=x['changes'],source_hashes=len(x['source_manifest']),
                overall_and_tier_preserved=True,checks=['five_hp_sum','two_phase_no_overkill_carry','fixed_2_3_3_group','exclude_crush_ink_efficiency','same_skill_wall_equals_floor','source_hashes','shared_ink_carry','atomic_charge_refills','mode_specific_exits','cold_start_paint','product_write_scope'])

if __name__=='__main__':
    result=check();(HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
