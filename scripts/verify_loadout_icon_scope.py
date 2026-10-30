"""Keep per-aircraft/preset icon choices independent of shared munition facts."""
import json
import re
import sys

from paths import ROOT, REPO, WIKI, WORK
from aircraft_loadouts import build_loadouts
from aircraft_presentation import enrich_aircraft
from vehicle_page import make_pages, merge_ordnance_pages


def main():
    try:
        from lupa import LuaRuntime
    except ImportError:
        sys.path.insert(0, str(ROOT / 'vendor/python/packages'))
        from lupa import LuaRuntime
    lua = LuaRuntime(unpack_returned_tuples=True)
    def convert(value):
        if isinstance(value, dict):
            return lua.table_from({k:convert(v) for k,v in value.items()})
        if isinstance(value, list):
            return lua.table_from([convert(v) for v in value])
        return value
    module = lua.execute((ROOT / 'src/loadouts.lua').read_text(encoding='utf-8'))
    cases = []
    shared = []
    for code, preset_name, expected in [('a-26b', '500lbs_wing_left_out', 'bombs_large'),
                                         ('a2d', '500lbs', 'bombs_middle')]:
        path = REPO / 'aces.vromfs.bin_u/gamedata/flightmodels' / (code + '.blkx')
        model = json.loads(path.read_text(encoding='utf-8'))
        loadouts = build_loadouts(model, REPO, None)
        catalog = {i['id']:i for i in loadouts.pop('catalog')}
        enrich_aircraft(code, REPO, model, [], [], {}, {}, loadouts, catalog, {})
        slot, option = next((s,o) for s in loadouts['slots'] for o in s['options'] if o['id']==preset_name)
        cid = option['items'][0]['id']
        assert option['items'][0]['count']==1
        icon = expected + '.png'
        assert option['icon_file']==icon
        row = next(r for r in loadouts['matrix_rows'] if r['catalog_id']==cid and r['count']==1)
        assert row['cells'][str(slot['index'])]['icon_file']==icon
        pages = make_pages({'id':code, 'aircraft_catalog':catalog, 'loadouts':loadouts}, ROOT/'src/vehicle.lua', 'WTJ')
        shards = [p for p in pages if p['model']=='json' and '/data/ordnance/' in p['title']]
        physical = {key:item for p in shards for key,item in json.loads(p['content'])['items'].items()}
        assert all(not any(k in item for k in ('icon_file','icon_type','icon_source_file')) for item in physical.values())
        shared.append(json.dumps({'schema':1,'kind':'aircraft_ordnance','items':{cid:physical[cid]}}))
        # One real option from each aircraft, rendered against the same physical
        # resource with a deliberately conflicting global icon.
        physical[cid]['icon_file']='GLOBAL_ICON_MUST_NOT_RENDER.png'
        fixture = {'supported_custom':True, 'slots':[{**slot,'options':[option]}],
            'display_slots':[{'index':slot['index'],'label':slot['display_index']}],
            'item_icons':loadouts['item_icons'], 'matrix_rows':[{**row,'cells':{str(slot['index']):row['cells'][str(slot['index'])]}}]}
        html = module.render(convert(fixture), convert(physical))
        matrix = re.search(r'<tr data-store="[^\"]+">(.*?)</tr>', html, re.S).group(1)
        assert '[[File:'+icon+'|' in matrix
        assert 'GLOBAL_ICON_MUST_NOT_RENDER' not in html
        fixed = {'supported_custom':False,'presets':[{'items':[{'id':cid,'count':1,'icon_file':icon}]}]}
        fixed_html = module.render(convert(fixed), convert(physical))
        assert '[[File:'+icon+'|' in fixed_html and 'GLOBAL_ICON_MUST_NOT_RENDER' not in fixed_html
        cases.append({'vehicle':code,'preset':preset_name,'weapon_id':cid,'count':1,'icon_file':icon})
    assert cases[0]['weapon_id']==cases[1]['weapon_id']
    assert cases[0]['icon_file']!=cases[1]['icon_file']
    merge_ordnance_pages(shared[0], shared[1])
    for folder in ('vehicle-prototype-mig35','vehicle-prototype-pe8'):
        for page in (WIKI/folder/'pages/data/ordnance').glob('*.json'):
            assert all(not any(k in item for k in ('icon_file','icon_type','icon_source_file'))
                       for item in json.loads(page.read_text(encoding='utf-8'))['items'].values())
    result={'passed':True,'real_game_cases':cases,'shared_ordnance_merge':'passed',
            'matrix_dropdown_and_fixed_preset_local_icons':'passed','shared_icon_override_ignored':'passed'}
    (WORK/'reports/loadout-icon-scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
