"""Screenshot-aligned benchmarks and explicit task-workload interactions.

The workload is a scenario, never a fitted game outcome or recovered video weight.
Unknown wall paint is kept distinguishable from the local-impact proxy.
"""
from __future__ import annotations
import argparse,copy,csv,hashlib,json,math,pathlib,sys,statistics
import numpy as np

HERE=pathlib.Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(BASE))
from evaluate import AXES,read,load_source
from scenarios import boss_benchmark,mob_benchmark,nth_frame
from field_adapters import adapt_modes

OVERALL_CONFIG=read(HERE/'overall_config.json')

PROFILES=[
    dict(id='balanced',name='均衡任务',boss_sets=1,mob_groups=2,ground_area=240,wall_area=48,distance=18),
    dict(id='combat',name='战斗偏重',boss_sets=2,mob_groups=3,ground_area=80,wall_area=16,distance=24),
    dict(id='environment',name='环境维护偏重',boss_sets=1,mob_groups=1,ground_area=480,wall_area=120,distance=12),
]
CONFIG=dict(version='1110-model-v2-reference-definitions',fps=60,cohock_hp=400,mob_hp=[400,400,100,100,100,40,40,40],
            boss_hp=[[300],[500],[600,500],[900],[1200]],density=.04,paint_overlap=.55,hit_rate=1,
            score_min=.5,score_max=5,ordinary_anchor_quantiles=[.05,.95],higher_is_better=True,
            refill_frames=180,approach_speed_units_per_frame=.18,profiles=PROFILES,
            painting_policy='按用户统一熟练度前提 默认涂墙与涂地一致 爆破卡爆点视为已掌握',
            approach_policy='每个战斗块初始距离统一为profile.distance 使用实际选用模式射程 不借全局最远模式',
            blaster_paint_discount=1.0,
            confidence='显式参数与定义高；固定模式资源排程中；涂墙等同涂地、极限射程和工作量情景低；不是原视频排名')
CONFIG['overall_policy']=copy.deepcopy(OVERALL_CONFIG)


def semantic_sha(path):
    """Hash parsed JSON independently of BOM, whitespace and checkout newlines."""
    canonical=json.dumps(read(path),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def verify_source_manifests(legacy):
    """Reject parameter changes, then capture this environment's byte hashes.

    The bootstrap byte manifest remains historical; semantic hashes make a
    clean checkout independent of Git's LF/CRLF conversion policy.
    """
    historical=legacy['source_manifest']
    semantic=legacy.get('source_semantic_manifest')
    if semantic is None or set(semantic)!=set(historical):
        raise ValueError('Bootstrap source_semantic_manifest is missing or has different source paths')
    current={}
    for path,expected in semantic.items():
        source=ROOT/path
        if semantic_sha(source)!=expected:
            raise ValueError(f'Source JSON content differs from the audited bootstrap: {path}')
        current[path]=hashlib.sha256(source.read_bytes()).hexdigest()
    return current,copy.deepcopy(semantic)


def period(m):return max(1.,(nth_frame(m,121)-nth_frame(m,1))/120)


def mode_metrics(m,g):
    p=period(m);ground=m['paint_area']*.55*60/p
    # Explicit user comparison convention: an equally skilled player can use
    # the wall-paint threshold. Keep raw wall diagnostics outside scoring.
    wall_rate=ground;wall_status='equal_ground_wall_user_assumption'
    we=dict(classification='推测假设 用户指定的统一熟练度口径',notes=['默认墙面与地面使用同一覆盖能力，不另因玩家意识或阈值操作差异扣分。'],
            diagnostic_parameter_evidence=m.get('wall_area_evidence',{}))
    if 'batch_size' in m:
        actions=math.floor((1+1e-9)/(m['ink']*m['batch_size']))*m['batch_size']
    else:actions=max(0,math.floor((1-m.get('entry_ink',0)+1e-9)/m['ink']))
    damage_tank=actions*m['damage'] if not m.get('rolling') else None
    return dict(ground_rate=ground,wall_rate=wall_rate,wall_status=wall_status,wall_evidence=we,
                ground_area_per_action=m['paint_area']*.55,wall_area_per_action=m['paint_area']*.55,
                ink_rate_per_s=m['ink']*60/p,tank_actions=actions,max_damage_per_tank=damage_tank,
                release_to_swim_frames=m.get('release_to_swim_frames'),range_extreme_proxy=m.get('range_extreme_proxy'),
                average_interval_frames=p)


def calibrate(rows,field='raw'):
    regular=[r for r in rows if not r['is_bear']];out={}
    for a in AXES:
        vals=np.log([r[field][a] for r in regular]);lo,hi=np.quantile(vals,[.05,.95])
        out[a]=dict(log_low=float(lo),log_high=float(hi),raw_low=math.exp(lo),raw_high=math.exp(hi))
    return out


def scores(raw,cal):
    return {a:round(float(np.clip(.5+4.5*(math.log(raw[a])-cal[a]['log_low'])/(cal[a]['log_high']-cal[a]['log_low']),.5,5)),1) for a in AXES}


def aggregate(modes,metrics,boss,mob):
    ids={a:None for a in AXES}
    ids['Range']=max([i for i,m in enumerate(modes) if m.get('range_grounded_eligible') and m.get('range_extreme_proxy')],key=lambda i:modes[i]['range_extreme_proxy'])
    gi=max(range(len(modes)),key=lambda i:metrics[i]['ground_rate'])
    wi=max(range(len(modes)),key=lambda i:metrics[i]['wall_rate'])
    ii=max([i for i in range(len(modes)) if metrics[i]['max_damage_per_tank'] is not None],key=lambda i:metrics[i]['max_damage_per_tank'])
    end_candidates=[i for i,m in enumerate(modes) if m.get('release_to_swim_frames') is not None and not m.get('rolling')]
    if end_candidates:
        ei=min(end_candidates,key=lambda i:modes[i]['release_to_swim_frames']);end=modes[ei]['release_to_swim_frames'];estatus=modes[ei]['release_to_swim_evidence']['classification']
    else:
        ei=min([i for i,m in enumerate(modes) if not m.get('rolling')],key=lambda i:modes[i]['recovery'])
        end=max(1,modes[ei]['recovery']);estatus='缺少直接潜墨实测 仅保留参数收招代理 不等于已核实硬直'
    ids['Inking']=gi;ids['Ink Efficiency']=ii;ids['Endlag']=ei
    ids['Mob Clearing']=mob['plans'][0]['mode_index']
    raw=dict(Killing=1/boss['frames'],Range=modes[ids['Range']]['range_extreme_proxy'],
             Inking=math.sqrt(metrics[gi]['ground_rate']*max(metrics[wi]['wall_rate'],1e-9)),
             **{'Ink Efficiency':metrics[ii]['max_damage_per_tank'],'Mob Clearing':1/mob['frames'],'Endlag':1/max(1,end)})
    selected={a:(modes[i]['name'] if i is not None else '五种血量逐项选优') for a,i in ids.items()}
    selected['Inking']=f"地面 {modes[gi]['name']} / 墙面 {modes[wi]['name']}"
    feat=dict(ground_rate=metrics[gi]['ground_rate'],wall_rate=metrics[wi]['wall_rate'],ground_mode=gi,wall_mode=wi,
              ground_ink_rate=metrics[gi]['ink_rate_per_s'],wall_ink_rate=metrics[wi]['ink_rate_per_s'],
              wall_status=metrics[wi]['wall_status'],release_to_swim_frames=end,endlag_status=estatus,
              endlag_source=modes[ei].get('release_to_swim_evidence'),range_extreme=raw['Range'],
              ink_damage_tank=raw['Ink Efficiency'],endlag_mode=ei,range_mode=ids['Range'])
    return raw,selected,feat


def workload(row,profile,refill=180,wall_factor=1.,floor_factor=1.,distance_factor=1.):
    from workload_sequence import run_workload
    from scenarios import paint_task
    f=row['features'];b=row['benchmarks']['boss'];mob=row['benchmarks']['mob'];blocks=[]
    for _ in range(profile['boss_sets']):
        for case in b['cases']:
            blocks.append(dict(kind='target',label=case['name'],mode=row['modes'][case['mode_index']],phases=case['phases']))
    for _ in range(profile['mob_groups']):
        blocks.append(dict(kind='mob',label='混合杂鱼',mode=row['modes'][mob['plans'][0]['mode_index']],density=CONFIG['density']))
    for kind,amount,factor in [('ground',profile['ground_area'],floor_factor),('wall',profile['wall_area'],wall_factor)]:
        options=[]
        for md,mm in zip(row['modes'],row['mode_metrics']):
            area=mm[kind+'_area_per_action']*factor
            pp=paint_task(md,amount,area,refill_frames=refill)
            if pp['feasible']:options.append((pp['frames'],pp['ink_spent'],md,area))
        _,_,md,area=min(options,key=lambda t:t[:2])
        blocks.append(dict(kind='paint',label=kind,component=kind,mode=md,area=amount,area_per_action=area))
    result=run_workload(blocks,refill_frames=refill)
    assert result['feasible']
    approach=sum(max(0.,profile['distance']*distance_factor-(b['mode'].get('range_extreme_proxy') or b['mode']['range']))/CONFIG['approach_speed_units_per_frame'] for b in blocks if b['kind'] in ['target','mob'])
    parts={k:result['components_frames'].get(k,0.) for k in ['boss','mob','ground','wall','extra_refill','release']}
    parts['approach']=approach
    return dict(id=profile['id'],name=profile['name'],frames=sum(parts.values()),seconds=sum(parts.values())/60,
                ink_tanks=result['ink_spent'],extra_refills=result['refill_count'],components_frames=parts,
                task_plan=result['taskplans'],resource_assumptions=result['resource_assumptions'])


def overall_raw_score(frames,calibration):
    """Unrounded 1–5 task score under the ordinary-weapon time anchors."""
    if not math.isfinite(frames) or frames<=0:
        raise ValueError('Task frames must be positive and finite')
    low=OVERALL_CONFIG['score_min'];high=OVERALL_CONFIG['score_max']
    return float(np.clip(low+(high-low)*(math.log(1/frames)-calibration['log_low'])/
                         (calibration['log_high']-calibration['log_low']),low,high))


def tier_for_score(score):
    """Classify the final one-decimal display value, including rounding to 5."""
    if not math.isfinite(score) or not 1<=score<=5:
        raise ValueError('Overall score must be finite and within 1–5')
    displayed=round(float(score),1)
    for band in OVERALL_CONFIG['tier_anchors']:
        if 'equals' in band and displayed==band['equals']:
            return band['tier']
        if 'min_inclusive' in band and band['min_inclusive']<=displayed<band['max_exclusive']:
            return band['tier']
    raise ValueError(f'No overall tier for {displayed}')


def _overall_map(vals,regular_mask):
    lo,hi=np.quantile(np.log([1/v for v,is_regular in zip(vals,regular_mask) if is_regular]),OVERALL_CONFIG['ordinary_anchor_quantiles'])
    calibration=dict(log_low=float(lo),log_high=float(hi),
                     time_slow_anchor=math.exp(-float(lo)),time_fast_anchor=math.exp(-float(hi)),
                     scale=[OVERALL_CONFIG['score_min'],OVERALL_CONFIG['score_max']],
                     population=sum(regular_mask),overall_version=OVERALL_CONFIG['version'])
    return [overall_raw_score(v,calibration) for v in vals],calibration


def run(write=False):
    legacy=read(BASE/'evaluation.json')
    source_manifest,source_semantic_manifest=verify_source_manifests(legacy)
    before=read(HERE/OVERALL_CONFIG['historical_manual_baseline'])
    publication_before=read(HERE/OVERALL_CONFIG['publication_baseline']);rows=[]
    for old in legacy['weapons']:
        src,_,_=load_source(old['id']);g=src['GameParameters'];modes=adapt_modes(old['id'],g,old['modes'])
        mm=[mode_metrics(m,g) for m in modes]
        boss=boss_benchmark(modes);mob=mob_benchmark(modes,density=CONFIG['density'])
        assert boss['feasible'] and mob['feasible'],old['id']
        raw,selected,feat=aggregate(modes,mm,boss,mob)
        row={k:copy.deepcopy(old[k]) for k in ['id','name','family','is_bear','source','source_sha256','assumptions','notes']}
        row['source_sha256']=source_manifest[row['source']]
        row['source_semantic_sha256']=source_semantic_manifest[row['source']]
        row.update(modes=modes,mode_metrics=mm,benchmarks=dict(boss=boss,mob=mob),raw=raw,selected_modes=selected,features=feat,
                   previous_scores=old['scores'],original_overall=before['weapon'][old['id']]['rating']['overall'],
                   original_tier=before['weapon'][old['id']]['rating']['tier'])
        rows.append(row)
    cal=calibrate(rows)
    for r in rows:
        r['scores']=scores(r['raw'],cal)
        assert r['scores']==publication_before['weapon'][r['id']]['rating']['dimensions'],('frozen_dimensions_changed',r['id'])
    regular=[not r['is_bear'] for r in rows]
    assert sum(regular)==63
    for r in rows:r['overall']=dict(original=r['original_overall'],equal_axis_baseline=round(statistics.mean(r['scores'].values()),1),scenarios=[workload(r,p) for p in PROFILES])
    overall_cal={}
    for i,p in enumerate(PROFILES):
        vals=[r['overall']['scenarios'][i]['frames'] for r in rows];ss,ac=_overall_map(vals,regular);overall_cal[p['id']]=ac
        for r,s in zip(rows,ss):
            r['overall']['scenarios'][i].update(raw_score=s,score=round(s,1))
    for r in rows:
        ss=[x['raw_score'] for x in r['overall']['scenarios']]
        mean=statistics.mean(ss);display=round(mean,1)
        r['overall'].update(raw_mean=mean,recommended=display,model_tier=tier_for_score(display),
                            original_tier=r['original_tier'],range=[round(min(ss),1),round(max(ss),1)],
                            overall_version=OVERALL_CONFIG['version'],
                            policy='三类1–5未取整任务分数等权平均后保留一位小数；普通武器采用，熊武器仅列候选')
    for i,p in enumerate(PROFILES):
        ranked=sorted(rows,key=lambda r:r['overall']['scenarios'][i]['frames'])
        for rank,r in enumerate(ranked,1):r['overall']['scenarios'][i]['rank']=rank
    for r in rows:
        rr=[s['rank'] for s in r['overall']['scenarios']];r['overall']['rank_range']=[min(rr),max(rr)]
    sensitivity=[]
    for r in rows:
        for factor,values in [('wall_factor',[.6,.8,1]),('refill_frames',[120,180,240]),('layout',['dispersed','grid','clustered']),('hit_rate',[.7,.85,1])]:
            for value in values:
                raw=copy.deepcopy(r['raw'])
                if factor=='wall_factor' and r['family']=='Blaster':raw['Inking']*=value
                elif factor=='layout':raw['Mob Clearing']=1/r['benchmarks']['mob']['layouts'][value]['frames']
                elif factor=='hit_rate' and r['family']=='Stringer':
                    modes=copy.deepcopy(r['modes'])
                    for m in modes:
                        if m.get('independent_projectiles'):
                            m['damage']*=value;m['projectile_damage']*=value
                    raw['Killing']=1/boss_benchmark(modes)['frames']
                elif factor=='refill_frames':raw['Killing']=1/boss_benchmark(r['modes'],refill_frames=value)['frames']
                sensitivity.append(dict(id=r['id'],factor=factor,value=value,scores=scores(raw,cal)))
        ss=[s['scores'] for s in sensitivity if s['id']==r['id']]
        r['sensitivity_envelope']={a:[min(s[a] for s in ss),max(s[a] for s in ss)] for a in AXES}
        variations=[]
        for wf in ([.6,.8,1] if r['family']=='Blaster' else [1]):
            for refill in [120,180,240]:
                for p in PROFILES:
                    w=workload(r,p,wall_factor=wf,refill=refill);ac=overall_cal[p['id']]
                    variations.append(overall_raw_score(w['frames'],ac))
        r['overall']['sensitivity_range']=[round(min(variations),1),round(max(variations),1)]
    current=read(ROOT/'data/weapon_data.json')
    for r in rows:
        wid=r['id'];rating=current['weapon'][wid]['rating'];previous=publication_before['weapon'][wid]['rating']
        if write and not r['is_bear']:
            # Bear and random objects are never assigned, restored, or rebuilt.
            rating['overall']=r['overall']['recommended'];rating['tier']=r['overall']['model_tier']
        published=(rating['overall'],rating['tier'])
        candidate=(r['overall']['recommended'],r['overall']['model_tier'])
        r['overall'].update(previous_published=previous['overall'],previous_published_tier=previous['tier'],
                            published=published[0],published_tier=published[1],
                            ordinary_eligible=not r['is_bear'],
                            applied_to_product=not r['is_bear'] and published==candidate,
                            changed_from_publication_baseline=published!=(previous['overall'],previous['tier']))
    overall_summary=dict(ordinary_eligible=63,
                         ordinary_applied=sum(not r['is_bear'] and r['overall']['applied_to_product'] for r in rows),
                         ordinary_changed=sum(not r['is_bear'] and r['overall']['changed_from_publication_baseline'] for r in rows),
                         ordinary_score_changed=sum(not r['is_bear'] and r['overall']['published']!=r['overall']['previous_published'] for r in rows),
                         ordinary_tier_changed=sum(not r['is_bear'] and r['overall']['published_tier']!=r['overall']['previous_published_tier'] for r in rows),
                         bear_preserved=8,random_preserved=len(legacy['excluded']),dimensions_unchanged=426)
    changes={a:sum(r['scores'][a]!=r['previous_scores'][a] for r in rows) for a in AXES}
    result=dict(config=CONFIG,calibration=cal,overall_calibration=overall_cal,weapons=rows,sensitivity=sensitivity,
                source_manifest=source_manifest,source_semantic_manifest=source_semantic_manifest,
                excluded=legacy['excluded'],changes=changes,
                overall_policy=copy.deepcopy(OVERALL_CONFIG),overall_write_summary=overall_summary,
                overall_written=bool(write),reference_definition_image='figures/reference_definition.png')
    (HERE/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (HERE/'model_config.json').write_text(json.dumps(CONFIG,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (HERE/'scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','name','family']+AXES);w.writeheader()
        for r in rows:w.writerow({**{k:r[k] for k in ['id','name','family']},**r['scores']})
    with (HERE/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','武器','旧击杀分','新击杀分','五种血量总帧','清杂帧','整箱最大伤害','射出到潜墨帧','原总分','等权六维基线','任务模型建议总分','场景最低分','场景最高分','跨场景最优名次','跨场景最差名次','墙涂证据状态','硬直证据状态','原档位','已发布总分','已发布档位','模型候选档位','普通武器已采用','相对发布前有改动']
        w=csv.writer(f);w.writerow(fields)
        for r in rows:w.writerow([r['id'],r['name'],r['previous_scores']['Killing'],r['scores']['Killing'],r['benchmarks']['boss']['frames'],r['benchmarks']['mob']['frames'],r['features']['ink_damage_tank'],r['features']['release_to_swim_frames'],r['overall']['original'],r['overall']['equal_axis_baseline'],r['overall']['recommended'],*r['overall']['range'],*r['overall']['rank_range'],r['features']['wall_status'],r['features']['endlag_status'],r['overall']['original_tier'],r['overall']['published'],r['overall']['published_tier'],r['overall']['model_tier'],r['overall']['applied_to_product'],r['overall']['changed_from_publication_baseline']])
    with (HERE/'overall_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','武器','family','is_bear','原总分','原档位','发布前总分','发布前档位','模型未取整均值','模型候选总分','模型候选档位','已发布总分','已发布档位','普通武器已采用','总分或档位有改动']
        fields += [p['id']+suffix for p in PROFILES for suffix in ['_耗时帧','_未取整分','_展示分']]
        w=csv.writer(f);w.writerow(fields)
        for r in rows:
            o=r['overall'];values=[r['id'],r['name'],r['family'],r['is_bear'],o['original'],o['original_tier'],o['previous_published'],o['previous_published_tier'],o['raw_mean'],o['recommended'],o['model_tier'],o['published'],o['published_tier'],o['applied_to_product'],o['changed_from_publication_baseline']]
            values += [v for scenario in o['scenarios'] for v in [scenario['frames'],scenario['raw_score'],scenario['score']]]
            w.writerow(values)
    with (HERE/'benchmarks.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['id','武器','300血帧','500血帧','600盾加500本体帧','900血帧','1200血帧','五项总帧','杂鱼规则队形帧','杂鱼分散帧','杂鱼聚集帧','整箱最大伤害','射出到潜墨帧','涂地墙同效代理每秒','极限距离代理'])
        for r in rows:w.writerow([r['id'],r['name'],*[c['frames'] for c in r['benchmarks']['boss']['cases']],r['benchmarks']['boss']['frames'],*[r['benchmarks']['mob']['layouts'][l]['frames'] for l in ['grid','dispersed','clustered']],r['features']['ink_damage_tank'],r['features']['release_to_swim_frames'],r['features']['ground_rate'],r['features']['range_extreme']])
    if write:
        (ROOT/'data/weapon_data.json').write_text(json.dumps(current,ensure_ascii=False,indent=4)+'\n',encoding='utf8')
    print(json.dumps(dict(weapons=len(rows),changes=changes,overall_written=bool(write),overall_summary=overall_summary,written=write),ensure_ascii=False))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description='复算六维和1–5任务总分；熊武器与随机图标不改写。')
    p.add_argument('--write',action='store_true',help='写入63把普通武器的overall/tier，并保留冻结六维；8把熊武器和2个随机图标完整保留当次current对象')
    run(p.parse_args().write)
