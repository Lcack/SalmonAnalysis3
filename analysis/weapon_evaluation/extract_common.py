"""Attack-mode adapters. Distances/paint are explicit geometric proxies, not engine replays."""
import math
import copy


def horizontal_travel(move, frames=300, height=1.0):
    """Flat-ground projectile proxy with explicit drag/gravity; no muzzle offset.

    State defaults are documented in notes/defaults_registry.json. Engine collision,
    player velocity and firing pose are deliberately outside this small model.
    """
    speed = move.get('SpawnSpeed', 2.0)
    straight = move.get('GoStraightToBrakeStateFrame', 4)
    max_speed = move.get('GoStraightStateEndMaxSpeed', speed)
    brake_frames = move.get('BrakeToFreeStateFrame', 4)
    threshold = move.get('BrakeToFreeVelocityY', -.15)
    vz, vy, z, y = speed, 0.0, 0.0, height
    brake_used = 0
    free = False
    for frame in range(max(1, math.ceil(frames))):
        if frame >= straight:
            if frame == straight:
                vz = min(vz, max_speed)
            if not free:
                vy = (1-move.get('BrakeAirResist', .36))*vy-move.get('BrakeGravity', .07)
                vz *= 1-move.get('BrakeAirResist', .36)
                brake_used += 1
                next_free = brake_used >= brake_frames or vy < threshold
            else:
                vy = (1-move.get('FreeAirResist', .02))*vy-move.get('FreeGravity', .016)
                vz *= 1-move.get('FreeAirResist', .02)
                next_free = True
        else:
            next_free = False
        previous_z, previous_y = z, y
        z += vz
        y += vy
        if y < 0:
            return previous_z + (z-previous_z)*previous_y/(previous_y-y)
        if frame >= straight:
            free = next_free
    return z


def shot_range(move, damage, guide=8):
    # Travel until falloff begins or the ground is reached, whichever occurs first.
    t = damage.get('ReduceStartFrame', guide)
    if t <= 0:
        t = guide
    return horizontal_travel(move, t)


def paint_area(g, range_, prefix=''):
    p = g.get(prefix+'PaintParam', {})
    sp = g.get(prefix+'SplashPaintParam', {})
    ss = g.get(prefix+'SplashSpawnParam', {})
    w = p.get('WidthHalfMiddle', p.get('WidthHalfNear', sp.get('WidthHalf', 1.5)))
    # Ellipse main landing mark + a strip connecting separately emitted droplets.
    depth = p.get('DepthScaleMax', 1.0)
    n = ss.get('SpawnNum', 1.0)
    sw = sp.get('WidthHalf', 1.5)
    return math.pi*w*w*depth + min(range_, n*2*sw)*2*sw


def mode(name, damage, interval, startup, recovery, ink, range_, width, paint,
         speed, piercing=False, **extra):
    return dict(name=name, damage=damage, interval=interval, startup=startup,
                recovery=recovery, ink=ink, range=range_, width=width,
                paint_area=paint, move_speed=speed, piercing=piercing,
                notes=[], assumptions=[], **extra)


def extract(wid, g, source_path):
    family = wid.split('_')[0]
    w = g.get('WeaponParam', {})
    d = g.get('DamageParam', {})
    m = g.get('MoveParam', {})
    out = []
    if family in ('Shooter', 'Maneuver', 'Blaster'):
        variants = [('', '站立射击')]
        if family == 'Shooter' and 'VariableWeaponParam' in g:
            variants.append(('Variable', '长按连射'))
        if family == 'Maneuver':
            variants.append(('LapOver', '翻滚后射击'))
        if family == 'Blaster' and 'BlastJumpParam' in g:
            variants.append(('Jump', '跳跃短射程'))
        for prefix, label in variants:
            wp = g.get('VariableWeaponParam', w) if prefix=='Variable' else w
            dp = g.get('DamageLapOverParam', d) if prefix=='LapOver' else g.get(prefix+'DamageParam', d)
            mp = g.get('MoveLapOverParam', m) if prefix=='LapOver' else g.get(prefix+'MoveParam', m)
            if prefix=='Jump':
                dp=g.get('DamageJumpParam',d)
                mp=g.get('MoveJumpParam',m)
            rep = wp.get('LapOver_RepeatFrame', wp.get('RepeatFrame', 6)) if prefix=='LapOver' else wp.get('RepeatFrame', 6)
            pre = wp.get('PreDelayFrame_HumanShot', 0)
            post = wp.get('PostDelayFrame_Blaster', 23) if family=='Blaster' else wp.get('PostDelayFrame', 4)
            ink = wp['InkConsume']
            ran = shot_range(mp, dp, wp.get('ShotGuideFrame', 8))
            pa = paint_area(g, ran, 'Variable' if prefix=='Variable' else '')
            damage = dp['ValueMax']/10
            width = 2*g.get('CollisionParam', {}).get('InitRadiusForPlayer', .2)
            x = mode(label, damage, rep, pre, post, ink, ran, width, pa, wp.get('MoveSpeed', .072))
            if family=='Maneuver' and prefix!='LapOver':
                step=g['SideStepParam']
                x['dodge_distance']=step.get('MoveDist',4.0)
                x['dodge_frames']=step.get('MoveFrame',12)+step.get('UnrelaxFrameMove',32)
                x['notes'].append('站立动作保留可用翻滚选项，仅在机动代理增加位移通道；不改变站立射击的伤害或起手')
            x['assumptions'].extend(['射程为平地离地1单位的分段弹道至衰减起点近似；含阻力重力，不含枪口偏移和碰撞', '涂墨为落点椭圆与滴墨条带面积和；未模拟随机重叠'])
            if 'RepeatFrame' not in wp:
                x['assumptions'].append('缺省 RepeatFrame 采用6帧；外部核验见 defaults_registry.json')
            if 'PostDelayFrame' not in wp:
                x['assumptions'].append('缺省 PostDelayFrame 采用4帧；属于显式默认假设')
            if 'Triple' in wid:
                x['burst_size'] = 3
                x['burst_gap'] = wp['TripleShotSpanFrame']
                x['notes'].append('三连发按两段RepeatFrame加TripleShotSpanFrame调度，不当作匀速射击')
                x['assumptions'].append('TripleShotSpanFrame按末发后等待处理；公开持续DPS存在触发动画计时口径差异，未将外部DPS反向校准参数')
            if prefix == 'LapOver':
                step=g['SideStepParam']
                x['startup'] = step.get('ChargeFrame',0)+step.get('MoveFrame',12)+step.get('UnrelaxFrameNoWeapon',4)
                x['entry_ink']=step['InkConsume']
                x['entry_once']=True
                x['dodge_distance']=step.get('MoveDist',4.0)
                x['dodge_frames']=step.get('MoveFrame',12)+step.get('UnrelaxFrameMove',32)
                x['recovery']=max(post,step.get('UnrelaxFrameNoSquid',32))
                x['notes'].append('翻滚有入场耗时和墨耗，不把翻滚等同无敌或无代价生存加成')
                if 'MoveDist' not in step:
                    x['assumptions'].append('缺省翻滚距离采用4单位；用于机动代理')
            if family=='Blaster':
                blast=g['BlastJumpParam'] if prefix=='Jump' else g['BlastParam']
                burst=g['BlasterBurstJumpParam'] if prefix=='Jump' else g['BlasterBurstParam']
                bdist=blast['DistanceDamage']
                x['aoe_damage']=bdist[-1]['Damage']/10
                x['width']=2*bdist[-1]['Distance']
                x['range']=horizontal_travel(mp,burst.get('BurstFrame',13))
                x['flight_frames']=burst.get('BurstFrame',13)
                rad=burst.get('SplashDropPaintRadius',3.2)
                x['paint_area']=math.pi*rad*rad + min(x['range'],g['SplashSpawnParam'].get('SpawnNum',1)*2*g['SplashPaintParam']['WidthHalf'])*2*g['SplashPaintParam']['WidthHalf']
                x['notes'].append('直击与爆风不叠加给同一目标；爆风边界伤害用于群体模型')
                if 'BurstFrame' not in burst or 'SplashDropPaintRadius' not in burst:
                    x['assumptions'].append('省略爆破时刻/涂墨半径采用逆向说明表默认13帧/3.2单位；未展开引擎继承')
            out.append(x)
        if 'SideStepBlastParam' in g:
            step=g['SideStepParam']; bp=g['SideStepBlastParam']; a=bp['DistanceDamage']
            out.append(mode('翻滚爆炸',a[0]['Damage']/10, step['MoveFrame']+step['ChargeFrame'],step['ChargeFrame'],step['UnrelaxFrameMove'],step['InkConsume'],a[-1]['Distance'],2*a[-1]['Distance'],math.pi*bp['PaintRadius']**2,step['MoveDist']/step['MoveFrame'],aoe_damage=a[-1]['Damage']/10,burst_size=step['RepeatCnt'],burst_gap=step['UnrelaxFrameMove'],dodge_distance=step['MoveDist'],dodge_frames=step['MoveFrame']+step['UnrelaxFrameMove']))
    elif family=='Charger':
        for charge,suf in [('MinCharge','点射'),('FullCharge','满蓄力')]:
            full=charge=='FullCharge'
            if '_Bear_' in wid and not full:
                continue
            pre=w.get('ChargeFrame'+charge,60 if full else 8)
            freeze=w.get('FreezeFrame'+charge,1)
            post=w.get('PostDelayFrame',8)
            ran=m.get('Distance'+charge,m['DistanceFullCharge'])
            splash=g.get('SplashPaintParam',{})
            pa=2*splash.get('WidthHalfFullCharge' if full else 'WidthHalfMinCharge',1.0)*ran/max(1,g.get('SplashSpawnParam',{}).get('SkipNum',1))
            # The next-charge gate and the swim/cancel gate are not serial.
            # A six-frame ordinary charging restart is supplementary timing
            # evidence, not an invented raw PostDelayFrame default.
            release_interval=4 if '_Bear_' in wid else pre+6
            x=mode(suf,d['Value'+charge]/10,release_interval,pre,post,w['InkConsume'+charge],ran,2*g.get('CollisionParam',{}).get('InitRadiusForPlayer',.2),pa,w.get('MoveSpeedFullCharge',.03),full and m.get('ThroughFullCharge',True))
            x['notes'].append('射程直接读取Distance字段；满蓄穿透只处理无遮挡同线目标')
            if 'ThroughFullCharge' not in m and full:x['assumptions'].append('满蓄穿透缺省采用true；竹筒/铅笔显式false优先')
            if 'ChargeFrame'+charge not in w:x['assumptions'].append('缺省蓄力采用满蓄60帧/点射8帧；见默认值登记')
            if 'PostDelayFrame' not in w:x['assumptions'].append('缺省狙击枪PostDelayFrame采用8帧')
            x['assumptions'].append('狙击枪涂墨为中间飞沫宽度乘射程并除SkipNum的条带代理；点射可能不连通')
            if '_Bear_' in wid:
                x['notes'].append('熊狙击枪只保留满蓄模式；公开机制表4帧连射，不支持普通点射，不套普通6帧再充能门限')
            else:
                x['notes'].append('普通狙击枪以解包ChargeFrame加公开机制表6帧再充能门限构成射击周期；未把缺省取消后摇串联到射击周期')
            if full and 'WeaponDivideChargerParam' in g:
                n=g['WeaponDivideChargerParam']['FullChargeDivideNum']
                x.update(batch_size=n,batch_charge=pre,batch_recovery=17,interval=17,ink=w['InkConsumeFullCharge']/n)
                x['notes'].append('铅笔蓄力后5发，整批墨耗分摊到每发；跨批计入重蓄力')
                x['notes'].append('铅笔分发间隔采用英日机制表一致的17帧；并非直接把原始PostDelayFrame15视为射击周期')
            out.append(x)
    elif family=='Spinner':
        for full,label in [(False,'一段蓄力'),(True,'满蓄力')]:
            if 'VariableShotParam' in g:
                continue
            pre=w['ChargeFrame_Second'] if full else w['ChargeFrame_First']
            duration=w['MaxShootingFrame_Second'] if full else w['MaxShootingFrame_First']
            full_override=g.get('WeaponFullChargeParam',{}) if full else {}
            duration=full_override.get('MaxShootingFrame_Second',duration)
            rep=full_override.get('RepeatFrame',w['RepeatFrame'])
            # ChargeFrame_Second is a total threshold, not added to First.
            n=max(1,math.ceil(duration/rep))
            dp=dict(d); dp['ReduceStartFrame']=d.get('ReduceStartFrame',11)
            mp=dict(m);mp['SpawnSpeed']=m.get('SpawnSpeedFirstLastAndSecond',m['SpawnSpeed'])
            ran=shot_range(mp,dp,w.get('ShotGuideFrame',11))
            x=mode(label,d.get('ValueFullChargeMax',d['ValueMax'])/10 if full else d['ValueMax']/10,rep,pre,w['PostDelayFrame'],w['InkConsume']*(1 if full else pre/w['ChargeFrame_Second'])/n,ran,.4,paint_area(g,ran),w['MoveSpeed'],batch_size=n,batch_charge=pre)
            x['assumptions'].append('部分蓄力墨耗按蓄力阈值线性插值；射击数为持续帧/射击间隔向上取整')
            x['assumptions'].append('涂墨面积/射程使用与射击枪相同的几何近似')
            if full_override:x['notes'].append('满蓄射击持续时间和连射间隔优先读取WeaponFullChargeParam，覆盖普通射击参数')
            out.append(x)
        if 'VariableShotParam' in g:
            # Ballpoint is not a generic 1-frame/1-shot partial charge. Export its
            # short recharge loop and long-range burst as separately labelled proxies.
            total=w['MaxShootingFrame_Second']
            n_short=w.get('FirstShootingTermBulletNum',10)
            short_charge=w['ChargeFrame_Second']*n_short*w['RepeatFrame']/total
            for long,label in [(False,'短射程补蓄循环'),(True,'长射程持续射击')]:
                dp=g.get('VariableDamageParam',d) if long else d
                mp=g['VariableMoveParam'] if long else m
                sp=g['VariableShotParam'] if long else w
                rep=sp['RepeatFrame']
                n=max(1,math.ceil((total-n_short*w['RepeatFrame'])/rep)) if long else n_short
                charge=w['ChargeFrame_Second'] if long else short_charge
                lead=n_short*w['RepeatFrame'] if long else 0
                ran=shot_range(mp,dp,w.get('ShotGuideFrame',11))
                ink=w['InkConsume']/n if long else w['InkConsume']*n_short*w['RepeatFrame']/total/n
                x=mode(label,dp['ValueMax']/10,rep,charge+lead,w['PostDelayFrame'],ink,ran,.4,paint_area(g,ran,'Variable' if long else ''),sp['MoveSpeed'],batch_size=n,batch_charge=charge+lead)
                x['notes'].append('圆珠笔分短射程3帧连射和长射程5帧连射；长射程入场计入先发短射程弹时间')
                x['assumptions'] += ['短射程默认前10发；10帧模式过渡未逐发插值，保留为近似', '短射程补蓄墨耗与时长按最大持续射击帧线性分配；长射程保守支付整次充能墨耗，先发短射程弹不计入其输出', '射程使用分段弹道；圆珠笔模式切换不是直接解包的独立攻击']
                out.append(x)
    elif family=='Stringer':
        b=g['spl__BulletStringerParam']; wp=g['spl__WeaponStringerParam'];c=wp['ChargeParam'];s=wp['ShotParam'];mp=b['MoveParam'];dp=b['DamageParam'];n=s.get('ArrowNum',3)
        for suffix,tag in [('Min','点射'),('Mid','一段蓄力'),('Full','满蓄力')]:
            key='Max' if suffix=='Full' else suffix
            pre=c['ChargeFrame'+suffix+'Charge'];freeze=c['FreezeFrame'+suffix+'Charge'];post=c['PostDelayFrame']
            v=mp['SpawnSpeed'+key]
            diffusion=s.get('DiffusionArrowParamArray',[])
            if diffusion:v=max(a.get('SpawnSpeed'+key,v) for a in diffusion)
            ran=horizontal_travel({**mp,'SpawnSpeed':v},height=2.0)
            angle_key='Min' if suffix=='Full' else ('Max' if suffix=='Min' else 'Mid')
            angle=abs(s.get('ArrowAngle'+angle_key,0))
            spread=2*ran*math.tan(math.radians(angle))+(n-1)*s.get('ArrowMargin',.2)
            rad=b['PaintParam']['WidthHalf'+key]
            det=b.get('DetonationParam',{});explosive=suffix=='Full' or (suffix=='Mid' and det.get('IsExplosiveBoltMidCharge',False))
            pa=n*math.pi*rad*rad
            if explosive:pa+=n*math.pi*det.get('BlastParam',{}).get('PaintRadius',0)**2
            x=mode(tag,dp['DirectHitDamage'+key]/10*n,pre+freeze,pre,post,c['InkConsume'+suffix+'Charge'],ran,max(.4,spread),pa,c['MoveSpeedFullCharge'],projectiles=n,projectile_damage=dp['DirectHitDamage'+key]/10)
            x['assumptions'] += ['单体默认所有箭命中同一大鲑鱼，为理想上界，另计算命中率敏感性', '射程按离地2单位、水平发射的分段弹道近似，包含阻力重力，非实测射程', '多箭涂墨面积使用无重叠圆面积之和，统一乘重叠修正', '箭扇宽度按角度与发射间隔的平面包络近似；负角度取绝对值，未重建交叉弹道']
            if 'ArrowAngle'+angle_key not in s:x['assumptions'].append('省略箭散角采用0度收束假设；该默认未得到引擎类表直接验证')
            if diffusion:x['notes'].append('熊弓各箭速度不同，射程采用显式DiffusionArrowParamArray中的最远箭速；总伤害仍为全中理想上界')
            x['notes'].append('ArrowAngleMax用于无蓄，ArrowAngleMid用于一圈，ArrowAngleMin用于满蓄；与Damage和SpawnSpeed后缀方向不同')
            x['notes'].append('下一次充能受FreezeFrame约束，移动取消受PostDelayFrame约束；两个并行门限不相加。射击周期为ChargeFrame加FreezeFrame')
            x['aoe_damage']=dp['DirectHitDamage'+key]/10
            x['independent_projectiles']=True
            x['notes'].append('直接命中箭不再追加同箭爆炸伤害；延迟爆炸不作为单体必得伤害')
            out.append(x)
            if explosive and det.get('BlastParam',{}).get('DistanceDamage'):
                explosion=copy.deepcopy(x)
                blast=det['BlastParam'];bounds=blast['DistanceDamage'][-1]
                radius=bounds['Distance'];spacing=spread/max(1,n-1)
                overlap=0 if spacing>=2*radius else 2*radius**2*math.acos(spacing/(2*radius))-.5*spacing*math.sqrt(4*radius**2-spacing**2)
                union_area=n*math.pi*radius**2-max(0,n-1)*overlap
                explosion.update(name=tag+'滞留爆炸',damage=bounds['Damage']/10*n,
                                 startup=pre+det.get('DetonationFrame',45),
                                 independent_projectiles=False,aoe_projectiles=n,
                                 aoe_damage=bounds['Damage']/10,aoe_radius=radius,aoe_union_area=union_area)
                explosion['notes'].append('独立滞留爆炸情景：同箭不计直击；清杂以等间距爆点圆并集扣除重叠，仅计一份爆风伤害')
                explosion['assumptions'].append('滞留爆点沿箭扇宽度等间距布置；群攻按圆并集面积，单体多爆同时命中另为理想上界；未模拟敌人离开')
                out.append(explosion)
    else:
        raise ValueError(f'Unsupported family {family}')
    return out
