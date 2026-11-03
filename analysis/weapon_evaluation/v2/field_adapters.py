"""Supplemental v2 fields with explicit missingness and measurement provenance.

No legacy metric is silently re-used as a newly defined measurement. Distances
below are flat-ground physical proxies, not claims of measured enemy hit range.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENDLAG = json.loads((HERE/'notes/endlag_measurements.json').read_text(encoding='utf8'))
JP_FIELDS = 'https://wikiwiki.jp/splatoon3mix/検証/パラメータ情報/メイン'
JP_TIMING = ENDLAG['source_url']
TRAJECTORY_SOURCE = 'https://github.com/sendou-ink/sendou.ink/blob/main/app/features/comp-analyzer/core/WeaponRange.ts'
PARAM_DEFAULTS_SOURCE = 'https://splatoonwiki.org/wiki/User:XarrotD/paramtable'


def _radius(c):
    if 'ParamArray' in c:
        return max((_radius(x) for x in c['ParamArray']), default=0.0)
    return max(float(c.get('InitRadiusForPlayer',0)),float(c.get('EndRadiusForPlayer',0)))


def _trajectory(move, pitch, height=1.0, limit=600):
    """Forward travel until floor contact or explicit projectile expiry.

    Assumes an upward aim angle and a point floor. Unknown collision/pose logic
    and the enemy's hitbox are not invented. Straight/brake/free defaults are
    independently recorded; the state transition remains a model approximation.
    """
    speed=float(move.get('SpawnSpeed',0))
    if speed<=0:return None
    a=math.radians(pitch)
    vz,vy=speed*math.cos(a),speed*math.sin(a)
    z,y=0.0,height
    straight=max(0,int(move.get('GoStraightToBrakeStateFrame',4)))
    maxspeed=float(move.get('GoStraightStateEndMaxSpeed',speed))
    bframes=max(0,int(move.get('BrakeToFreeStateFrame',4)))
    threshold=float(move.get('BrakeToFreeVelocityY',-.15))
    brake=0;free=bframes==0
    for f in range(max(1,min(int(limit),600))):
        if f>=straight:
            if f==straight:
                norm=math.hypot(vz,vy)
                if norm>maxspeed and norm>0:
                    vz*=maxspeed/norm;vy*=maxspeed/norm
            if not free:
                air=float(move.get('BrakeAirResist',.36));gravity=float(move.get('BrakeGravity',.07))
                brake+=1
            else:
                air=float(move.get('FreeAirResist',.02));gravity=float(move.get('FreeGravity',.016))
            vz*=1-air;vy=vy*(1-air)-gravity
        zz,yy=z,y
        z+=vz;y+=vy
        if y<0:
            return zz+(z-zz)*yy/(yy-y)
        if f>=straight and not free and (brake>=bframes or vy<threshold):free=True
        if vz<1e-7:return z
    return z


def _sweep(move, collision=None, native_angle=0.0, limit=600):
    vals=[(_trajectory(move,p+native_angle,limit=limit),p) for p in range(46)]
    vals=[(v,p) for v,p in vals if v is not None]
    if not vals:return None,None
    value,angle=max(vals)
    return value+_radius(collision or {}),angle


def _endlag(wid,gp,m):
    r=deepcopy(ENDLAG['weapons'][wid])
    family=wid.split('_')[0];name=m['name']
    out=dict(value=r['release_to_swim_frames'],source_url=r['source_url'],
             source_version=ENDLAG['source_version'],source_measurement_status=r['measurement_status'],
             origin=r['origin'],classification='客观事实 旧版实测',confidence='中',
             notes=r['notes'],phase_range_frames=None)
    if out['value'] is None:
        out.update(classification='缺测',confidence='无',notes=r['notes']+['未能检索到该模式有效实测信源，不用旧recovery或任意常数冒充。'])
    if family=='Shooter' and wid=='Shooter_Flash_Coop':
        d=r['modes']['hold' if '长按' in name else 'tap']
        out.update(value=d['release_to_swim_frames'],origin=d['origin'])
    elif family in ('Roller','Brush'):
        if m.get('rolling'):
            out.update(value=None,origin='rolling_has_no_projectile',classification='不适用',confidence='高')
            out['notes'].append('推刷和碾压没有射出子弹；取消行进至潜墨为另一指标，不进入严格射击Endlag。')
        elif family=='Roller' and r['modes']:
            d=r['modes']['vertical' if '纵' in name else 'horizontal']
            out.update(value=d['release_to_swim_frames'],origin=d['origin'])
    elif family=='Slosher' and r['origin']=='first_projectile_release':
        # v2 uses the final projectile as the single zero-time of a whole action.
        d=r['modes']['last_projectile']
        out.update(value=d['release_to_swim_frames'],origin='last_projectile_release',classification='计算得出 旧版首发实测减本地发射偏移')
        out['notes'].append('整次动作以最后一颗有效弹为零时刻；原始首发至潜墨值另留在endlag_measurements.json。')
    elif family=='Saber' and r['modes']:
        key='charged_stationary' if m.get('charged') else 'horizontal_first'
        d=r['modes'][key]
        out.update(value=d['release_to_swim_frames'],origin='ink_wave_release',classification='计算得出 旧版首攻击实测扣除剑气偏移')
        if '近战' in name:
            out['notes'].append('普通刀近战动作同时有剑气；此处仍从剑气事件计时，近战命中事件早3帧。')
    elif family=='Maneuver' and ('翻滚' in name):
        out['notes'].append('此模式含翻滚状态，最初一发还受翻滚锁定剩余时间影响。普通射击取消基线不是新翻滚动作的固定后摇。')
        if m.get('entry_once'):
            step=gp.get('SideStepParam',{})
            left=max(0,float(step.get('UnrelaxFrameNoSquid',0))-float(step.get('UnrelaxFrameNoWeapon',0)))
            if out['value'] is not None:
                out['initial_post_roll_remaining_lock_proxy_frames']=left
                out['initial_post_roll_to_swim_lower_bound_frames']=max(out['value'],left)
    if out['value'] is not None and out['origin']=='cancel_input':
        wp=gp.get('VariableWeaponParam',gp.get('WeaponParam',{})) if '长按' in name else gp.get('WeaponParam',{})
        rep=wp.get('LapOver_RepeatFrame',wp.get('RepeatFrame',6)) if '翻滚后' in name else wp.get('RepeatFrame',6)
        out['phase_range_frames']=[out['value'],out['value']+max(0,float(rep)-1)]
    if family=='Spinner':
        # The source explicitly distinguishes these two clocks and says its
        # transition threshold still needs verification. Do not turn input-to-
        # swim 6F into an invented fixed last-projectile-to-swim value.
        out['sustained_cancel_to_swim_frames']=r['modes']['sustained_cancel']['cancel_to_swim_frames']
        out['sustained_cancel_origin']='cancel_input'
        out['source_mechanism_uncertainty']='first-shot and sustained-cancel gates do not run in parallel; 6–7F threshold not fully verified by source'
    # Explicit v1110 blaster cancel field has directly documented semantics.
    if family=='Blaster':
        val=gp.get('WeaponParam',{}).get('PostDelayFrame_Blaster')
        if val is not None:
            out.update(value=float(val),origin='projectile_release',source_url=JP_FIELDS,
                       source_version='11.1.0 local parameter plus parameter meaning',
                       classification='客观事实 参数值 逻辑推断对应潜墨',confidence='中至高')
            out['legacy_measured_value_frames']=r['release_to_swim_frames']
            if val!=r['release_to_swim_frames'] and r['release_to_swim_frames'] is not None:
                out['notes'].append('采用本地新版显式Blaster后摇字段，旧实测冲突保留供复核。')
    if out['value'] is None and '_Bear_' in wid:
        val=None;interval=None;description=None
        if family=='Maneuver' and '爆炸' not in name:
            val=gp.get('WeaponParam',{}).get('PostDelayFrame')
            interval=[val,val+max(0,float(m.get('interval',1))-1)] if val is not None else None
            description='只把本地PostDelayFrame作取消窗口代理；无熊双枪实测，不等同已确认末弹至潜墨。'
            if '翻滚后' in name and val is not None:
                step=gp.get('SideStepParam',{})
                left=max(0,float(step.get('UnrelaxFrameNoSquid',0))-float(step.get('UnrelaxFrameNoWeapon',0)))
                val=max(val,left);interval=[min(interval[0],val),max(interval[1],val)]
        elif family=='Roller' and not m.get('rolling') and '纵' not in name:
            raw=gp.get('WeaponWideSwingParam',{}).get('SubWeaponSquidDelayFrm')
            if raw is not None:val=float(raw)+5;interval=[float(raw),val]
            description='熊滚横甩SubWeaponSquidDelayFrm显式8；采用常规同类实测差5F的映射作13F低置信代理，区间8至13，不称熊武器实测。'
        elif family=='Slosher':
            raw=gp.get('WeaponParam',{}).get('PostDelayFrame')
            if raw is not None:val=float(raw)+10;interval=[float(raw),val]
            description='熊桶显式PostDelayFrame15；普通同类表的潜墨值比该字段多10F，移植为25F低置信代理，区间15至25。'
        elif family=='Stringer':
            raw=gp.get('spl__WeaponStringerParam',{}).get('ChargeParam',{}).get('PostDelayFrame')
            if raw is not None:val=float(raw)+1;interval=[float(raw),val]
            description='熊弓显式PostDelayFrame10；用普通弓相同字段至测量的1F差作11F低置信代理，区间10至11。'
        elif family=='Saber':
            prefix='ChargeSwing' if m.get('charged') else 'WeakSwing'
            raw=gp.get('spl__WeaponSaberParam',{}).get('SwingParam',{}).get(prefix+'PostDelayFrame')
            out['attack_event_to_swim_proxy_frames']=float(raw) if raw is not None else None
            out['attack_event_to_swim_proxy_interval_frames']=[float(raw),float(raw)+1] if raw is not None else None
            out['notes'].append('熊刀严格没有子弹：只额外提供本地攻击事件后摇代理，不写入release_to_swim_frames；采用扩展口径需单列。')
        if val is not None:
            out.update(value=val,origin='local_cancel_field_proxy',source_url=JP_FIELDS,
                       source_version='11.1.0 explicit parameter plus v10.0.1 mechanism extrapolation',
                       classification='推测假设 缺测熊武器参数代理',confidence='低',
                       proxy_interval_frames=interval)
            out['notes'].append(description)
    return out


def _range(wid,gp,m):
    family=wid.split('_')[0];name=m['name'];candidates=[];notes=[];paths=[]
    eligible=not (family=='Blaster' and '跳跃' in name) and not (family=='Roller' and '纵' in name)
    meta=dict(classification='计算得出 几何代理',confidence='低',source_url=TRAJECTORY_SOURCE,
              aim_pitch_degrees=[0,45],aim_step_degrees=1,spawn_height=1.0,
              enemy_hitbox_included=False,muzzle_offset_included=False,
              definition='平地固定离地1单位扫仰角，到首次地面相交前的水平距离，加显式弹丸碰撞半径；不是地面涂墨长度。',
              partial=False,notes=notes,parameter_paths=paths)
    if not eligible:
        meta['notes'].append('此攻击要求跳跃，不属于平地不起跳射程场景。')
        return None,False,meta
    if m.get('rolling'):
        c=gp.get('BodyParam',{}).get('CollisionParam',{})
        val=c.get('Radius')
        paths.append('BodyParam.CollisionParam.Radius')
        meta.update(definition='接触形状前向半径，行进距离不算武器射程。',partial=True)
        return (float(val) if val is not None else None),True,meta
    if family=='Maneuver' and '翻滚爆炸' in name:
        data=gp.get('SideStepBlastParam',{}).get('DistanceDamage',[])
        value=max((float(x['Distance']) for x in data),default=None)
        paths.append('SideStepBlastParam.DistanceDamage')
        meta.update(definition='翻滚爆炸以爆心为原点的显式最大伤害半径；不额外计翻滚位移。',source_url=JP_FIELDS,confidence='中')
        return value,True,meta
    if family in ('Shooter','Maneuver','Spinner'):
        prefix=''
        if family=='Shooter' and '长按' in name:prefix='Variable'
        if family=='Maneuver' and '翻滚后' in name:prefix='LapOver'
        if family=='Spinner' and '长射程' in name:prefix='Variable'
        mk='MoveLapOverParam' if prefix=='LapOver' else prefix+'MoveParam'
        ck='CollisionLapOverParam' if prefix=='LapOver' else prefix+'CollisionParam'
        move=deepcopy(gp.get(mk,gp.get('MoveParam',{})))
        if family=='Spinner':move['SpawnSpeed']=move.get('SpawnSpeedFirstLastAndSecond',move.get('SpawnSpeed',0))
        value,angle=_sweep(move,gp.get(ck,gp.get('CollisionParam',{})))
        paths.extend([mk,ck]);meta['maximizing_pitch_degrees']=angle
        if family=='Spinner':notes.append('初速随机项未取极端幸运值；使用显式名义初速。')
        return value,True,meta
    if family=='Blaster':
        move=gp['MoveParam'];burst=gp['BlasterBurstParam'];blast=gp['BlastParam']
        value,angle=_sweep(move,gp.get('CollisionParam',{}),limit=burst.get('BurstFrame',13))
        radius=max((float(x['Distance']) for x in blast.get('DistanceDamage',[])),default=0)
        value=(value+radius) if value is not None else None
        paths.extend(['MoveParam','BlasterBurstParam.BurstFrame','BlastParam.DistanceDamage']);meta['maximizing_pitch_degrees']=angle
        notes.append('爆炸属于可命中范围，额外加显式最外爆风半径；不把爆炸涂墨半径当伤害半径。')
        return value,True,meta
    if family=='Charger':
        key='DistanceMinCharge' if '点射' in name else 'DistanceFullCharge'
        value=gp.get('MoveParam',{}).get(key)
        paths.append('MoveParam.'+key)
        meta.update(definition='直接使用该充能状态Distance参数。',confidence='中',source_url=JP_FIELDS)
        notes.append('参数距离从枪口起算；本口径没有额外补枪口长度和敌人半径。')
        return (float(value) if value is not None else None),True,meta
    if family=='Stringer':
        b=gp['spl__BulletStringerParam'];wp=gp['spl__WeaponStringerParam']
        key='Max' if '满蓄' in name else ('Mid' if '一段' in name else 'Min')
        move=deepcopy(b['MoveParam']);move['SpawnSpeed']=move.get('SpawnSpeed'+key,0)
        diff=wp.get('ShotParam',{}).get('DiffusionArrowParamArray',[])
        if diff:move['SpawnSpeed']=max(x.get('SpawnSpeed'+key,move['SpawnSpeed']) for x in diff)
        value,angle=_sweep(move,b.get('CollisionParam',{}))
        det=b.get('DetonationParam',{})
        explosive=key=='Max' or (key=='Mid' and det.get('IsExplosiveBoltMidCharge',False))
        if explosive:
            rad=max((x['Distance'] for x in det.get('BlastParam',{}).get('DistanceDamage',[])),default=0)
            if value is not None:value+=rad
        paths.extend(['spl__BulletStringerParam.MoveParam.SpawnSpeed'+key,'spl__BulletStringerParam.CollisionParam'])
        meta['maximizing_pitch_degrees']=angle
        notes.append('忽略各箭横向散布对最远水平距离的影响；熊弓采用最快显式箭速，属于几何可达上界。')
        return value,True,meta
    if family in ('Roller','Brush'):
        group=gp.get('SwingUnitGroupParam' if family=='Brush' else 'WideSwingUnitGroupParam',{})
        p=group.get('DamageParam',{}).get('Inside',{})
        value=p.get('DamageMinDistance')
        paths.append(('SwingUnitGroupParam' if family=='Brush' else 'WideSwingUnitGroupParam')+'.DamageParam.Inside.DamageMinDistance')
        meta.update(definition='伤害衰减最远距离锚点，保留为已知可伤害范围代理，不声称等于完整弹道极限。',partial=True,source_url=JP_FIELDS)
        return (float(value) if value is not None else None),True,meta
    if family=='Slosher':
        units=gp.get('UnitGroupParam',{}).get('Unit',[])
        for i,u in enumerate(units):
            n=int(u.get('BulletNum',1))
            if n<=0 or max(float(u.get('DamageParam',{}).get('ValueMax',0)),float(u.get('DamageParam',{}).get('ValueMin',0)))<=0:continue
            move=deepcopy(u.get('MoveParam',{}))
            speed=float(u.get('SpawnSpeedGround',u.get('SpawnSpeedBase',move.get('SpawnSpeed',0))))
            # Each unit can change successive glob speeds; choose the maximum
            # explicitly generated glob rather than assuming every one is first.
            speed=max(speed+j*float(u.get('AfterOffsetSpawnSpeed',0)) for j in range(n))
            move['SpawnSpeed']=speed
            native=math.degrees(math.atan(float(u.get('AddSpawnSpeedYRateByXZ',0))))
            value,angle=_sweep(move,u.get('CollisionParam',{}),native_angle=native)
            if value is not None:candidates.append((value,angle,i))
            paths.append(f'UnitGroupParam.Unit[{i}].MoveParam + SpawnSpeedGround + AfterOffsetSpawnSpeed')
        if not candidates:return None,True,meta
        value,angle,i=max(candidates)
        blast=gp.get('BlastParam',{}).get('BlastParam',{})
        radius=max((float(x['Distance']) for x in blast.get('DistanceDamage',[])),default=0)
        value+=radius
        meta['maximizing_pitch_degrees']=angle;meta['maximizing_unit']=i
        if 'BounceGroupParam' in gp:
            meta['partial']=True;notes.append('未复现浴缸多次弹跳；这里只到首次落地，不能当其完整平地最远射程。')
        notes.append('Unit中的SpawnSpeedGround替代MoveParam内的0占位，初始上升比以atan换成原生角度；此变换仍属模型假设。')
        return value,True,meta
    if family=='Shelter':
        groups=gp.get('spl__BulletShelterShotgunParam',{}).get('GroupParams',[])
        for i,g in enumerate(groups):
            value,angle=_sweep(g.get('MoveParam',{}),g.get('CollisionParam',{}),native_angle=float(g.get('VerticalDegree',0)))
            if value is not None:candidates.append((value,angle,i))
        if not candidates:return None,True,meta
        value,angle,i=max(candidates)
        paths.append(f'spl__BulletShelterShotgunParam.GroupParams[{i}].MoveParam/CollisionParam')
        meta.update(maximizing_pitch_degrees=angle,maximizing_group=i)
        notes.append('最远一颗散弹能命中，不代表远端仍能达到整发伤害上限。')
        return value,True,meta
    if family=='Saber':
        charged=m.get('charged',False);ori='Vertical' if charged else 'Horizontal'
        swing=gp.get('spl__WeaponSaberParam',{}).get('SwingParam',{})
        if m.get('melee'):
            shape=gp.get('BulletSaberSlash'+ori+'Param',{}).get('ShapeParam',{})
            value=float(shape.get('BoxCenter',{}).get('Z',0))+float(shape.get('BoxHalfExtents',{}).get('Z',0))
            if shape.get('HasCylinderShape'):
                value=max(value,max(float(shape.get(k,{}).get('Z',0)) for k in ['CylinderCenterA','CylinderCenterB'])+float(shape.get('CylinderRadius',0)))
            off=swing.get('ShotSlashOffset_Vertical' if charged else 'ShotSlashOffset_L',{})
            value+=float(off.get('Z',0))
            paths.append('BulletSaberSlash'+ori+'Param.ShapeParam + explicit ShotSlashOffset')
            meta.update(partial=True,definition='刀身判定盒或胶囊最前端加显式发射位置，未增加玩家踏步位移。')
            return value,True,meta
        bullet=gp.get('BulletSaber'+ori+'Param',{});move=bullet.get('MoveParam',{})
        frame=bullet.get('BurstParam',{}).get('BurstFrame')
        if frame is None:return None,True,meta
        value=float(move.get('SpawnSpeed',0))*float(frame)
        off=swing.get('ShotBulletOffset_Vertical' if charged else 'ShotBulletOffset_L',{})
        value+=float(off.get('Z',0))+_radius(bullet.get('CollisionParam',{}))
        paths.extend(['BulletSaber'+ori+'Param.MoveParam.SpawnSpeed','BulletSaber'+ori+'Param.BurstParam.BurstFrame'])
        meta.update(partial=True,definition='显式刀波初速乘消失帧加发射偏移和碰撞半径；竖斩末段下坠未复现。',source_url=JP_FIELDS)
        return value,True,meta
    return None,True,meta


def _wall(wid,gp,m):
    family=wid.split('_')[0];name=m['name'];paths=[];radii=[];defaults=[]
    def take(o,path,keys=('PaintRadiusShock',)):
        for key in keys:
            value=o.get(key)
            if isinstance(value,(int,float)) and value>0:
                radii.append(float(value));paths.append(path+'.'+key)
        if not any(key in o for key in keys) and 'PaintRadiusShock' in keys and o.get('$type')=='spl__BulletWallDropCollisionPaintParam':
            radii.append(1.3);paths.append(path+'.PaintRadiusShock [typed default]')
            defaults.append(dict(path=path,checked_type=o['$type'],value=1.3,source_url='https://splatoonwiki.org/wiki/User:XarrotD/paramtable'))
    if m.get('rolling'):
        return None,dict(parameter_paths=[],confidence='无',notes=['碾压/推刷不产生射出弹丸，本墙面冲击代理不适用。'])
    if family in ('Shooter','Maneuver','Spinner','Blaster'):
        take(gp.get('WallDropCollisionPaintParam',{}),'WallDropCollisionPaintParam')
    elif family=='Charger':
        take(gp.get('WallDropCollisionPaintParam',{}),'WallDropCollisionPaintParam',('PaintRadiusShockMinCharge',) if '点射' in name else ('PaintRadiusShockMaxCharge','PaintRadiusShock'))
    elif family=='Stringer':
        take(gp.get('spl__BulletStringerParam',{}).get('WallDropPaintParam',{}),'spl__BulletStringerParam.WallDropPaintParam')
    elif family in ('Roller','Brush'):
        k='SwingUnitGroupParam' if family=='Brush' else ('VerticalSwingUnitGroupParam' if '纵' in name else 'WideSwingUnitGroupParam')
        for i,u in enumerate(gp.get(k,{}).get('Unit',[])):
            if int(u.get('BulletNum',1))>0:take(u.get('UnitParam',{}).get('WallDropCollisionPaintParam',{}),f'{k}.Unit[{i}].UnitParam.WallDropCollisionPaintParam')
    elif family=='Slosher':
        for i,u in enumerate(gp.get('UnitGroupParam',{}).get('Unit',[])):
            if int(u.get('BulletNum',1))>0:take(u.get('WallDropCollisionPaintParam',{}),f'UnitGroupParam.Unit[{i}].WallDropCollisionPaintParam')
    elif family=='Shelter':
        take(gp.get('spl__BulletShelterShotgunParam',{}).get('SplashWallDropCollisionParam',{}),'spl__BulletShelterShotgunParam.SplashWallDropCollisionParam')
    elif family=='Saber' and '_Bear_' not in wid:
        k='BulletSaberVerticalParam' if m.get('charged') else 'BulletSaberHorizontalParam'
        take(gp.get(k,{}).get('WallDropPaintParam',{}),k+'.WallDropPaintParam')
    meta=dict(parameter_paths=paths,typed_defaults_applied=defaults,source_url=JP_FIELDS,confidence='低',classification='推测假设 单冲击圆几何代理',
              notes=['只取最大一个适用墙面冲击墨点半径构造圆面积πr²；伞使用SplashWallDropCollisionParam，墨滴数量与击墙时序未还原；不把多滴、爆风、下流墨迹全部无重叠叠加。',
                     '这不是引擎墙面着色面积；墙距、弹丸散布、墙面纹理、下流时长未统一，不能声称实测墙涂或对所有武器都是严格下界。'])
    if not radii:
        meta.update(confidence='无',classification='缺测')
        meta['notes'].append('当前稀疏文件缺少适用的直接撞墙半径；不以地面半径或同类常数补造。')
        meta['notes'].append('默认1.3只在节点显式$type为spl__BulletWallDropCollisionPaintParam时可补；缺节点或无$type不凭形似补值。')
        return None,meta
    return math.pi*max(radii)**2,meta


def _wall_profiles(wid,gp,m,direct_area,direct_evidence):
    """Conditional paint-radius candidates, never damage-radius wall areas.

    The parameter researcher explicitly leaves parts of blaster paint generation
    unresolved. These circles are comparable geometric candidates, not an engine
    reconstruction or measured wall footprint.
    """
    if not wid.startswith('Blaster_'):
        base=dict(area=direct_area,candidate_area=direct_area,
                  model='existing_direct_wall_impact_circle',
                  classification=direct_evidence.get('classification','缺测'),
                  confidence=direct_evidence.get('confidence','无'),
                  source_url=direct_evidence.get('source_url'),
                  distance=None,
                  distance_condition='尚未复现该类墙距对涂墨面积的影响；沿用已列单冲击圆代理。',
                  evidence=deepcopy(direct_evidence))
        return {'near':deepcopy(base),'burst':deepcopy(base),
                'distance_dependence_modeled':False}

    jump='跳跃' in m['name']
    suffix='Jump' if jump else ''
    bk='BlasterBurst'+suffix+'Param'
    burst=gp.get(bk,{})
    move=gp.get('Move'+suffix+'Param',{})
    blast=gp.get('Blast'+suffix+'Param',{})
    typed=burst.get('$type')=='spl__BulletBlasterBurstParam'
    def paint_candidate(key,default):
        val=burst.get(key)
        status='local_explicit'
        if val is None and typed:
            val=default;status='documented_default_for_explicit_class'
        elif val is None:status='missing_unverified_class'
        return val,dict(parameter_path=bk+'.'+key,
                        parameter_status=status,
                        checked_type=burst.get('$type'),
                        default_source_url=PARAM_DEFAULTS_SOURCE if status=='documented_default_for_explicit_class' else None,
                        parameter_meaning_source_url=JP_FIELDS)
    near_radius,near_e=paint_candidate('SplashPaintShotColHitRadius',1.4)
    burst_radius,burst_e=paint_candidate('SplashPaintRadius',2.0)
    frame=burst.get('BurstFrame')
    frame_status='local_explicit'
    if frame is None and typed:frame=13;frame_status='documented_default_for_explicit_class'
    center=_trajectory(move,0,limit=frame) if frame is not None else None
    damage_radius=max((float(x['Distance']) for x in blast.get('DistanceDamage',[])),default=None)
    outer=center+damage_radius if center is not None and damage_radius is not None else None
    def profile(radius,evidence,condition):
        area=math.pi*float(radius)**2 if radius is not None else None
        return dict(area=area,candidate_area=area,radius=radius,
                    model='single_paint_radius_circle_pi_r_squared',
                    classification='推测假设 距离条件下的涂墨半径几何候选' if area is not None else '缺测',
                    confidence='低' if area is not None else '无',
                    source_url=JP_FIELDS,
                    evidence=evidence,
                    distance_condition=condition,
                    damage_radius_used_for_area=False,
                    notes=['原研究者明确部分爆破涂墨参数调用关系仍不明；此圆面积不是实测墙涂或完整引擎仿真。',
                           '墙面倾角、与爆心间隙、离地高度、散射飞沫、着色纹理与下流没有统一；不把πr²当任何墙距下的保证覆盖面积。'])
    near=profile(near_radius,near_e,'弹丸在自然爆炸帧之前提前碰到竖直墙，使用提前撞地形的涂墨半径候选。')
    near.update(distance=None,
                direct_wall_drop_area=direct_area,
                direct_wall_drop_evidence=deepcopy(direct_evidence),
                distance_less_than_natural_burst_center_proxy=center)
    natural=profile(burst_radius,burst_e,'墙位于自然爆点附近、弹丸没有提前撞墙；用自然爆炸涂墨半径候选，不等同最远伤害边缘。')
    natural.update(distance=center,
                   distance_origin='flat_ground_spawn_height_1_pitch_0_projectile_center_no_muzzle_offset',
                   natural_burst_frame=frame,
                   natural_burst_frame_status=frame_status,
                   natural_burst_frame_default_source_url=PARAM_DEFAULTS_SOURCE if frame_status!='local_explicit' else None,
                   damage_outer_radius=damage_radius,
                   damage_outer_edge_distance=outer,
                   distance_geometry_note='distance是0度发射下爆点中心的水平travel；damage_outer_edge_distance另外加伤害半径。二者都不是墙面涂墨面积或同一墙距。')
    unknown={key:dict(value=burst.get(key),local_explicit=key in burst,used_for_area=False,
                       meaning_status='原研究表含义不明，不用于主要面积候选')
             for key in ['WallHitPaintRadius','SplashDropPaintRadius','SplashDropPaintShotColHitRadius']}
    return dict(near=near,burst=natural,distance_dependence_modeled=True,
                distance_model_scope='只区分提前撞墙与自然爆点附近两种条件，未实现连续墙距着色仿真。',
                unmodeled_paint_fields=unknown,
                generic_BlastParam_PaintRadius=blast.get('PaintRadius'),
                generic_paint_note='本地BlastParam.PaintRadius为0不能推导为没有爆炸涂墨；BlasterBurstParam另有非零涂墨半径。',
                grounded_eligible=not jump)


def adapt_modes(wid,gp,modes):
    result=deepcopy(modes)
    for m in result:
        if wid.startswith('Shooter_Triple') and 'burst_gap' in m:
            m['burst_gap']+=2
            m['burst_timing_evidence']=dict(source_url=JP_TIMING,source_version='10.0.1',
                added_next_humanoid_startup_frames=2,
                formula='first-to-first=2*RepeatFrame+TripleShotSpanFrame+2',
                classification='计算得出 60fps机制时序补充')
        e=_endlag(wid,gp,m)
        m['release_to_swim_frames']=e['value']
        m['release_to_swim_evidence']=e
        m['release_to_swim_phase_range_frames']=e.get('phase_range_frames')
        value,eligible,r=_range(wid,gp,m)
        m['range_extreme_proxy']=value
        m['range_grounded_eligible']=eligible
        m['range_extreme_evidence']=r
        wall,w=_wall(wid,gp,m)
        m['wall_area_per_action_proxy']=wall
        m['wall_area_evidence']=w
        m['wall_profiles']=_wall_profiles(wid,gp,m,wall,w)
        m['partial_metrics_notes']=[*r.get('notes',[]),*w.get('notes',[])]
    return result
