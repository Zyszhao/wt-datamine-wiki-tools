"""Compare every resolved MiG-35 matrix cell and mass to the saved official page."""
import json
from pathlib import Path
from paths import WIKI, WORK, ROOT
from vehicle_official_reference import parse_saved_page

def main():
    folder = WIKI / 'vehicle-prototype-mig35/pages'
    data = json.loads((folder / 'data/vehicle/mig_35.json').read_text(encoding='utf-8'))
    official = parse_saved_page(ROOT.parent / 'Reference', 'mig_35')
    rows = data['loadouts']['matrix_rows']
    assert len(rows) == len(official['loadout_rows']) == 46
    unmatched = list(official['loadout_rows'])
    checks = []
    for row in rows:
        cells = [row['cells'].get(str(s['index'])) for s in data['loadouts']['display_slots']]
        mask = [bool(c) for c in cells]
        candidates = [r for r in unmatched if abs(r['weight_kg']-row['mass_kg']) < .01 and [bool(s.get('icons')) for s in r['slots']] == mask]
        # Icon identity distinguishes equal-mass variants (Kh-38ML/MT, KAB-500).
        candidates = [r for r in candidates if all(not c or c['icon_file'] == r['slots'][i]['icons'][0] for i,c in enumerate(cells))]
        assert candidates, (row['catalog_id'], row['mass_kg'], mask)
        match = candidates[0]
        unmatched.remove(match)
        checks.append({'id':row['catalog_id'],'count':row['count'],'official':match['name'],'mass_kg':row['mass_kg'],'cells':'passed'})
    assert not unmatched
    cannon = next(w for w in data['weapons'] if w['trigger']=='cannon')
    assert len(cannon['belts']) == 5
    for belt, ref in zip(cannon['belts'],official['belts'][0]['rows']):
        assert belt['filling'] == ref['filling']
        assert belt['penetration'] == ref['penetration']
        assert [f.removeprefix('WTJTreeTesting_ammo_') for f in belt['icon_sequence']] == ref['icon_layers']
    result={'passed':True,'matrix_rows':46,'columns':11,'belts':5,'checks':checks,'source':official['source'],'live_wiki_written':False}
    (WORK/'reports/mig35-reference-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','source')}))

if __name__=='__main__':main()
