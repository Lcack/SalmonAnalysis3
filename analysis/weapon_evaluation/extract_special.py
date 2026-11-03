"""Auditable action extraction for Roller, Brush, Slosher, Shelter and Saber.

Values are parameters or explicitly labelled geometric/timing proxies.  This is
not a game-engine simulation.  A unit with many globs is *not* automatically a
many-hit single-target attack.  Damage is divided by ten at the boundary.
"""

from __future__ import annotations

import math


MECHANIC_SOURCES = {
    "bear_saber": "https://splatoonwiki.org/wiki/Grizzco_Splatana",
    "brush_defaults": "https://splatoonwiki.org/wiki/Octobrush",
    "shelter_defaults": "https://splatoonwiki.org/wiki/Splat_Brella",
    "roller_periods": "https://overfishing.wiki/%E3%82%A6%E3%82%A7%E3%83%9D%E3%83%B3%E6%83%85%E5%A0%B1",
    "slosher_mechanics": "https://wikiwiki.jp/splatoon3mix/%E3%82%B5%E3%83%BC%E3%83%A2%E3%83%B3%E3%83%A9%E3%83%B3/%E3%83%96%E3%82%AD%E5%88%A5%E7%AB%8B%E3%81%A1%E5%9B%9E%E3%82%8A/%E3%82%B9%E3%83%AD%E3%83%83%E3%82%B7%E3%83%A3%E3%83%BC%E5%B1%9E",
}


def _num(d, key, default, assumptions, description=None):
    value = d.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    assumptions.append(description or f"{key}缺省，模型取{default}，并非完整引擎默认值核定")
    return float(default)


def _new(name, source_path, assumptions=None, notes=None, **kwargs):
    assumptions = list(assumptions or [])
    record = {
        "name": name,
        "damage": None,
        "interval": None,
        "startup": None,
        "recovery": None,
        "ink": None,
        "range": None,
        "width": None,
        "paint_area": None,
        "move_speed": None,
        "piercing": False,
        "source_path": str(source_path),
        "assumptions": assumptions,
        "notes": list(notes or []),
        "range_proxy": True,
        "paint_proxy": True,
    }
    record.update(kwargs)
    record["notes"].extend("假设：" + a for a in assumptions)
    return record


def _ellipse_union(ellipses, step=0.30):
    """Deterministic midpoint raster union; avoids summing overlapping splats.

    Each tuple is x, forward-z, lateral-radius, forward-radius.  Coordinate
    placement is a flat-floor model, not a claim about actual ink coverage.
    """
    ellipses = [(x, z, rx, rz) for x, z, rx, rz in ellipses if rx > 0 and rz > 0]
    if not ellipses:
        return 0.0
    xmin = min(x - rx for x, z, rx, rz in ellipses)
    xmax = max(x + rx for x, z, rx, rz in ellipses)
    zmin = min(z - rz for x, z, rx, rz in ellipses)
    zmax = max(z + rz for x, z, rx, rz in ellipses)
    n = 0
    x = xmin + step / 2
    while x < xmax:
        z = zmin + step / 2
        while z < zmax:
            if any(((x - ex) / rx) ** 2 + ((z - ez) / rz) ** 2 <= 1 for ex, ez, rx, rz in ellipses):
                n += 1
            z += step
        x += step
    return round(n * step * step, 4)


def _paint_unit_ellipses(units, assumptions):
    """Place all known bullet-unit endpoint ellipses and union their areas."""
    ellipses = []
    for i, unit in enumerate(units):
        if unit.get("PaintOnly") is False or "PaintOnly" not in unit:
            pass  # Damage-bearing bullets also paint.
        p = unit.get("UnitParam", {}).get("PaintParam", unit.get("PaintParam", {}))
        if not p:
            continue
        near = p.get("WidthHalfNear", p.get("WidthHalfNearest", p.get("WidthHalf", 0)))
        far = p.get("WidthHalfFar", near)
        radius = (float(near) + float(far)) / 2
        if radius <= 0:
            continue
        distance = p.get("DistanceXZFar", p.get("DistanceFar", 10.0))
        depth = p.get("DepthScaleNear", p.get("DepthScaleMaxStraight", p.get("DepthScaleMax", 1.0)))
        count = int(unit.get("BulletNum", 1))
        if "BulletNum" not in unit:
            assumptions.append(f"涂墨Unit[{i}]未列BulletNum，以1颗建几何代理")
        if count <= 0:
            continue
        half_angle = float(unit.get("SpawnWideDegree", unit.get("RandomRotateYDegree", 0)))
        base_angle = float(unit.get("BaseRotateYDegree", unit.get("SpawnRotateYDegree", 0)))
        for j in range(count):
            angle = base_angle + (2 * j / (count - 1) - 1) * half_angle if count > 1 else base_angle
            angle = math.radians(angle)
            # Floor endpoint at the parameter's far-distance anchor.  The
            # endpoint's forward radius includes its depth multiplier.
            ellipses.append((distance * math.sin(angle), distance * math.cos(angle), radius, radius * depth))
        # Sloshers explicitly specify the floor droplets underneath a flight
        # path.  Read the Combination indirection rather than assigning every
        # SplashParam to every glob.  Wall-only droplets are excluded from this
        # flat-floor proxy.
        spawn_group = unit.get("SplashAndSplashWallHitSpawnPrm", {})
        params = spawn_group.get("SplashParam", [])
        used = set()
        for combo in spawn_group.get("Combination", []):
            idx = int(combo.get("SplashArrayOrderNum", -1))
            if idx < 0 or idx >= len(params) or idx in used:
                continue
            used.add(idx)
            splash = params[idx]
            paint = splash.get("DrawSizeCollisionPaintParam", {})
            spawn = splash.get("SpawnParam", {})
            pr = float(paint.get("PaintWidthHalf", 0))
            pd = float(paint.get("PaintDepthScale", 1))
            spacing = float(spawn.get("SpawnBetweenLength", 3))
            first = (float(spawn.get("FirstSplashRateForLengthMin", 1)) +
                     float(spawn.get("FirstSplashRateForLengthMax", 1))) / 2
            n = int(spawn.get("SpawnNum", combo.get("TotalNum", 1)))
            for j in range(n):
                d = spacing * (first + j)
                angle = math.radians(base_angle)
                ellipses.append((d * math.sin(angle), d * math.cos(angle), pr, pr * pd))
    return ellipses


def _damage_profile(group):
    p = group.get("DamageParam", {}).get("Inside", {})
    return [{"distance": float(p[d]), "damage": float(p[v]) / 10}
            for d, v in [("DamageMaxDistance", "DamageMaxValue"),
                         ("DamageHighDistance", "DamageHighValue"),
                         ("DamageLowDistance", "DamageLowValue"),
                         ("DamageMinDistance", "DamageMinValue")]
            if d in p and v in p]


def _roller_brush(weapon_id, gp, source_path, brush):
    out = []
    roll = gp.get("WeaponRollParam", {})
    if brush:
        actions = [("挥刷", "WeaponSwingParam", "SwingUnitGroupParam", None)]
    else:
        actions = [("横甩", "WeaponWideSwingParam", "WideSwingUnitGroupParam", 21),
                   ("纵甩", "WeaponVerticalSwingParam", "VerticalSwingUnitGroupParam", 30)]
    for label, weapon_key, group_key, fixed_tail in actions:
        if weapon_key not in gp or group_key not in gp:
            continue
        assumptions = []
        weapon = gp[weapon_key]
        group = gp[group_key]
        units = group.get("Unit", [])
        inside = group.get("DamageParam", {}).get("Inside", {})
        outside = group.get("DamageParam", {}).get("Outside", {})
        damage = _num(inside, "DamageMaxValue", 0, assumptions) / 10
        startup = _num(weapon, "SwingFrame", 1, assumptions)
        if brush:
            # Octobrush's repeat period is an omitted class default.
            default_repeat = 10 if "Normal" in weapon_id else (6 if "Mini" in weapon_id else 13)
            interval = _num(roll, "SwingRepeatFrame", default_repeat, assumptions,
                            f"SwingRepeatFrame缺省，参照公开Octobrush参数采用{default_repeat}F")
            recovery = max(interval, float(weapon.get("SubWeaponSquidDelayFrm", 10)))
            assumptions.append("笔类recovery以连挥周期和已列下潜延迟的较大值做代理")
        else:
            interval = startup + fixed_tail
            recovery = fixed_tail
            assumptions.append(f"{label}完整周期取SwingFrame+{fixed_tail}F；固定尾段由公开同类周期交叉核对")
            assumptions.append("滚筒recovery采用完整周期减抬手帧的尾段代理，未声称引擎真实取消窗口")
        r = _num(inside, "DamageMinDistance", 10, assumptions)
        ellipses = _paint_unit_ellipses(units, assumptions)
        nearest = group.get("SplashNearestParam", {}).get("SpawnParam", {})
        if nearest.get("PaintWidthHalf"):
            radius = float(nearest["PaintWidthHalf"])
            offset = nearest.get("Offset", {})
            ellipses.append((float(offset.get("X", 0)), float(offset.get("Z", 0)), radius,
                             radius * float(nearest.get("PaintDepthScale", 1.0))))
        # Damage width uses actual collision radii and yaw spread, never paint
        # width.  Distinct unit paths have already been visited above.
        extents = []
        damage_range = float(inside.get("DamageMaxDistance", r))
        projectile_count = 0
        for u in units:
            if u.get("PaintOnly"):
                continue
            projectile_count += int(u.get("BulletNum", 1))
            c = u.get("UnitParam", {}).get("CollisionParam", {})
            radius = c.get("EndRadiusForPlayer", c.get("InitRadiusForPlayer", .5))
            angle = abs(float(u.get("SpawnWideDegree", 0))) + abs(float(u.get("SpawnRotateYDegree", 0)))
            extents.append(damage_range * math.sin(math.radians(angle)) + float(radius))
        width = 2 * max(extents, default=.5)
        notes = ["每挥采用DamageParam.Inside的单目标伤害曲线，不将Unit.BulletNum逐颗累加",
                 "paint_area为各Unit末端落墨椭圆及近脚墨点的并集栅格面积，非实测塗地面积",
                 "range取DamageMinDistance作为衰减末端射程代理，damage对应近距离最大伤害",
                 "width在DamageMaxDistance评估，避免用远端扇面面积搭配近身最高伤害",
                 "多墨滴群伤不是无限贯通，multi_target仅表示一次动作可覆盖多个目标"]
        out.append(_new(label, source_path, assumptions, notes,
                        damage=damage, interval=interval, startup=startup,
                        recovery=recovery, ink=_num(weapon, "InkConsume", .05, assumptions),
                        range=r, width=width, paint_area=_ellipse_union(ellipses),
                        move_speed=_num(weapon, "SwingMoveSpeed", .03, assumptions),
                        piercing=False, multi_target=True, projectiles=max(1, projectile_count),
                        damage_range=damage_range, damage_profile=_damage_profile(group),
                        outer_damage=float(outside.get("DamageMaxValue", damage * 10)) / 10,
                        damage_components=[{"path": group_key + ".DamageParam.Inside.DamageMaxValue", "damage": damage}],
                        ink_recover_stop=weapon.get("InkRecoverStop"),
                        mechanic_sources=[MECHANIC_SOURCES["brush_defaults" if brush else "roller_periods"]]))
    body = gp.get("BodyParam", {})
    if body and roll:
        assumptions = []
        paint = body.get("PaintParam", {})
        collision = body.get("CollisionParam", {})
        period = float(max(1, round(_num(body, "DamageSpanSecond", .133, assumptions) * 60)))
        assumptions.append("接触伤害秒间隔乘60后四舍五入至整数帧，避免0.133秒形成7.98帧伪精度")
        speed = _num(roll, "SpeedDash" if not brush else "SpeedNormal",
                     .168 if brush else .132, assumptions)
        ink_per_frame = _num(roll, "InkConsumeMaxPerFrame", .001, assumptions)
        damage = _num(body, "Damage", 0, assumptions) / 10
        width = 2 * _num(collision, "WidthHalf", 1.4 if not brush else .8, assumptions)
        paint_width = 2 * _num(paint, "WidthHalfMax", 2.8 if not brush else .9, assumptions)
        if brush:
            startup = _num(roll, "ToPaintFrame", 12, assumptions)
        else:
            startup = next((x["interval"] for x in out), 42)
            assumptions.append("首次进入碾压以横甩完整周期作为起手代理，已进入滚动时的接触效率另由interval表达")
        assumptions.append("滚动recovery采用8F动作取消代理，未从当前文件核定")
        out.append(_new("滚动碾压" if not brush else "推刷行进", source_path, assumptions,
                        ["滚动伤害按同一敌人接触冷却采样；连续碾压的首次命中未包含接敌移动时间",
                         "墨耗为最高速每帧消耗乘接触周期；低速省墨不据此夸大碾压DPS",
                         "滚动paint_area=涂墨宽度×速度×周期，为直线新地面条带代理"],
                        damage=damage, interval=period, startup=startup, recovery=8.0,
                        ink=ink_per_frame * period, range=_num(collision, "Radius", .4, assumptions) + 1,
                        width=width, paint_area=paint_width * speed * period,
                        move_speed=speed, piercing=True, rolling=True,
                        ink_per_frame=ink_per_frame, dash_start_frame=roll.get("DashFrame"),
                        normal_move_speed=roll.get("SpeedNormal"), paint_width=paint_width,
                        ink_recover_stop=roll.get("InkRecoverStop"),
                        sustained_contact=True, multi_target=True,
                        entry_ink=next((x["ink"] for x in out), 0.0),
                        notes_model="若单次碾压不足目标生命值，碰撞击退破坏持续接触假设，不宜用于大鲑鱼重复命中评分"))
    return out


def _slosher(weapon_id, gp, source_path):
    assumptions = []
    w = gp.get("WeaponParam", {})
    units = gp.get("UnitGroupParam", {}).get("Unit", [])
    groups = {}
    components = []
    blob = "Bathtub" in weapon_id
    for i, u in enumerate(units):
        count = int(u.get("BulletNum", 1))
        if "BulletNum" not in u:
            assumptions.append(f"Unit[{i}].BulletNum缺省，按1颗处理")
        if count <= 0:
            continue
        damage_param = u.get("DamageParam", {})
        damage = float(damage_param.get("ValueMax", 0)) / 10
        group_id = damage_param.get("GroupNum", 0)
        if blob:
            # Four separate bubbles hit independently even though GroupNum is
            # shared.  Their emission times remain explicit.
            delay = float(u.get("UnitDelayFrame", 0))
            span = float(u.get("AfterOffsetDelayFrame", 1))
            for j in range(count):
                components.append({"path": f"UnitGroupParam.Unit[{i}].DamageParam.ValueMax",
                                   "damage": damage, "delay": delay + j * span})
        else:
            previous = groups.get(group_id)
            if previous is None or damage > previous["damage"]:
                groups[group_id] = {"path": f"UnitGroupParam.Unit[{i}].DamageParam.ValueMax",
                                    "damage": damage, "delay": float(u.get("UnitDelayFrame", 0))}
    if not blob:
        components = list(groups.values())
    blast = gp.get("BlastParam", {}).get("BlastParam", {})
    distance_damage = blast.get("DistanceDamage", [])
    if distance_damage:
        near = min(distance_damage, key=lambda p: p["Distance"])
        components.append({"path": "BlastParam.BlastParam.DistanceDamage",
                           "damage": float(near["Damage"]) / 10, "delay": 0})
    damage = sum(c["damage"] for c in components)
    interval = _num(w, "RepeatFrame", 30, assumptions)
    lift = _num(w, "SwingLiftFrame", 12, assumptions)
    startup = lift + max((c["delay"] for c in components), default=0)
    recovery = _num(w, "PostDelayFrame", 10, assumptions)
    r = _num(gp.get("MainEffectiveRangeUpParam", {}), "BaseDistance", 14, assumptions)
    ellipses = _paint_unit_ellipses(units, assumptions)
    nearest = gp.get("NearestParam", {}).get("DrawSizeCollisionPaintParam", {})
    if nearest.get("PaintWidthHalf"):
        pr = float(nearest["PaintWidthHalf"])
        ellipses.append((0, 0, pr, pr * float(nearest.get("PaintDepthScale", 1))))
    if blast.get("PaintRadius"):
        radius = float(blast["PaintRadius"])
        ellipses.append((0, r, radius, radius))
    collision_widths = []
    for u in units:
        if int(u.get("BulletNum", 1)) <= 0:
            continue
        c = u.get("CollisionParam", {})
        radius = float(c.get("EndRadiusForPlayer", c.get("InitRadiusForPlayer", .4)))
        yaw = abs(float(u.get("BaseRotateYDegree", 0))) + abs(float(u.get("RandomRotateYDegree", 0)))
        collision_widths.append(2 * (radius + r * math.sin(math.radians(yaw))))
    width = max(collision_widths, default=1)
    if distance_damage:
        width = max(width, 2 * max(float(p["Distance"]) for p in distance_damage))
    assumptions.append("BaseDistance用于打工射程相对代理，不等于弹道落地或任意仰角的最大射程")
    assumptions.append("paint_area为嵌套Unit末端、按Combination索引读取的飞行落墨及脚下椭圆并集；不模拟地形与弹道")
    assumptions.append("通常Slosher按同一GroupNum只取最高伤害，Bloblobber四颗独立泡泡例外")
    notes = ["BulletNum是墨滴序列，不逐颗叠加单敌伤害；Double不同GroupNum可叠加两泼",
             "startup计到本次伤害包的最后一个有效组成，damage_components保留逐段发射偏移",
             "普通桶多墨滴分散可攻击多敌，但不等于蓄力狙式无条件贯通；分开标注multi_target",
             "浴缸四颗独立泡泡每颗60，不可将整泼240复制到每一只杂鱼"]
    record = _new("一泼直击" + ("含爆炸" if distance_damage else ""), source_path, assumptions, notes,
                  damage=damage, interval=interval, startup=startup, recovery=recovery,
                  ink=_num(w, "InkConsume", .06, assumptions), range=r, width=width,
                  paint_area=_ellipse_union(ellipses), move_speed=_num(w, "MoveSpeed", .04, assumptions),
                  piercing=("Bear" in weapon_id or "Washtub" in weapon_id),
                  multi_target=True,
                  projectiles=sum(max(0, int(u.get("BulletNum", 1))) for u in units),
                  independent_projectiles=blob,
                  projectile_damage=(components[0]["damage"] if blob and components else None),
                  damage_components=components, damage_first_frame=lift,
                  ink_recover_stop=w.get("InkRecoverStop"),
                  direct_damage=sum(c["damage"] for c in components if "BlastParam" not in c["path"]),
                  splash_damage=sum(c["damage"] for c in components if "BlastParam" in c["path"]),
                  mechanic_sources=[MECHANIC_SOURCES["slosher_mechanics"]])
    if distance_damage:
        record["aoe_damage"] = float(near["Damage"]) / 10
        record["direct_collision_width"] = max(collision_widths, default=1)
    out = [record]
    if 'Washtub' in weapon_id and record.get('direct_damage',0)>0:
        direct=dict(record)
        direct.update(name='直弹贯通',damage=record['direct_damage'],
                      width=record.get('direct_collision_width',.8),
                      damage_components=[c for c in components if 'BlastParam' not in c['path']],
                      splash_damage=0,multi_target=False,piercing=True)
        direct.pop('aoe_damage',None)
        direct['notes']=record['notes']+['直弹贯通单列125伤害通道；不把200近距直击加爆风伤害复制给通道内每个目标']
        out.append(direct)
    if distance_damage:
        extra = dict(record)
        extra.update(name="仅爆风", damage=float(near["Damage"]) / 10,
                     width=2 * max(float(p["Distance"]) for p in distance_damage),
                     damage_components=[components[-1]], direct_damage=0,
                     splash_damage=float(near["Damage"]) / 10)
        out.append(extra)
    if "Launcher" in weapon_id or "Bear" in weapon_id:
        swirl_damage = min((float(u.get("DamageParam", {}).get("ValueMax", 0)) / 10
                            for u in units if int(u.get("BulletNum", 1)) > 0), default=damage)
        extra = dict(record)
        extra.update(name="旋涡擦伤", damage=swirl_damage, piercing=True,
                     damage_components=[{"path": "UnitGroupParam.Unit[1].DamageParam.ValueMax", "damage": swirl_damage}],
                     notes=record["notes"] + ["旋涡只用独立列出的擦伤伤害，不能让主弹直击伤害无条件贯通"])
        out.append(extra)
    return out


def _shelter(weapon_id, gp, source_path):
    assumptions = []
    w = gp.get("spl__WeaponShelterShotgunParam", {})
    b = gp.get("spl__BulletShelterShotgunParam", {})
    groups = b.get("GroupParams", [])
    total = 0
    pellet_components = []
    for i, group in enumerate(groups):
        count = _num(group, "TotalNum", 1, assumptions)
        dmg = _num(group.get("DamageParam", {}), "ValueMax", 0, assumptions) / 10
        total += count * dmg
        pellet_components.append({"path": f"spl__BulletShelterShotgunParam.GroupParams[{i}]",
                                  "count": count, "damage_per_pellet": dmg})
    cap = _num(b, "DamageEffectiveTotalMax", total * 10, assumptions) / 10
    damage = min(total, cap)
    repeat = float(w.get("RepeatFrame", 0))
    if repeat <= 0:
        # These values are omitted class defaults.  PostDelayFrame_Main is the
        # post-shot wait; add the next humanoid startup for repeat firing.
        startup = _num(w, "PreDelayFrame_HumanMain", 8, assumptions,
                       "PreDelayFrame_HumanMain缺省，参照Splat Brella公开参数取8F")
        recovery = _num(w, "PostDelayFrame_Main", 22, assumptions,
                        "PostDelayFrame_Main缺省取22F，使普通伞完整周期为30F；取消下潜窗口另列")
        interval = startup + recovery
    else:
        interval = repeat
        startup = _num(w, "PreDelayFrame_HumanMain", 8, assumptions,
                       "自动连射伞未列起手帧，按8F作起手代理")
        recovery = min(interval, 20)
        assumptions.append("自动连射伞recovery以min(完整周期,20F)做代理，未核定精确取消窗口")
    # End of straight travel plus the geometric series in braking state.
    # This is stable, transparent and uses the center pellet (not random max).
    center = groups[0] if groups else {}
    m = center.get("MoveParam", {})
    speed = _num(m, "SpawnSpeed", 2.6, assumptions)
    straight = _num(m, "GoStraightToBrakeStateFrame", 3, assumptions)
    brake_speed = _num(m, "GoStraightStateEndMaxSpeed", speed, assumptions)
    resist = _num(m, "BrakeAirResist", .36, assumptions)
    r = speed * straight + brake_speed * (1 - resist) / max(resist, .05)
    widths = []
    ellipses = []
    for i, g in enumerate(groups):
        count = int(g.get("TotalNum", 1))
        c = g.get("CollisionParam", {})
        radius = float(c.get("EndRadiusForPlayer", c.get("InitRadiusForPlayer", .2)))
        angle = abs(float(g.get("HorizontalDegree", 0)))
        widths.append(2 * (r * math.tan(math.radians(angle)) + radius))
        p = g.get("PaintParam", {})
        paint_radius = float(p.get("WidthHalfNear", p.get("WidthHalfFar", 1)))
        for j in range(count):
            a = (-1 + 2 * j / (count - 1)) * angle if count > 1 else 0
            ellipses.append((r * math.tan(math.radians(a)), r, paint_radius, paint_radius * 1.6))
    splash = b.get("SplashParam", {})
    if splash.get("SplashPaintWidthFullActive"):
        radius = float(splash["SplashPaintWidthFullActive"])
        n = int(splash.get("CreateSplashNum", 6))
        depth = float(splash.get("SplashPaintDepthScaleFullActive", 2.1))
        for j in range(n):
            ellipses.append((0, r * (j + 1) / (n + 1), radius, radius * depth))
    canopy = gp.get("spl__BulletShelterCanopyParam", {})
    canopy_w = gp.get("spl__WeaponShelterCanopyParam", {})
    assumptions.append("射程为中心弹直行距离加制动段几何级数，未计自由落体末段与仰角")
    assumptions.append("涂墨为落点散布及沿中心线墨滴椭圆并集，椭圆深度参数缺省取1.6")
    return [_new("散弹近距上限", source_path, assumptions,
                 ["单目标damage=min(各Group弹数×单弹伤害之和,DamageEffectiveTotalMax)，不会将11颗散弹全算给单敌",
                  "熊伞IsAlwaysNaked=true，不能因文件残留Canopy数据赋予护盾收益",
                  "墨耗采用打工文件，未使用公开页面中的PVP墨耗"],
                 damage=damage, interval=interval, startup=startup, recovery=recovery,
                 ink=_num(w, "InkConsume", .03, assumptions), range=r,
                 width=max(widths, default=1), paint_area=_ellipse_union(ellipses),
                 move_speed=_num(w, "MoveSpeed", .065, assumptions), piercing=False,
                 damage_cap=cap, total_pellet_damage=total, pellet_components=pellet_components,
                 canopy_available=not canopy_w.get("IsAlwaysNaked", False),
                 canopy_contact_damage=(float(canopy["CanopyDamage"]) / 10 if "CanopyDamage" in canopy else None),
                 canopy_ink_per_second=canopy_w.get("InkConsumeUmbrella"),
                 canopy_open_frame=canopy_w.get("CanopyOpenFrame"),
                 ink_recover_stop=w.get("InkRecoverStop"),
                 mechanic_sources=[MECHANIC_SOURCES["shelter_defaults"]])]


def _saber(weapon_id, gp, source_path):
    w = gp.get("spl__WeaponSaberParam", {})
    swing = w.get("SwingParam", {})
    charge = w.get("ChargeParam", {})
    bear = "Bear" in weapon_id
    out = []
    for charged in (False, True):
        assumptions = []
        orientation = "Vertical" if charged else "Horizontal"
        slash = gp.get("BulletSaberSlash" + orientation + "Param", {})
        bullet = gp.get("BulletSaber" + orientation + "Param", {})
        s = slash.get("ShapeParam", {})
        prefix = "ChargeSwing" if charged else "WeakSwing"
        charge_f = _num(charge, "ChargeFrameFullCharge", 20, assumptions) if charged else 0
        swing_f = _num(swing, prefix + "Frame", 22 if charged else 26, assumptions)
        slash_f = _num(swing, prefix + "ShotSlashFrame", 3 if charged else 6, assumptions)
        bullet_f = _num(swing, prefix + "ShotBulletFrame", 6 if charged else 9, assumptions)
        post = _num(swing, prefix + "PostDelayFrame", 14 if charged else 22, assumptions)
        interval = charge_f + swing_f
        ink = _num(charge if charged else swing, "InkConsumeFullCharge" if charged else "InkConsume", .06 if charged else .025, assumptions)
        move = _num(swing, "ChargeMoveVelLimit" if charged else "WeakSwingMoveVelLimit", .06, assumptions)
        melee_damage = _num(slash.get("DamageParam", {}), "DamageValue", 0, assumptions) / 10
        ranged_damage = _num(bullet.get("DamageParam", {}), "HitDamage", 0, assumptions) / 10
        # Bounding-box + capsule forward/lateral reach.  Spawn offsets are
        # explicit when available; absent offsets are not silently invented.
        box = s.get("BoxHalfExtents", {})
        box_c = s.get("BoxCenter", {})
        melee_range = float(box_c.get("Z", 0)) + float(box.get("Z", 1))
        melee_width = 2 * float(box.get("X", 1))
        if s.get("HasCylinderShape"):
            cr = _num(s, "CylinderRadius", 1.4, assumptions)
            ca, cb = s.get("CylinderCenterA", {}), s.get("CylinderCenterB", {})
            melee_range = max(melee_range, max(float(ca.get("Z", 0)), float(cb.get("Z", 0))) + cr)
            melee_width = max(melee_width, abs(float(ca.get("X", 0)) - float(cb.get("X", 0))) + 2 * cr)
        offset_key = "ShotSlashOffset_Vertical" if charged else "ShotSlashOffset_L"
        offset = swing.get(offset_key, {})
        if "Z" in offset:
            melee_range += float(offset["Z"])
        else:
            assumptions.append("近战发射偏移缺省，range仅取已列判定形状前端，不补入未知偏移")
        assumptions.append("近战range由形状包围盒或胶囊前端加已列发射偏移构造，为几何可达代理")
        # Normal splatanas can connect both blade and beam on close targets.
        # Grizzco is explicitly melee-only despite retained beam parameters.
        components = [{"damage": melee_damage, "delay": slash_f,
                       "path": "BulletSaberSlash" + orientation + "Param.DamageParam.DamageValue"}]
        if not bear:
            components.append({"damage": ranged_damage, "delay": bullet_f,
                               "path": "BulletSaber" + orientation + "Param.DamageParam.HitDamage"})
        else:
            assumptions.append("熊刀无远程刀波；残留BulletSaber参数不作为远程伤害或远程射程")
        base_notes = ["recovery是命中后至PostDelayFrame下潜时刻的剩余帧，避免把命中偏移重复相加",
                      "近战加刀波仅在两者均命中的近距离理想条件成立；远程模式单独列出"]
        # Minimal local ink footprint for melee only.  Normal ranged modes
        # below receive the beam's line of splash union.
        foot = w.get("FootSplashPaintParam", {})
        radius = float(foot.get("WidthHalfNearest", foot.get("WidthHalf", 2)))
        footprint = _ellipse_union([(0, melee_range / 2, radius, radius * float(foot.get("DepthScaleMax", 1)))])
        out.append(_new(("蓄力" if charged else "横斩") + "近战" + ("加刀波" if not bear else ""), source_path,
                        assumptions, base_notes,
                        damage=sum(c["damage"] for c in components), interval=interval,
                        startup=charge_f + max(c["delay"] for c in components),
                        recovery=max(0, post - max(c["delay"] for c in components)),
                        ink=ink, range=melee_range, width=melee_width,
                        paint_area=footprint, move_speed=move, piercing=True,
                        charged=charged, melee=True, charge_frames=charge_f,
                        damage_first_frame=charge_f, damage_components=components,
                        cancel_frame=post, ink_recover_stop=swing.get("InkRecoverStop_ChargeSwing" if charged else "InkRecoverStop"),
                        lunge_distance=swing.get("SideStepParam", {}).get("MoveDist"),
                        mechanic_sources=[MECHANIC_SOURCES["bear_saber"]] if bear else []))
        if bear:
            continue
        assumptions = []
        m = bullet.get("MoveParam", {})
        r = _num(m, "SpawnSpeed", 1, assumptions) * _num(m, "GoStraightToBrakeStateFrame", 10, assumptions)
        b_offset = swing.get("ShotBulletOffset_Vertical" if charged else "ShotBulletOffset_L", {})
        r += float(b_offset.get("Z", 0))
        collision = bullet.get("CollisionParam", {})
        offsets = collision.get("OffsetArray", [])
        radii = collision.get("ParamArray", [])
        radius = max((float(c.get("EndRadiusForPlayer", c.get("InitRadiusForPlayer", .3))) for c in radii), default=.3)
        width = (max((float(x.get("X", 0)) for x in offsets), default=0)
                 - min((float(x.get("X", 0)) for x in offsets), default=0) + 2 * radius)
        splash = bullet.get("SplashSpawnParam", {})
        n = int(splash.get("SplashNumMax", 1))
        spacing = float(splash.get("DropInterval", r / max(n, 1)))
        p = bullet.get("SplashPaintParam", bullet.get("PaintParam", {}))
        pr = float(p.get("WidthHalf", p.get("WidthHalfNearest", 1.8)))
        ellipses = [(0, min((j + 1) * spacing, r), pr, pr * 1.3) for j in range(n)]
        assumptions.extend(["刀波射程取发射速度×直行帧+已列枪口偏移，未模拟下坠尾段",
                            "刀波涂墨以DropInterval与SplashNumMax定位墨滴椭圆，重合部分取并集，深度比例缺省取1.3"])
        out.append(_new(("蓄力" if charged else "横斩") + "刀波", source_path, assumptions,
                        ["仅计远程刀波伤害，不加入近战判定；与近战模式共享墨耗和挥动周期"],
                        damage=ranged_damage, interval=interval, startup=charge_f + bullet_f,
                        recovery=max(0, post - bullet_f), ink=ink, range=r,
                        width=width, paint_area=_ellipse_union(ellipses),
                        move_speed=move, piercing=True, charged=charged, melee=False,
                        charge_frames=charge_f, damage_components=[components[-1]],
                        damage_first_frame=charge_f, cancel_frame=post,
                        ink_recover_stop=swing.get("InkRecoverStop_ChargeSwing" if charged else "InkRecoverStop")))
    return out


def extract(weapon_id, gp, source_path):
    """Return explicitly parameterized action modes, or [] for other classes."""
    if "GameParameters" in gp:
        gp = gp["GameParameters"]
    kind = weapon_id.split("_", 1)[0]
    if kind in {"Roller", "Brush"}:
        return _roller_brush(weapon_id, gp, source_path, kind == "Brush")
    if kind == "Slosher":
        return _slosher(weapon_id, gp, source_path)
    if kind == "Shelter":
        return _shelter(weapon_id, gp, source_path)
    if kind == "Saber":
        return _saber(weapon_id, gp, source_path)
    return []
