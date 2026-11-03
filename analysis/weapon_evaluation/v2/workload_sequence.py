"""A sequential workload with one shared ink tank and mode-specific exits.

Blocks declare complete fixed modes.  The engine carries remaining ink between
blocks, reserves whole charge batches, serializes refill stalls, and pays the
actual selected mode's exit window.  There is no ceil(total_ink) shortcut and no
global fastest-Endlag borrowing.  No files are written by this module.
"""

from __future__ import annotations

from copy import deepcopy
import math

try:
    from .scenarios import (_Schedule, _fixed_target, _fixed_mob, paint_task,
                            nth_frame, _events)
except ImportError:
    from scenarios import (_Schedule, _fixed_target, _fixed_mob, paint_task,
                           nth_frame, _events)

EPS = 1e-9


def _mode_exit(mode, first_release, final_release):
    evidence = mode.get("release_to_swim_evidence", {})
    value = mode.get("release_to_swim_frames")
    missing = not isinstance(value, (int, float)) or not math.isfinite(value)
    proxy = missing or "推测假设" in str(evidence.get("classification", ""))
    if missing:
        value = max(0.0, float(mode.get("recovery", 0)))
        classification = "推测假设 使用该动作已归一到命中或射出后的recovery代理"
        if mode.get("melee") and evidence.get("attack_event_to_swim_proxy_frames") is not None:
            classification = "推测假设 无子弹近战以动作事件后recovery代替射出至潜墨"
    else:
        value = max(0.0, float(value))
        classification = evidence.get("classification", "已有模式退出参数")
    initial_lock = evidence.get("initial_post_roll_remaining_lock_proxy_frames")
    remaining_lock = None
    if isinstance(initial_lock, (int, float)):
        elapsed = max(0.0, final_release - first_release)
        remaining_lock = max(0.0, float(initial_lock) - elapsed)
        value = max(value, remaining_lock)
    return {"frames": value, "mode": mode["name"], "proxy": proxy,
            "classification": classification,
            "source": evidence,
            "initial_post_roll_lock_frames": initial_lock,
            "post_roll_lock_remaining_at_exit": remaining_lock,
            "origin": "最后已知动作发射或伤害事件，等待剩余自动连发后计退出"}


def _seed_plan(block, remaining, pending_lock, refill_frames, max_actions):
    mode = block["mode"]
    kw = dict(tank=1.0, refill_frames=refill_frames, allow_refill=True,
              max_actions=max_actions, initial_ink=remaining,
              initial_refill_lock_frames=pending_lock)
    if block["kind"] == "target":
        phases = block["phases"]
        phases = [float(phases)] if isinstance(phases, (int, float)) else [float(v) for v in phases]
        return _fixed_target(mode, phases, **kw)
    if block["kind"] == "mob":
        return _fixed_mob(mode, float(block.get("density", .04)),
                          block.get("layout", "grid"), **kw)
    if block["kind"] == "paint":
        return paint_task(mode, float(block["area"]), float(block["area_per_action"]), **kw)
    raise ValueError("block.kind must be target, mob or paint")


def _component(block):
    if block["kind"] == "target":
        return "boss"
    if block["kind"] == "mob":
        return "mob"
    label = str(block.get("label", ""))
    return "wall" if block.get("surface") == "wall" or "墙" in label or block.get("component") == "wall" else "ground"


def run_workload(blocks, refill_frames=180.0, *, initial_ink=1.0, max_actions=10000):
    """Execute integer workload blocks in order using their selected modes.

    Refill stalls are the exact additional delays introduced by the declared
    fixed-mode schedules.  They may exceed pure recovery duration because ink
    locks and renewed mode entry are serialized.  No passive recovery between
    blocks is credited; the model is consequently conservative on that axis.
    """
    if not 0 <= float(initial_ink) <= 1:
        raise ValueError("initial_ink must lie in [0,1]")
    if not math.isfinite(float(refill_frames)) or float(refill_frames) < 0:
        raise ValueError("refill_frames must be finite and non-negative")
    remaining = float(initial_ink)
    pending_lock = 0.0
    elapsed = 0.0
    ink_spent = 0.0
    total_refills = []
    plans = []
    exits = []
    parts = dict(boss=0.0, mob=0.0, ground=0.0, wall=0.0,
                 extra_refill=0.0, release=0.0)
    for index, raw_block in enumerate(blocks):
        block = deepcopy(raw_block)
        mode = block["mode"]
        label = str(block.get("label", f"任务{index + 1}"))
        seed = _seed_plan(block, remaining, pending_lock, refill_frames, max_actions)
        if not seed.get("feasible"):
            return {"feasible": False, "frames": None, "failed_block": index,
                    "failed_label": label, "reason": seed.get("reason"),
                    "components_frames": parts, "taskplans": plans,
                    "remaining_ink": remaining}
        n = int(seed["actions"])
        if n == 0:
            plans.append({"label": label, "kind": block["kind"], "mode": mode["name"],
                          "mode_name": mode["name"], "block_index": index,
                          "actions": 0, "frames": 0.0, "ink_spent": 0.0,
                          "initial_ink": remaining, "remaining_ink": remaining,
                          "start_frame": elapsed, "end_frame": elapsed, "plan": []})
            continue
        replay_mode = deepcopy(mode)
        forced_final_n = n
        forced_burst = bool(mode.get("burst_timing_evidence")) and int(mode.get("burst_size", 0)) > 1
        if forced_burst:
            size = int(mode["burst_size"])
            forced_final_n = int(math.ceil(n / size) * size)
            # Reserve all three automatic rounds before initiating a burst.
            # This preserves the original burst timetable while avoiding an
            # impossible mid-burst refill.  Optional repeated dodge rolls do
            # not carry burst_timing_evidence and are not forced to RepeatCnt.
            replay_mode.update(batch_size=size, batch_charge=0.0,
                               batch_recovery=float(mode["burst_gap"]))
        shared = _Schedule(replay_mode, tank=1.0, refill_frames=refill_frames,
                           allow_refill=True, initial_ink=remaining,
                           initial_refill_lock_frames=pending_lock)
        original = _Schedule(mode, tank=1.0, refill_frames=refill_frames,
                             allow_refill=True, initial_ink=remaining,
                             initial_refill_lock_frames=pending_lock)
        action_shifts = {}
        resource_trace = []
        first_release = None
        terminal = None
        for action in range(1, forced_final_n + 1):
            events = shared.action(action)
            if events is None:
                return {"feasible": False, "frames": None, "failed_block": index,
                        "failed_label": label, "reason": shared.reason,
                        "components_frames": parts, "taskplans": plans}
            if first_release is None:
                first_release = min(e["frame"] for e in events)
            terminal = max(e["frame"] for e in events)
            shared.last_impact = terminal
            if action <= n:
                previous_events = original.action(action)
                original.last_impact = max(e["frame"] for e in previous_events)
                action_shifts[action] = events[0]["frame"] - previous_events[0]["frame"]
            resource_trace.append({"action": action, "last_event_frame": elapsed + terminal,
                                   "remaining_ink": max(0.0, shared.available),
                                   "cumulative_ink_spent": shared.ink_spent,
                                   "forced_automatic_burst_tail": action > n})
        base = (nth_frame(replay_mode, forced_final_n) - float(replay_mode["startup"])
                + max(e["offset"] for e in _events(replay_mode)) + 1)
        active = terminal + 1
        refill_delay = max(0.0, active - base)
        exit_info = _mode_exit(mode, first_release, terminal)
        exit_frames = exit_info["frames"]
        exit_info.update(label=label, block=index,
                         start_frame=elapsed + active,
                         end_frame=elapsed + active + exit_frames)
        trace = []
        for record in seed.get("plan", []):
            record = deepcopy(record)
            if "frame" in record:
                record["frame"] += elapsed + action_shifts.get(int(record["action"]), 0)
            trace.append(record)
        refills = [{**item, "block": index, "label": label,
                    "start_frame": elapsed + item["start_frame"],
                    "end_frame": elapsed + item["end_frame"]} for item in shared.refills]
        plan = {"label": label, "kind": block["kind"], "mode": mode["name"],
                "mode_name": mode["name"], "block_index": index,
                "actions_to_target_completion": n, "actions": forced_final_n,
                "frames": active, "base_frames": base,
                "resource_delay_frames": refill_delay, "exit_frames": exit_frames,
                "initial_ink": remaining, "remaining_ink": max(0.0, shared.available),
                "ink_spent": shared.ink_spent, "refills": refills,
                "start_frame": elapsed, "last_event_frame": elapsed + terminal,
                "end_frame": elapsed + active + exit_frames,
                "plan": trace, "resource_schedule": resource_trace,
                "forced_complete_automatic_burst": forced_burst}
        parts[_component(block)] += base
        parts["extra_refill"] += refill_delay
        parts["release"] += exit_frames
        ink_spent += shared.ink_spent
        total_refills.extend(refills)
        remaining = max(0.0, shared.available)
        stop = mode.get("ink_recover_stop")
        stop = float(stop if isinstance(stop, (int, float)) else mode.get("recovery", 0))
        pending_lock = max(0.0, stop - exit_frames - 1)
        elapsed += active + exit_frames
        plans.append(plan)
        exits.append(exit_info)
    assert abs(sum(parts.values()) - elapsed) <= 1e-6
    discarded = sum(float(r["remaining_ink"]) for r in total_refills)
    balance = float(initial_ink) + len(total_refills) - discarded - ink_spent - remaining
    assert abs(balance) <= 1e-6, ("ink balance", balance)
    return {"feasible": True, "frames": elapsed, "seconds": elapsed / 60,
            "components_frames": parts, "ink_spent": ink_spent,
            "initial_ink": float(initial_ink), "remaining_ink": remaining,
            "discarded_ink_at_refill": discarded, "ink_balance_error": balance,
            "refillcount": len(total_refills), "refill_count": len(total_refills),
            "refills": total_refills, "taskplans": plans, "mode_exits": exits,
            "resource_assumptions": [
                "任务按给定整数块顺序完成，固定模式由调用者决定，不在执行中免费换姿态",
                "只有一个容量为1的墨箱，余墨逐块传递；整批蓄力和自动三连发均按原子预付",
                "无法支付下一原子成本时补满，未用余墨不会被当作已经花掉；不用ceil总耗墨估算补墨次数",
                f"整箱恢复时长设为{float(refill_frames):g}F，为可覆盖的模型假设",
                "补墨前计当前模式回墨锁定；跨块首次补墨计上一动作退出后尚未消退的回墨锁定",
                "extra_refill是相对同一固定动作时序增加的真实停顿，包含未被原动作门限覆盖的回墨锁定",
                "每块等待最后已知发射事件和该模式退出窗口，自动三连发保守发完余弹；不强迫用完可选翻滚次数",
                "潜墨缺测使用该模式recovery并标proxy；无子弹近战保持动作事件代理口径",
                "未奖励任务间潜墨的被动回墨，因此对墨耗的顺序成本属于保守情景",
                "不模拟跨任务保留蓄力或未用储弹，下一任务重新付它声明的起手和整批资源",
                "不含玩家接敌位移、瞄准时间、墙面落墨飞行时延；由调用者另外列示，不能声称实机任务用时",
            ]}
