"""Verify real aircraft data against game inputs and saved official references."""
import json
from pathlib import Path
from paths import ROOT, REPO, WIKI, WORK
from vehicle_official_reference import extract_saved_html, parse_saved_page


def main():
    read=lambda p: json.loads(p.read_text(encoding='utf-8'))
    mig=read(WIKI/'vehicle-prototype-mig35/pages/data/vehicle/mig_35.json')
    pe=read(WIKI/'vehicle-prototype-pe8/pages/data/vehicle/pe-8_m82.json')
    assert mig['br']=={'ab':14.3,'rb':14.3,'sb':14.3,'grb':13.0}
    assert mig['loadouts']['supported_custom'] is True
    assert pe['loadouts']['supported_custom'] is False and not pe['loadouts']['slots']
    assert len(pe['loadouts']['presets'])==6
    assert [p['mass_kg'] for p in pe['loadouts']['presets']]==[1990.4,4140,3026.4,3049.8,4320,5080]
    assert [p['items'][0]['count'] for p in pe['loadouts']['presets']]==[40,40,12,6,4,1]
    assert all(p['entity']['mass_matches_blk'] is True for p in pe['loadouts']['presets'])
    assert len(pe['weapons'])==6 and len({w['trigger'] for w in pe['weapons']})==5
    assert all(w['role']=='防御炮塔' and len(w['belts'])==3 for w in pe['weapons'])
    assert all(any(r['label']=='备弹量' for r in w['characteristics']) for w in pe['weapons'])
    for data in (mig,pe):
        sensors=data['sensors'];defs=sensors['definitions']
        assert all(i['definition_id'] in defs for i in sensors['installations'])
        assert not any('fsms' in d or 'values' in d for d in defs.values())
    system=mig['sensors'];assert len(json.dumps(system).encode())<40000
    assert system['definitions']['su_spo-150m_02']['properties']['detectLaunch'] is False
    assert system['definitions']['su_spo-150m_02']['properties']['launch_detection_by_group'] is True
    assert any(i['activation']=='loadout' and i['option']=='t220' for i in system['installations'])
    assert any(i.get('requires_modification') for i in system['installations'])
    audit=mig['economy_audit']
    assert audit['repair']['costMultiplier']==1.623
    assert [audit['repair']['modes'][m]['derived'] for m in ('ab','rb','sb')]==[4499,12934,15219]
    assert audit['rewards']['silver']=={'ab':100,'rb':320,'sb':510}
    assert audit['rewards']['research']==268 and audit['talisman']['value']==3500
    economy=next(s for s in mig['sections'] if s['id']=='economy')['rows']
    assert next(r['value'] for r in economy if r['label']=='改装总费（研发点）')==305900
    assert next(r['value'] for r in economy if r['label']=='改装总费（银狮）')==476000
    ref=extract_saved_html(WORK/'research/pe8-official.html',location='https://wiki.warthunder.com/unit/pe-8_m82')
    assert len(ref['belts'])==3
    for weapon in pe['weapons']:
        assert any([b['penetration'] for b in weapon['belts']]==[b['penetration'] for b in t['rows']] for t in ref['belts'])
    result={'passed':True,'version':mig['game_version'],'mig35':{'matrix_rows':46,'sensor_bytes':len(json.dumps(system).encode()),'sensor_references':'passed','conditional_installations':'passed','economy':'passed'},'pe8':{'presets':6,'mounts':6,'gunners':5,'belts_per_mount':3,'preset_mass_crosscheck':'passed','custom_supported':False},'live_wiki_written':False}
    (WORK/'reports/aircraft-system-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()