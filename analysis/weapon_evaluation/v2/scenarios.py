"""Explicit target scenarios using the already audited action modes.

No files are written on import.  Public functions:
    sequence_time(modes, hp, **resource_options)
    boss_benchmark(modes, **resource_options)
    mob_benchmark(modes, density=.04, **resource_options)
    paint_task(mode, area, area_per_action, **resource_options)

The optimizer enumerates FIXED modes, not arbitrary cost-free mode switching.
Damage events, burst gaps, charge batches and ink refills are scheduled.  Mob
aiming uses deterministic greedy useful-damage selection in a declared geometry;
it is a reproducible feasible proxy plan, not a proof of global optimal aiming.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path


BOSS_CASES = (
    ("300血目标", [300.0]),
    ("500血目标", [500.0]),
    ("600盾与500本体", [600.0, 500.0]),
    ("900血目标", [900.0]),
    ("1200血目标", [1200.0]),
)
MOB_HP = (400.0, 400.0, 100.0, 100.0, 100.0, 40.0, 40.0, 40.0)
EPS = 1e-9


def load_modes(path=None):
    """Read an old evaluation export, returning {weapon_id: action_modes}."""
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "evaluation.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {w["id"]: copy.deepcopy(w["modes"]) for w in data["weapons"]}


def nth_frame(mode, n):
    """Nominal last damage/release frame of action n, before resource stalls."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if "batch_size" in mode:
        size = int(mode["batch_size"])
        batch, slot = divmod(n - 1, size)
        cycle = (float(mode.get("batch_charge", mode["startup"]))
                 + (size - 1) * float(mode["interval"])
                 + float(mode.get("batch_recovery", mode["recovery"])))
        return float(mode["startup"]) + batch * cycle + slot * float(mode["interval"])
    if "burst_size" in mode:
        size = int(mode["burst_size"])
        burst, slot = divmod(n - 1, size)
        return (float(mode["startup"])
                + burst * ((size - 1) * float(mode["interval"]) + float(mode["burst_gap"]))
                + slot * float(mode["interval"]))
    return float(mode["startup"]) + (n - 1) * float(mode["interval"])


def _events(mode):
    components = mode.get("damage_components", [])
    if (components and "damage_first_frame" in mode
            and all(isinstance(c.get("damage"), (int, float)) for c in components)):
        return sorted([{
            "offset": float(mode["damage_first_frame"]) + float(c.get("delay", 0)),
            "damage": float(c["damage"]), "component": c.get("path", "分段伤害"),
        } for c in components if c["damage"] > 0], key=lambda e: e["offset"])
    return [{"offset": float(mode["startup"]), "damage": float(mode["damage"]),
             "component": "动作总伤害包"}]


class _Schedule:
    """Mode-local schedule with paid entry, whole charge batches and refills."""

    def __init__(self, mode, tank=1.0, refill_frames=180.0, allow_refill=True,
                 initial_ink=None, initial_refill_lock_frames=0.0):
        self.mode = mode
        self.tank = float(tank)
        self.entry = float(mode.get("entry_ink", 0))
        self.initial_ink = self.tank if initial_ink is None else float(initial_ink)
        if not -EPS <= self.initial_ink <= self.tank + EPS:
            raise ValueError("initial_ink must lie within tank capacity")
        self.available = max(0.0, self.initial_ink)
        self.initial_refill_lock = max(0.0, float(initial_refill_lock_frames))
        self.entry_paid = False
        self.refill_frames = float(refill_frames)
        self.allow_refill = allow_refill
        self.delay = 0.0
        self.last_impact = 0.0
        self.ink_spent = 0.0
        self.refills = []
        self.paid_batches = 0
        self.events = _events(mode)
        self.reason = None
        if self.entry > self.tank + EPS:
            self.reason = "入场墨耗超过墨箱容量"

    def action(self, n):
        if self.reason:
            return None
        mode = self.mode
        if "batch_size" in mode:
            size = int(mode["batch_size"])
            first_in_batch = (n - 1) % size == 0
            cost = float(mode["ink"]) * size if first_in_batch else 0.0
        else:
            first_in_batch = False
            cost = float(mode["ink"])
        if cost + self.entry > self.tank + EPS:
            self.reason = "单次动作或整批蓄力墨耗超过可用整箱"
            return None
        base = nth_frame(mode, n) - float(mode["startup"])
        first_offset = self.events[0]["offset"]
        nominal_first = base + first_offset
        entry_cost = self.entry if not self.entry_paid else 0.0
        if cost + entry_cost > self.available + EPS:
            if not self.allow_refill:
                self.reason = "整箱墨不足且未允许补墨"
                return None
            if n == 1:
                stop = self.initial_refill_lock
            else:
                stop = mode.get("ink_recover_stop")
                stop = float(stop if isinstance(stop, (int, float)) else mode["recovery"])
                stop = max(stop, float(mode["recovery"]))
            begin = self.last_impact + stop
            end = begin + self.refill_frames
            # The new action/charge/roll entry starts only after refilling.
            # Its first damage event still pays the full initial offset.
            self.delay = max(self.delay, end + first_offset - nominal_first)
            self.refills.append({"start_frame": begin, "end_frame": end,
                                 "before_action": n, "remaining_ink": max(0, self.available)})
            self.available = self.tank
            entry_cost = self.entry
        self.available -= cost + entry_cost
        self.ink_spent += cost + entry_cost
        self.entry_paid = True
        if first_in_batch:
            self.paid_batches += 1
        return [{**event, "frame": base + event["offset"] + self.delay,
                 "action": n} for event in self.events]

    def exported(self):
        return {"ink_spent": round(self.ink_spent, 8),
                "remaining_ink": round(max(0, self.available), 8),
                "initial_ink": self.initial_ink, "tank_capacity": self.tank,
                "refills": self.refills, "paid_charge_batches": self.paid_batches,
                "resource_policy": "整批预付墨耗，补墨期间停止输出，重新进入动作不免起手"}


def _resource_assumptions(refill_frames):
    return [
        "独立基准默认从满墨且未预蓄力开始；顺序调用可显式传入initial_ink，不在不同模式之间免费借用状态",
        "每个目标只允许完整模式参数，未插值构造没有解包依据的半蓄力",
        "补墨以整箱模型处理，忽略未用墨水对整箱恢复时长的缩短",
        f"整箱恢复时长设为{float(refill_frames):g}F，可由调用者覆盖；该值是情景假设而非武器参数事实",
        "补墨前等待已列ink_recover_stop与recovery的较大值；缺省时用recovery做代理",
        "不计接敌路程、瞄准转向、飞行距离、无敌窗口和真实盾体切换动画",
        "这些血量只定义生命值靶，不等于真实大鲑鱼露出弱点、绕后或解除装甲的交战时间",
        "报告帧数等于最终伤害事件的零基帧加1，保证零起手攻击仍计1帧",
    ]


def _fixed_target(mode, phases, *, tank, refill_frames, allow_refill, max_actions,
                  initial_ink=None, initial_refill_lock_frames=0.0):
    if mode.get("sustained_contact") and float(mode["damage"]) + EPS < max(phases):
        return {"feasible": False, "mode": mode["name"],
                "reason": "单次接触不能击杀最高血量阶段，击退使连续接触假设失效"}
    scheduler = _Schedule(mode, tank=tank, refill_frames=refill_frames, allow_refill=allow_refill,
                          initial_ink=initial_ink, initial_refill_lock_frames=initial_refill_lock_frames)
    remaining = list(phases)
    stage = 0
    trace = []
    stage_frames = []
    overkill = 0.0
    for n in range(1, max_actions + 1):
        events = scheduler.action(n)
        if events is None:
            return {"feasible": False, "mode": mode["name"], "reason": scheduler.reason,
                    **scheduler.exported()}
        for event in events:
            damage = event["damage"]
            before = remaining[stage]
            applied = min(before, damage)
            remaining[stage] = max(0.0, before - damage)
            overkill += max(0.0, damage - before)
            scheduler.last_impact = event["frame"]
            trace.append({"action": n, "frame": event["frame"], "phase": stage + 1,
                          "damage": damage, "applied_damage": applied,
                          "remaining_hp": remaining[stage], "component": event["component"]})
            if remaining[stage] <= EPS:
                stage_frames.append(event["frame"] + 1)
                stage += 1
                if stage == len(phases):
                    return {"feasible": True, "mode": mode["name"],
                            "frames": event["frame"] + 1, "actions": n,
                            "terminal_action_last_event_frame": max(e["frame"] for e in events),
                            "phase_completion_frames": stage_frames,
                            "overkill_discarded": overkill, "plan": trace,
                            **scheduler.exported()}
                # This packet's excess is discarded.  Only the next independent
                # event may damage the next shield/body phase.
    return {"feasible": False, "mode": mode["name"], "reason": "超出动作次数上限"}


def sequence_time(modes, hp, *, tank=1.0, refill_frames=180.0,
                  allow_refill=True, max_actions=10000, initial_ink=None,
                  initial_refill_lock_frames=0.0):
    """Fastest complete fixed-mode plan for one HP target or HP phase list.

    hp=[600,500] enforces a non-carrying shield/body boundary.  This is an exact
    minimum over the supplied fixed modes and their event schedules; it does not
    claim the optimum of arbitrary cross-mode combos.
    """
    phases = [float(hp)] if isinstance(hp, (int, float)) else [float(x) for x in hp]
    if not phases or any(not math.isfinite(h) or h <= 0 for h in phases):
        raise ValueError("hp must contain positive finite health values")
    alternatives = []
    for i, mode in enumerate(modes):
        result = _fixed_target(mode, phases, tank=tank, refill_frames=refill_frames,
                               allow_refill=allow_refill, max_actions=max_actions,
                               initial_ink=initial_ink, initial_refill_lock_frames=initial_refill_lock_frames)
        result["mode_index"] = i
        alternatives.append(result)
    valid = [p for p in alternatives if p["feasible"]]
    if not valid:
        return {"feasible": False, "frames": None, "phases": phases,
                "alternatives": alternatives, "reason": "没有可完成的固定模式"}
    best = min(valid, key=lambda p: (p["frames"], p["ink_spent"], p["mode_index"]))
    return {**best, "phases": phases, "plans": [best],
            "alternatives": alternatives,
            "optimization": "完整固定模式枚举的最短完成帧，不进行跨模式混合",
            "assumptions": _resource_assumptions(refill_frames) + [
                f"本次初始墨量为{float(tank if initial_ink is None else initial_ink):g}，墨箱容量为{float(tank):g}",
                "盾体过杀不结转；同一动作中后续独立伤害事件可进入下一阶段，不额外虚构阶段无敌时间"]}


def paint_task(mode, area, area_per_action, *, tank=1.0, refill_frames=180.0,
               allow_refill=True, max_actions=10000, initial_ink=None,
               initial_refill_lock_frames=0.0):
    """Complete a finite painting quota using whole, resource-paid actions.

    area_per_action must already contain the caller's overlap/surface correction.
    It is an area proxy, not a claim that projectile release equals observed
    surface ink arrival.  The last known action event is the timing reference.
    """
    area = float(area)
    area_per_action = float(area_per_action)
    if not math.isfinite(area) or area < 0:
        raise ValueError("area must be finite and non-negative")
    if not math.isfinite(area_per_action) or area_per_action <= 0:
        raise ValueError("area_per_action must be positive and finite")
    if area <= EPS:
        return {"feasible": True, "mode": mode["name"], "frames": 0.0,
                "actions": 0, "area": area, "area_per_action": area_per_action,
                "covered_area": 0.0, "ink_spent": 0.0,
                "remaining_ink": float(tank if initial_ink is None else initial_ink),
                "refills": [], "paid_charge_batches": 0, "plan": []}
    actions = int(math.ceil((area - EPS) / area_per_action))
    if actions > max_actions:
        return {"feasible": False, "mode": mode["name"], "frames": None,
                "reason": "涂墨配额超出动作次数上限", "required_actions": actions}
    scheduler = _Schedule(mode, tank=tank, refill_frames=refill_frames,
                          allow_refill=allow_refill, initial_ink=initial_ink,
                          initial_refill_lock_frames=initial_refill_lock_frames)
    trace = []
    frame = 0.0
    for n in range(1, actions + 1):
        events = scheduler.action(n)
        if events is None:
            return {"feasible": False, "mode": mode["name"], "frames": None,
                    "reason": scheduler.reason, "actions": n - 1,
                    "area": area, "area_per_action": area_per_action,
                    "plan": trace, **scheduler.exported()}
        frame = max(event["frame"] for event in events)
        scheduler.last_impact = frame
        trace.append({"action": n, "frame": frame,
                      "covered_area": n * area_per_action,
                      "remaining_area": max(0.0, area - n * area_per_action)})
    return {"feasible": True, "mode": mode["name"], "frames": frame + 1,
            "terminal_action_last_event_frame": frame,
            "actions": actions, "area": area, "area_per_action": area_per_action,
            "covered_area": actions * area_per_action,
            "excess_area": actions * area_per_action - area,
            "plan": trace, **scheduler.exported(),
            "assumptions": _resource_assumptions(refill_frames) + [
                "面积按完整动作逐次累计；面积输入须已含调用者规定的重叠和墙面修正",
                "以最后一个已知动作事件计完成，不把未知弹道到墙面或落地时延伪装成实测",
                "整批动作即使只用其中一发完成配额，也预付整批墨耗并计入起手蓄力"]}


def boss_benchmark(modes, **resource_options):
    cases = []
    for name, phases in BOSS_CASES:
        result = sequence_time(modes, phases, **resource_options)
        cases.append({"name": name, **result})
    valid = all(case["feasible"] for case in cases)
    return {"feasible": valid,
            "frames": sum(case["frames"] for case in cases) if valid else None,
            "cases": cases, "plans": [case.get("plans", []) for case in cases],
            "definition": "300、500、600盾加500本体、900、1200血五项独立冷启动完成帧之和",
            "orientation": "越低越快", "cross_mode_switching": False}


def _positions(density, layout):
    if density <= 0 or not math.isfinite(density):
        raise ValueError("density must be positive and finite")
    if layout == "clustered":
        # Same point is a clustering sensitivity limit, not a claim that solid
        # salmonids can occupy identical world positions or a guaranteed bound
        # for every spread-shot pattern.
        return [(0.0, 0.0)] * len(MOB_HP)
    if layout == "dispersed":
        # A control with no shared attack footprint.  Approach travel remains
        # excluded consistently with the other benchmark arrangements.
        return [(float(i) * 1000.0, 0.0) for i in range(len(MOB_HP))]
    spacing = 1 / math.sqrt(density)
    return [(float(i % 2) * spacing, float(i // 2) * spacing) for i in range(len(MOB_HP))]


def _packet(mode, hp, positions, aim, layout):
    """Return a target-wise action packet in a declared 2D coverage proxy."""
    n = len(hp)
    damage = [0.0] * n
    if layout == "dispersed":
        damage[aim] = float(mode["damage"])
        return damage
    ax, ay = positions[aim]
    width = max(.01, float(mode.get("width", .4)))
    def circle(radius, cx=ax, cy=ay):
        return [i for i, (x, y) in enumerate(positions)
                if hp[i] > EPS and (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2 + EPS]
    def lane(lane_width):
        return [i for i, (x, y) in enumerate(positions) if hp[i] > EPS
                and abs(x - ax) <= lane_width / 2 + EPS
                and -EPS <= y - ay <= float(mode.get("range", 0)) + EPS]
    if mode.get("aoe_projectiles"):
        count = int(mode["aoe_projectiles"])
        radius = float(mode["aoe_radius"])
        # Every explosion retains its own center, allowing both overlap damage
        # and actual overlap loss in coverage in the *same* arrangement.
        for j in range(count):
            cx = ax + ((j / (count - 1)) - .5) * width if count > 1 else ax
            for i in circle(radius, cx, ay):
                damage[i] += float(mode["aoe_damage"])
    elif mode.get("independent_projectiles"):
        count = int(mode.get("projectiles", 1))
        pd = float(mode.get("projectile_damage", mode["damage"] / count))
        candidates = circle(width / 2)
        # This is the declared ideal projectile-allocation bound; no random
        # hit-rate fraction is silently substituted for discrete arrows.
        for _ in range(count):
            targets = [i for i in candidates if hp[i] - damage[i] > EPS]
            if not targets:
                break
            i = max(targets, key=lambda j: (min(pd, hp[j] - damage[j]), hp[j] - damage[j], -j))
            damage[i] += pd
    elif "aoe_damage" in mode:
        for i in circle(width / 2):
            damage[i] = float(mode["aoe_damage"])
        if "direct_damage" in mode:
            # Explosher: distinct piercing core plus floor blast.  The core
            # follows a lane; the blast stays at the aimed endpoint.
            core = float(mode["direct_damage"])
            for i in lane(float(mode.get("direct_collision_width", .8))):
                damage[i] += core
        else:
            # Blaster direct and blast are alternatives for the center enemy.
            damage[aim] = max(damage[aim], float(mode["damage"]))
    elif mode.get("piercing"):
        for i in lane(width):
            damage[i] = float(mode["damage"])
    elif mode.get("multi_target") or width > 1.5:
        candidates = circle(width / 2)
        cap = int(mode.get("projectiles", n))
        candidates.sort(key=lambda i: (min(float(mode["damage"]), hp[i]), -i), reverse=True)
        for i in candidates[:cap]:
            damage[i] = float(mode["damage"])
    else:
        damage[aim] = float(mode["damage"])
    return damage


def _fixed_mob(mode, density, layout, *, tank, refill_frames, allow_refill, max_actions,
               initial_ink=None, initial_refill_lock_frames=0.0):
    if mode.get("sustained_contact") and float(mode["damage"]) + EPS < max(MOB_HP):
        return {"feasible": False, "mode": mode["name"], "reason": "碾压不能单次击杀大鲑鱼，连续接触不成立"}
    hp = list(MOB_HP)
    positions = _positions(density, layout)
    scheduler = _Schedule(mode, tank=tank, refill_frames=refill_frames, allow_refill=allow_refill,
                          initial_ink=initial_ink, initial_refill_lock_frames=initial_refill_lock_frames)
    trace = []
    for n in range(1, max_actions + 1):
        options = []
        for aim in range(len(hp)):
            if hp[aim] <= EPS:
                continue
            packet = _packet(mode, hp, positions, aim, layout)
            useful = sum(min(h, d) for h, d in zip(hp, packet))
            kills = sum(h > EPS and d + EPS >= h for h, d in zip(hp, packet))
            options.append((useful, kills, -aim, packet))
        if not options:
            break
        _, _, negative_aim, packet = max(options, key=lambda o: o[:3])
        if not any(d > EPS for d in packet):
            return {"feasible": False, "mode": mode["name"], "reason": "队形内不存在有效伤害模板"}
        events = scheduler.action(n)
        if events is None:
            return {"feasible": False, "mode": mode["name"], "reason": scheduler.reason,
                    **scheduler.exported()}
        # Mob AoE coverage is evaluated at an action's last event.  Sub-event
        # target masks are unavailable for all classes, so no spurious exact
        # first-subhit clear time is claimed here.
        frame = max(event["frame"] for event in events)
        scheduler.last_impact = frame
        useful = [min(h, d) for h, d in zip(hp, packet)]
        hp = [max(0.0, h - d) for h, d in zip(hp, packet)]
        trace.append({"action": n, "frame": frame, "aim_target": -negative_aim,
                      "damage_packet": packet, "applied_damage": useful,
                      "remaining_hp": list(hp)})
        if all(h <= EPS for h in hp):
            return {"feasible": True, "mode": mode["name"], "frames": frame + 1,
                    "terminal_action_last_event_frame": frame,
                    "actions": n, "plan": trace, "positions": positions,
                    "initial_hp": list(MOB_HP), **scheduler.exported()}
    return {"feasible": False, "mode": mode["name"], "reason": "超出动作次数上限"}


def mob_benchmark(modes, density=.04, *, tank=1.0, refill_frames=180.0,
                  allow_refill=True, max_actions=10000, initial_ink=None,
                  initial_refill_lock_frames=0.0):
    """Eight-target mixed-group completion under three explicit arrangements.

    density controls the 2x4 grid spacing (1/sqrt(density)).  No source image
    supplies a formation, so the central grid and both limiting arrangements
    are assumptions, not observed enemy placements.
    """
    layouts = {}
    for layout in ("grid", "dispersed", "clustered"):
        alternatives = []
        for i, mode in enumerate(modes):
            result = _fixed_mob(mode, float(density), layout, tank=tank,
                                refill_frames=refill_frames, allow_refill=allow_refill,
                                max_actions=max_actions, initial_ink=initial_ink,
                                initial_refill_lock_frames=initial_refill_lock_frames)
            result["mode_index"] = i
            alternatives.append(result)
        valid = [p for p in alternatives if p["feasible"]]
        best = min(valid, key=lambda p: (p["frames"], p["ink_spent"], p["mode_index"])) if valid else None
        layouts[layout] = {"feasible": bool(valid), "frames": best["frames"] if best else None,
                           "plan": best, "alternatives": alternatives}
    central = layouts["grid"]
    return {"feasible": central["feasible"], "frames": central["frames"],
            "plans": [central["plan"]] if central["plan"] else [],
            "layouts": layouts, "density": float(density),
            "spacing": 1 / math.sqrt(float(density)),
            "definition": "2只400血、3只100血、3只40血全部清除的完成帧",
            "optimization": "逐模式枚举；每次选择即时有效伤害最大的瞄准模板，非全局瞄准最优证明",
            "assumptions": _resource_assumptions(refill_frames) + [
                "中央情景为2列4行规则点阵；序列按400、400、100、100、100、40、40、40逐行放置",
                "分散情景每次攻击只影响一个敌人；聚集情景使用同点极限，不声称真实敌人可重合或该情景对所有弹道都最快",
                "独立箭采用扇宽覆盖内的理想离散分配；滞留爆炸逐个爆心计算重叠伤害，不重复虚构额外敌人",
                "贯通为朝点阵纵轴的矩形攻击模板；普通群攻为宽度对应的圆形模板，均是几何代理",
                "全部敌人视为已经可瞄准；只对贯通长度应用range，不加入走位接敌时间",
                "Mob每次动作计到最后一个分段伤害事件；未逐武器推断未知的群体分段碰撞",
            ]}
