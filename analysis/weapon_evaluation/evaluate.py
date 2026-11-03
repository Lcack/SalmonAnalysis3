"""Reproducible parameter-based Salmon Run six-axis model, snapshot 1110.

Run from the repository root: python analysis/weapon_evaluation/evaluate.py --write
No match telemetry is fitted. Scenario assumptions are exported, never game facts.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, math, pathlib, statistics, sys
import numpy as np
from extract_common import extract as extract_common

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
DATA = ROOT/'data/weapon_data.json'
PARAM = ROOT/'data/weapon_data_1110'
AXES = ['Killing','Range','Inking','Ink Efficiency','Mob Clearing','Endlag']
CONFIG = dict(version='1110-model-v1', fps=60, cohock_hp=400,
              mob_hp=[40,100], density=.04, group_cap=8,
              paint_overlap=.55, hit_rate=1.0, ordinary_anchor_quantiles=[.05,.95],
              score_min=.5, score_max=5.0, higher_is_better=True,
              confidence='原始显式参数高；离散击杀计算中；涂墨群攻射程机动代理低至中；未做实机校准')


def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))


def merge(base,over):
    result=copy.deepcopy(base)
    for k,v in over.items():
        result[k]=merge(result[k],v) if isinstance(v,dict) and isinstance(result.get(k),dict) else copy.deepcopy(v)
    return result


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def load_source(wid, write_missing=False):
    family,variant,_=wid.split('_'); folder=PARAM/family
    name=f'Weapon{family}{variant}_Coop.game__GameParameterTable.json'
    coop=folder/name; base=folder/name.replace('_Coop','')
    prefix='Bear_' if variant=='Bear' else 'Merge_'
    target=folder/(prefix+name)
    assert coop.exists(),coop
    expected=read(coop) if variant=='Bear' else merge(read(base),read(coop))
    if variant!='Bear':expected.pop('$parent',None)
    if target.exists():
        assert read(target)==expected,f'Merge mismatch: {target}'
    elif write_missing:
        target.write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return expected, target if target.exists() else coop, [p for p in [base,coop] if p.exists()]


def nth_frame(m,n):
    """Time of shot n, n>=1. Startup paid each batch but only once for roll entry."""
    if 'batch_size' in m:
        size=m['batch_size']; batches,slot=divmod(n-1,size)
        return m['startup']+batches*(m.get('batch_charge',m['startup'])+(size-1)*m['interval']+m.get('batch_recovery',m['recovery']))+slot*m['interval']
    if 'burst_size' in m:
        size=m['burst_size'];batches,slot=divmod(n-1,size)
        return m['startup']+batches*((size-1)*m['interval']+m['burst_gap'])+slot*m['interval']
    return m['startup']+(n-1)*m['interval']


def metric(m,cfg):
    # This sweep is arrow convergence, not an artificial damage nerf to shooters.
    hit=cfg['hit_rate'] if m.get('independent_projectiles') else 1.0
    damage=m['damage']*hit
    shots=math.ceil((cfg['cohock_hp']-1e-9)/damage)
    # Killing is a near-target release-time model for all families; flight is
    # retained as metadata, never added to blasters alone.
    flight=0
    def impact(n):
        frame=nth_frame(m,n)
        components=m.get('damage_components',[])
        if components and 'damage_first_frame' in m and all('damage' in c for c in components):
            needed=cfg['cohock_hp']-(shots-1)*damage
            cumulative=0
            for component in sorted(components,key=lambda c:c.get('delay',0)):
                cumulative+=component['damage']*hit
                if cumulative+1e-9>=needed:
                    return frame-m['startup']+m['damage_first_frame']+component.get('delay',0)
        return frame
    cold=(impact(shots)+flight+1)/60
    chain=(impact(8*shots)+flight+m['recovery']+1)/60
    if 'batch_size' in m:
        tank_shots=math.floor((1+1e-10)/(m['ink']*m['batch_size']))*m['batch_size']
    else:
        tank_shots=max(0,math.floor((1-m.get('entry_ink',0)+1e-10)/m['ink']))
    kills=tank_shots//shots
    # Fractional remainder is kept separate; score uses complete kills plus leftover progress.
    tank_eq=kills+(tank_shots%shots)/shots
    action_period=(nth_frame(m,121)-nth_frame(m,1))/120
    period=max(1,action_period)
    paint=m['paint_area']*cfg['paint_overlap']*60/period
    area=math.pi*(m['width']/2)**2
    if m.get('aoe_projectiles'):
        effective_targets=min(cfg['group_cap'],1+cfg['density']*m['aoe_union_area'])
        group_damage=m['aoe_damage']
    elif m.get('independent_projectiles'):
        effective_targets=min(cfg['group_cap'],m.get('projectiles',1),1+cfg['density']*max(area,m['width']*2))
        group_damage=m.get('projectile_damage',damage/max(1,m.get('projectiles',1)))*hit
    elif 'aoe_damage' in m:
        effective_targets=min(cfg['group_cap'],1+cfg['density']*area)
        group_damage=m['aoe_damage']*hit
    elif m['piercing']:
        effective_targets=min(cfg['group_cap'],1+cfg['density']*m['range']*max(1.5,m['width']))
        group_damage=damage
    elif 'aoe_damage' in m or m['width']>1.5:
        effective_targets=min(cfg['group_cap'],1+cfg['density']*area)
        group_damage=m.get('mob_damage',m.get('aoe_damage',damage))*hit
    else:
        effective_targets=1;group_damage=damage
    if m.get('multi_target') and 'aoe_damage' not in m:
        effective_targets=min(effective_targets,m.get('projectiles',cfg['group_cap']))
    mob_times=[]
    for hp in cfg['mob_hp']:
        if m.get('sustained_contact') and group_damage<hp:
            mob_times.append(1e6)
            continue
        nhit=math.ceil((hp-1e-9)/max(group_damage,1e-6))
        mob_times.append(nhit*period/(60*effective_targets))
    mob=1/math.sqrt(math.prod(mob_times))
    # Endlag proxy pays first-action and release delays, with measured move-speed term.
    delay=m['startup']+m['recovery']+6
    mobility=(1+m['move_speed']/.072)/delay
    if m.get('dodge_distance'):
        mobility += .25*m['dodge_distance']/max(1,m['dodge_frames']+m['recovery'])
    return dict(Killing=math.sqrt((1/cold)*(8/chain)),Range=m['range'],Inking=paint,
                **{'Ink Efficiency':tank_eq,'Mob Clearing':mob,'Endlag':mobility},
                cohock_hits=shots,cohock_cold_s=cold,cohock_chain_s=chain/8,
                cohock_kills_per_tank=kills,cohock_equivalent_per_tank=tank_eq,
                tank_shots=tank_shots,paint_proxy_per_s=paint,mob_targets_proxy=effective_targets,
                average_interval_frames=period)


def aggregate(modes,cfg):
    mm=[metric(m,cfg) for m in modes]
    chosen={}
    for axis in AXES:
        candidates=[i for i,m in enumerate(modes) if not (axis in ['Killing','Ink Efficiency'] and m.get('sustained_contact') and m['damage']<cfg['cohock_hp'])]
        assert candidates,('no eligible action',axis)
        chosen[axis]=max(candidates,key=lambda i:mm[i][axis])
    return {a:mm[chosen[a]][a] for a in AXES},chosen,mm


def anchors(rows):
    regular=[r for r in rows if not r['is_bear']]
    out={}
    for a in AXES:
        vals=np.log([r['raw'][a] for r in regular])
        lo,hi=np.quantile(vals,CONFIG['ordinary_anchor_quantiles'])
        out[a]=dict(log_low=float(lo),log_high=float(hi),raw_low=math.exp(lo),raw_high=math.exp(hi))
    return out


def score(raw,anchor):
    return {a:round(float(np.clip(.5+4.5*(math.log(raw[a])-anchor[a]['log_low'])/(anchor[a]['log_high']-anchor[a]['log_low']),.5,5)),1) for a in AXES}


def run(write=False):
    from extract_special import extract as extract_special
    data=read(DATA);rows=[];files={}
    for wid,w in data['weapon'].items():
        if w['type']=='?':continue
        source,path,inputs=load_source(wid,write)
        g=source['GameParameters'];family=wid.split('_')[0]
        modes=(extract_special if family in ['Roller','Brush','Slosher','Shelter','Saber'] else extract_common)(wid,g,str(path.relative_to(ROOT)))
        assert modes,(wid,'no modes')
        for m in modes:
            for k in ['damage','interval','ink','range','width','paint_area']:
                assert math.isfinite(m[k]) and m[k]>0,(wid,m['name'],k,m[k])
            for k in ['startup','recovery','move_speed']:assert m[k]>=0,(wid,k)
        raw,chosen,metrics=aggregate(modes,CONFIG)
        row=dict(id=wid,name=w['name_zh'],family=family,is_bear='_Bear_' in wid,
                 source=str(path.relative_to(ROOT)).replace('\\','/'),source_sha256=sha(path),
                 unresolved_parent=source.get('$parent'),modes=modes,mode_metrics=metrics,selected_modes={a:modes[i]['name'] for a,i in chosen.items()},raw=raw,
                 assumptions=sorted({n for m in modes for n in m.get('assumptions',[])}),
                 notes=sorted({n for m in modes for n in m.get('notes',[])}))
        for p in inputs+[path]:files[str(p.relative_to(ROOT)).replace('\\','/')]=sha(p)
        rows.append(row)
    assert len(rows)==71 and len({r['id'] for r in rows})==71
    anchor=anchors(rows)
    for r in rows:r['scores']=score(r['raw'],anchor)
    # One-factor scenario sweeps. Calibration remains fixed, so bars are comparable.
    sweeps=[]
    for field,values in [('hit_rate',[.7,.85,1.0]),('density',[.02,.04,.08]),('paint_overlap',[.35,.55,.75]),('timing_scale',[.8,1,1.2])]:
        for value in values:
            cfg={**CONFIG,field:value}
            for r in rows:
                modes=r['modes']
                if field=='timing_scale':
                    modes=copy.deepcopy(modes)
                    for m in modes:
                        for key in ['interval','startup','recovery','batch_charge','batch_recovery','burst_gap','damage_first_frame']:
                            if key in m:m[key]*=value
                        for c in m.get('damage_components',[]):
                            if 'delay' in c:c['delay']*=value
                raw,_,_=aggregate(modes,cfg)
                sweeps.append(dict(id=r['id'],factor=field,value=value,scores=score(raw,anchor)))
    for r in rows:
        relevant=[s['scores'] for s in sweeps if s['id']==r['id']]+[r['scores']]
        r['sensitivity_envelope']={a:[min(s[a] for s in relevant),max(s[a] for s in relevant)] for a in AXES}
    result=dict(config=CONFIG,calibration=anchor,weapons=rows,source_manifest=files,
                sensitivity=sweeps,excluded=[k for k,v in data['weapon'].items() if v['type']=='?'])
    (OUT/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (OUT/'model_config.json').write_text(json.dumps(CONFIG,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (OUT/'scores.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['id','name','family']+AXES);writer.writeheader()
        for r in rows:writer.writerow({**{k:r[k] for k in ['id','name','family']},**r['scores']})
    with (OUT/'attack_modes.csv').open('w',newline='',encoding='utf-8-sig') as f:
        cols=['id','weapon','mode','damage','interval','startup','recovery','ink','range','width','paint_area','cohock_hits','cohock_cold_s','cohock_chain_s','cohock_kills_per_tank']
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        for r in rows:
            for m,mm in zip(r['modes'],r['mode_metrics']):
                writer.writerow(dict(id=r['id'],weapon=r['name'],mode=m['name'],**{k:m[k] if k in m else mm[k] for k in cols[3:]}))
    with (OUT/'weapon_profiles.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['id','武器','类型','维度','分数','原始指标','采用动作','起手帧','攻击间隔帧','收招代理帧','大鲑鱼所需动作数','冷启动击杀秒','整箱完整击杀数','敏感性最低分','敏感性最高分','参数文件','假设数量']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:
            for a in AXES:
                i=next(i for i,m in enumerate(r['modes']) if m['name']==r['selected_modes'][a]);m=r['modes'][i];mm=r['mode_metrics'][i]
                writer.writerow(dict(zip(fields,[r['id'],r['name'],r['family'],a,r['scores'][a],r['raw'][a],m['name'],m['startup'],m['interval'],m['recovery'],mm['cohock_hits'],mm['cohock_cold_s'],mm['cohock_kills_per_tank'],*r['sensitivity_envelope'][a],r['source'],len(r['assumptions'])])))
    if write:
        backup=OUT/'weapon_data.before.json'
        if not backup.exists():backup.write_bytes(DATA.read_bytes())
        for r in rows:data['weapon'][r['id']]['rating']['dimensions']=r['scores']
        DATA.write_text(json.dumps(data,ensure_ascii=False,indent=4)+'\n',encoding='utf8')
    print(json.dumps(dict(weapons=len(rows),regular=sum(not r['is_bear'] for r in rows),bear=sum(r['is_bear'] for r in rows),modes=sum(len(r['modes']) for r in rows),excluded=result['excluded'],written=write),ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args();run(args.write)
