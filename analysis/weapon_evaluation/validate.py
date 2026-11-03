"""Meaningful invariants for the six-axis evaluator and product writeback."""
import hashlib, json, math, pathlib
from evaluate import ROOT,OUT,AXES,read,metric,nth_frame,CONFIG,load_source

def check():
    result=read(OUT/'evaluation.json'); current=read(ROOT/'data/weapon_data.json');before=read(OUT/'weapon_data.before.json')
    assert set(current)==set(before)
    assert len(result['weapons'])==71
    assert sum(r['is_bear'] for r in result['weapons'])==8
    assert set(current['weapon'])==set(before['weapon'])
    changed=[]
    for wid,w in current['weapon'].items():
        old=before['weapon'][wid]
        new_without=json.loads(json.dumps(w));old_without=json.loads(json.dumps(old))
        new_without['rating'].pop('dimensions',None);old_without['rating'].pop('dimensions',None)
        assert new_without==old_without,('unrequested change',wid)
        if w['type']=='?':assert w==old;continue
        assert list(w['rating']['dimensions'])==AXES
        assert all(isinstance(v,(int,float)) and .5<=v<=5 and abs(v*10-round(v*10))<1e-8 for v in w['rating']['dimensions'].values())
        r=next(r for r in result['weapons'] if r['id']==wid)
        assert r['scores']==w['rating']['dimensions']
        load_source(wid)
        if w!=old:changed.append(wid)
        for axis in ['Killing','Ink Efficiency']:
            selected=next(m for m in r['modes'] if m['name']==r['selected_modes'][axis])
            assert not (selected.get('sustained_contact') and selected['damage']<400)
        for m,mm in zip(r['modes'],r['mode_metrics']):
            assert mm['cohock_cold_s']>0 and mm['cohock_chain_s']>0
            if m.get('batch_size'):
                assert mm['tank_shots']%m['batch_size']==0
            if m.get('aoe_projectiles'):
                single=math.pi*m['aoe_radius']**2
                assert single<=m['aoe_union_area']<=single*m['aoe_projectiles']+1e-8
                assert abs(metric(m,{**CONFIG,'density':0})['mob_targets_proxy']-1)<1e-8
    assert len(changed)==71
    byid={r['id']:r for r in result['weapons']}
    splat=byid['Shooter_Normal_Coop'];m=splat['modes'][0];mm=splat['mode_metrics'][0]
    assert (m['damage'],m['interval'],mm['cohock_hits'],mm['tank_shots'])==(36,6,12,108)
    pencil=next(m for m in byid['Charger_Pencil_Coop']['modes'] if 'batch_size' in m)
    assert nth_frame(pencil,6)-nth_frame(pencil,1)==157
    assert metric(pencil,CONFIG)['tank_shots']==15
    bear=byid['Charger_Bear_Coop'];assert len(bear['modes'])==1 and bear['modes'][0]['interval']==4
    assert all(m.get('melee') for m in byid['Saber_Bear_Coop']['modes'])
    ordinary_brella=byid['Shelter_Normal_Coop']['modes'][0]
    assert ordinary_brella['damage']<=ordinary_brella['damage_cap']
    explosive=byid['Slosher_Washtub_Coop']
    assert max(mm['mob_targets_proxy'] for mm in explosive['mode_metrics'])>1
    assert any(m['interval']==3 for m in byid['Spinner_HyperShort_Coop']['modes'])
    for rel,expected in result['source_manifest'].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected,rel
    return dict(status='passed',evaluated_weapons=71,dimensions_written=426,
                random_icons_unchanged=2,source_files_verified=len(result['source_manifest']),
                attacks=sum(len(r['modes']) for r in result['weapons']),
                preserved_fields='All fields outside rating.dimensions, including overall and tier',
                checks=['merge equality','source SHA256','writeback scope','finite scores','one-decimal scores','batch ammunition','roll knockback eligibility','arrow blast union','S-BLAST modes','splat 400HP arithmetic','pencil cadence','bear charger','bear melee only','brella damage cap','Explosher AOE'])

if __name__=='__main__':
    result=check();(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
