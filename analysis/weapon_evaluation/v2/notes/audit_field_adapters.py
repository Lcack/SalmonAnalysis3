"""Audit all available modes and selected independent mechanism invariants."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[1]
sys.path.insert(0, str(HERE.parent))
from field_adapters import adapt_modes, _wall

source = json.loads((BASE/'evaluation.json').read_text(encoding='utf8'))
weapons = []
for w in source['weapons']:
    gp = json.loads((ROOT/w['source']).read_text(encoding='utf8'))['GameParameters']
    before = deepcopy(w['modes'])
    modes = adapt_modes(w['id'], gp, w['modes'])
    assert before == w['modes'], w['id']
    assert len(modes) == len(before)
    for m in modes:
        for key in ['release_to_swim_frames', 'range_extreme_proxy', 'wall_area_per_action_proxy']:
            val = m[key]
            assert val is None or (math.isfinite(val) and val >= 0), (w['id'], m['name'], key, val)
        if w['family'] == 'Spinner':
            assert m['release_to_swim_frames'] == 7
            assert m['release_to_swim_evidence']['sustained_cancel_to_swim_frames'] == 6
        if w['family'] == 'Shelter':
            assert m['wall_area_per_action_proxy'] is not None
            assert 'SplashWallDropCollisionParam' in ' '.join(m['wall_area_evidence']['parameter_paths'])
        if w['id'].startswith('Shooter_Triple'):
            period = 2*m['interval']+m['burst_gap']
            assert period == (18 if 'TripleQuick' in w['id'] else 32), (w['id'], period)
        if w['id'] == 'Saber_Bear_Coop':
            assert m['release_to_swim_frames'] is None
        if w['family'] == 'Blaster':
            for condition in ['near','burst']:
                p=m['wall_profiles'][condition]
                assert p['area'] is not None and math.isclose(p['area'],math.pi*p['radius']**2)
                assert not p['damage_radius_used_for_area']
            p=m['wall_profiles']['burst']
            assert math.isclose(p['damage_outer_edge_distance'],p['distance']+p['damage_outer_radius'])
            if w['id']=='Blaster_Precision_Coop' and m['range_grounded_eligible']:
                assert m['wall_profiles']['near']['radius']==.7
                assert m['wall_profiles']['burst']['radius']==1.0
            if w['id']=='Blaster_Middle_Coop':
                assert m['wall_profiles']['near']['radius']==1.4
                assert m['wall_profiles']['burst']['radius']==2.0
                assert m['wall_profiles']['near']['evidence']['parameter_status']=='documented_default_for_explicit_class'
        else:
            assert m['wall_profiles']['near']['area']==m['wall_area_per_action_proxy']
            assert m['wall_profiles']['burst']['area']==m['wall_area_per_action_proxy']
    weapons.append({'id': w['id'], 'family': w['family'], 'modes': modes})

# A default is justified by its exact documented class, not its key's spelling.
area, evidence = _wall('Stringer_Foo_Coop', {'spl__BulletStringerParam': {'WallDropPaintParam': {'$type': 'spl__BulletWallDropCollisionPaintParam'}}}, {'name': 'test'})
assert math.isclose(area, math.pi*1.3**2) and len(evidence['typed_defaults_applied']) == 1
for node in [{}, {'$type': 'some_other_type'}]:
    area, evidence = _wall('Stringer_Foo_Coop', {'spl__BulletStringerParam': {'WallDropPaintParam': node}}, {'name': 'test'})
    assert area is None and not evidence['typed_defaults_applied']

measured = json.loads((HERE/'endlag_measurements.json').read_text(encoding='utf8'))
assert len(measured['missing']) == 7
assert all(measured['weapons'][wid]['release_to_swim_frames'] is None for wid in measured['missing'])
counts = {'weapons': len(weapons), 'modes': sum(len(w['modes']) for w in weapons)}
for key in ['release_to_swim_frames', 'range_extreme_proxy', 'wall_area_per_action_proxy']:
    counts[key+'_missing'] = sum(m[key] is None for w in weapons for m in w['modes'])
counts['low_confidence_endlag_proxy_modes'] = sum(m['release_to_swim_evidence']['confidence'] == '低' for w in weapons for m in w['modes'])
output = {'source': 'v1 evaluation modes copied unchanged then explicit v2 adapters', 'checks': 'finite nonnegative or null; legacy input unchanged; all six spinners 7 and sustained cancel6; all shelters use SplashWallDropCollisionParam; L3/H3 period18/32; Grizz Saber strict release metric null; exact-class-only wall default; raw missing measurements kept null; blaster near/burst are paint-radius circles with damage-edge distance distinct; Precision explicit0.7/1.0 and Middle typed-default1.4/2.0', 'counts': counts, 'weapons': weapons}
(HERE/'adapted_modes_audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps(counts))
