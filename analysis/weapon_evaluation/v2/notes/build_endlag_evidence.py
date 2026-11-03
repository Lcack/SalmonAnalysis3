"""Export supplemental release/cancel-to-swim evidence without inventing omissions."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
E = json.loads((BASE / 'evaluation.json').read_text(encoding='utf8'))
SOURCE = 'https://wikiwiki.jp/splatoon3mix/検証/メインウェポン/前隙・後隙'
raw = {
    'Shooter_Blaze': 2, 'Shooter_Expert': 4, 'Shooter_First': 2,
    'Shooter_Flash': 6, 'Shooter_Gravity': 3, 'Shooter_Heavy': 4,
    'Shooter_Long': 4, 'Shooter_Normal': 4, 'Shooter_Precision': 3,
    'Shooter_QuickLong': 3, 'Shooter_QuickMiddle': 3, 'Shooter_Short': 2,
    'Shooter_TripleMiddle': 22, 'Shooter_TripleQuick': 10,
    'Blaster_LightLong': 20, 'Blaster_LightShort': 20, 'Blaster_Light': 20,
    'Blaster_Long': 30, 'Blaster_Middle': 23, 'Blaster_Precision': 26,
    'Blaster_Short': 26,
    'Brush_Heavy': 21, 'Brush_Mini': 14, 'Brush_Normal': 18,
    'Roller_Compact': 13, 'Roller_Heavy': 15, 'Roller_Hunter': 15,
    'Roller_Normal': 15, 'Roller_Wide': 13,
    'Slosher_Bathtub': 25, 'Slosher_Diffusion': 20, 'Slosher_Double': 16,
    'Slosher_Launcher': 20, 'Slosher_Strong': 16, 'Slosher_Washtub': 35,
    'Shelter_Compact': 20, 'Shelter_Focus': 25,
    'Shelter_Normal': 20, 'Shelter_Wide': 40,
}
for w in E['weapons']:
    if w['family'] == 'Charger': raw[w['id'].removesuffix('_Coop')] = 16
    if w['family'] == 'Maneuver' and not w['is_bear']:
        raw[w['id'].removesuffix('_Coop')] = 6
    if w['family'] == 'Stringer' and not w['is_bear']:
        raw[w['id'].removesuffix('_Coop')] = 11
    if w['family'] == 'Spinner':
        raw[w['id'].removesuffix('_Coop')] = 7

records = {}
for w in E['weapons']:
    key = w['id'].removesuffix('_Coop')
    family = w['family']
    value = raw.get(key)
    d = dict(release_to_swim_frames=value,
             origin=('cancel_input' if family in ('Shooter','Maneuver') and 'Triple' not in key and key != 'Shooter_Flash' else 'projectile_release'),
             measurement_status='measured_in_source_v10.0.1' if value is not None else 'missing_in_measurement_source',
             source_url=SOURCE if value is not None else None,
             local_source=w['source'], modes={}, notes=[])
    if family in ('Shooter','Maneuver') and d['origin']=='cancel_input':
        d['notes'].append('最小值成立于与最后一发同帧取消；取消相位可增加0至RepeatFrame减1帧，不能声称任意取消时刻都固定为该值。')
    if family=='Shooter' and 'Triple' in key:
        d['origin']='third_bullet_release'
        d['notes'].append('三连发以第3颗子弹为零时刻；第1颗到潜墨还须加两次RepeatFrame。')
    if key=='Shooter_Flash':
        d['modes']['tap']={'release_to_swim_frames':6,'origin':'projectile_release'}
        d['modes']['hold']={'release_to_swim_frames':3,'origin':'cancel_input'}
    if family=='Roller' and not w['is_bear']:
        d['modes']['horizontal']={'release_to_swim_frames':value,'origin':'flick_projectile_release'}
        d['modes']['vertical']={'release_to_swim_frames':19,'origin':'flick_projectile_release','grounded_range_eligible':False}
        d['modes']['rolling']={'release_to_swim_frames':None,'cancel_to_swim_frames':6,'origin':'roll_cancel_input'}
    if family=='Brush':
        d['modes']['rolling']={'release_to_swim_frames':None,'cancel_to_swim_frames':6,'origin':'brush_roll_cancel_input'}
    if family=='Slosher' and key in ('Slosher_Bathtub','Slosher_Double'):
        delay=15 if key=='Slosher_Bathtub' else 8
        d['origin']='first_projectile_release'
        d['modes']['last_projectile']={'release_to_swim_frames':value-delay,'origin':'last_projectile_release','classification':'calculated_from_measurement_and_local_emission_offsets','local_last_minus_first_frames':delay}
    if family=='Blaster':
        gp=json.loads((BASE.parents[1]/w['source']).read_text(encoding='utf8'))['GameParameters']
        actual=gp['WeaponParam'].get('PostDelayFrame_Blaster')
        d['local_PostDelayFrame_Blaster']=actual
        if value is not None and value!=actual:
            d['notes'].append('公开旧版实测与本地PostDelayFrame_Blaster不一致；原测量保留，不直接覆盖1110。')
            d['measurement_status']='version_or_definition_conflict'
    if family=='Maneuver':
        d['notes'].append('翻滚锁定与射击取消计时并行。数值6仅为普通射击取消基线；翻滚期间发出子弹时仍须等待剩余UnrelaxFrameNoSquid，不可直接给所有翻滚后射击6。')
    if family=='Spinner':
        d['origin']='first_projectile_release'
        d['modes']['sustained_cancel']={'release_to_swim_frames':None,'cancel_to_swim_frames':6,'origin':'cancel_input'}
        d['notes'].append('源表末尾旋转枪章节给出首发至潜墨7F、持续射击取消输入至潜墨6F。作者称两种门限不并行，6至7F阈值机制还需检验；不把取消输入6直接冒充固定末弹6。')
    if family=='Saber' and not w['is_bear']:
        # Source timing starts at the first attack event (melee); the ink wave
        # starts three frames later in both the source table and local fields.
        vals={'Saber_Normal':(23,22,15,26),'Saber_Lite':(16,15,23,26),'Saber_Heavy':(28,None,31,50)}[key]
        names=['horizontal_first','horizontal_repeat','charged_stationary','charged_lunge']
        d['modes']={name:{'first_attack_to_swim_frames':v,
                          'release_to_swim_frames':v-3 if v is not None else None,
                          'first_to_projectile_frames':3,
                          'origin':'ink_wave_release',
                          'classification':'calculated_from_measured_first_attack_timing'}
                    for name,v in zip(names,vals)}
        d['release_to_swim_frames']=d['modes']['horizontal_first']['release_to_swim_frames']
        d['origin']='ink_wave_release'
        d['measurement_status']='measured_first_attack_plus_explicit_event_offset'
        d['source_url']=SOURCE
        d['notes'].append('表后摇从刀身首次攻击事件计；严格子弹口径扣除剑气晚3帧的偏移。不得把近战与剑气事件混成同一零时刻。')
    if key=='Saber_Bear':
        d['notes'].append('熊刀没有剑气子弹，且源表熊刀测量为空。严格子弹射出定义下不适用，不用普通刀或任意固定值补齐。')
    records[w['id']]=d

result=dict(
    checked_on='2026-11-03', source_url=SOURCE, source_version='10.0.1',
    source_last_modified=None,
    source_method='60fps screen capture; source counts from event frame as1 to frame immediately before next action. Swim begins when character starts crouching, not when fully submerged.',
    target_snapshot='11.1.0',
    version_boundary='这是旧版机制实测补充，不能声称全部为1110实测。原始解包字段仍是1110；冲突保留两者。',
    measurement_scope='列为潜墨开始的后摇；不等于回墨锁定、下一次射击间隔或总起手动作。',
    classifications={'explicit_local_parameters':'客观事实 高','source_measurements':'客观事实 中至高 受版本边界限制','event_offset_adjustments':'计算得出 中','missing':'未能检索到有效实测信源 不填造'},
    weapons=records,
    missing=[k for k,v in records.items() if v['release_to_swim_frames'] is None])
(HERE/'endlag_measurements.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(len(records),len(result['missing']),result['missing'])
