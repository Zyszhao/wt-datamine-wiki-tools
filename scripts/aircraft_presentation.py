"""Aircraft presentation adapter: saved official results plus local icon parts."""
from pathlib import Path
import json
from vehicle_official_reference import parse_saved_page, extract_saved_html

LABELS = {
 'Max speed':'最大速度', 'Rate of Climb':'爬升率', 'Turn time':'回转时间',
 'Max altitude':'实用升限', 'Takeoff Run':'起飞滑跑距离', 'Crew':'乘员',
 'Engine':'发动机', 'Length':'机长', 'Wingspan':'翼展', 'Wing Loading':'翼载荷',
 'Base weight':'基础重量', 'Fuel in main tanks':'机内燃油', 'Fuel in drop tanks':'副油箱燃油',
 'Max Speed Limit (IAS)':'极限速度（IAS）', 'Mach Number Limit':'极限马赫数',
 'G limit':'过载限制（满内油）', 'Flap Speed Limit (IAS)':'襟翼限制（着陆 / 起飞，IAS）',
 'Gear Speed Limit (IAS)':'起落架限制（IAS）',
 'Landing flaps':'着陆襟翼', 'Take-off flaps':'起飞襟翼', 'Combat flaps':'战斗襟翼', 'Air brake':'减速板',
 'Drogue parachute':'减速伞', 'Flares/Chaff':'热焰弹 / 箔条与导弹逼近告警',
 'Radar/Optical Detection':'雷达 / 光电探测', 'Radar Warning System':'雷达告警接收机',
 'Laser Warning System':'激光告警接收机', 'Ballistic Computer':'弹道计算机',
 'Helmet-mounted display':'头盔瞄准显示器', 'Night vision device':'夜视仪',
 'Thermal imager':'热成像仪', 'Voice warning system':'语音告警系统',
 'Armored targets':'穿甲', 'Armoured targets':'穿甲', 'Default':'默认', 'Universal':'通用', 'Ground targets':'对地', 'Air targets':'对空', 'Stealth':'隐踪',
}

def enrich_aircraft(code, root, model, sections, weapons, reference, images, loadouts, catalog, lang):
    try:
        ref = parse_saved_page(root.parent / 'Reference', code)
    except FileNotFoundError:
        saved = Path(__file__).resolve().parents[1]/'work/research'/('pe8-official.html' if code=='pe-8_m82' else code+'-official.html')
        ref = extract_saved_html(saved,location='https://wiki.warthunder.com/unit/'+code) if saved.is_file() else {'source':{},'specification_blocks':[],'belts':[],'loadout_rows':[], 'slot_headers':[]}
    source = ref['source'].get('file','') + '; ' + ref['source'].get('location','')
    if ref['source']:
        reference['aircraft_snapshot'] = ref['source']
    source = source + ' (saved official result)'
    if ref['specification_blocks']:
        sections[:] = [s for s in sections if s['id'] not in ('general', 'mobility', 'survivability', 'optics')]
    converted = []
    for block in ref['specification_blocks']:
        if block['title'] not in ('Flight performance', 'General characteristics'):
            continue
        sid = 'mobility' if block['title'] == 'Flight performance' else 'aircraft-general'
        rows = []
        for r in block['rows']:
            rr = (r.get('sub_rows') or [r])[0] if not r.get('text') else r
            unit = rr.get('unit', '')
            label = LABELS.get(r['label'], r['label'])
            modes = rr.get('modes') or r.get('modes')
            if modes:
                value = {m: str(v.get('stock', '—')) + ' → ' + str(v.get('upgraded', '—')) for m,v in modes.items() if m in ('ab','rb')}
                unit = {'Max speed':'km/h','Rate of Climb':'m/s','Turn time':'秒','Base weight':'t'}.get(r['label'],unit)
                label += '（基础 → 完全体）'
            else:
                value = rr.get('text') or rr.get('value')
                unit = ''  # Text already contains the original unit and compound values.
                if r['label'] == 'Crew': value = str(rr.get('value')) + ' 人'
            if r['label'] == 'Max speed': label += '（12,000 m）' if '12,000' in rr.get('label','') else ''
            group = 'weight' if r['label'] in ('Base weight','Fuel in main tanks','Fuel in drop tanks') else 'limits' if r['label'] in ('Max Speed Limit (IAS)','Mach Number Limit','G limit','Flap Speed Limit (IAS)','Gear Speed Limit (IAS)') else 'main'
            rows.append({'label':label,'value':value,'unit':unit,'group':group,'source':source,'status':'official_reference_snapshot'})
        availability = block.get('availability', {})
        for label, state in zip(availability.get('labels',[]),availability.get('states',[])):
            rows.append({'label':LABELS.get(label,label),'value':'✓' if state.get('has_check') else '—','source':source,'group':'equipment'})
        converted.append({'id':sid,'title':'飞行性能' if sid=='mobility' else '一般特征', 'rows':rows,
            'features':[LABELS.get(f['title'],f['title']) for f in block.get('features',[])]})
    sections[0:0] = converted
    def icon(part):
        p = root / 'atlases.vromfs.bin_u/gameuiskin' / part
        if p.is_file():
            name = p.name
            images[name] = p
            return name
        return None
    # Derive recipes from BLK, preserving each projectile in order. The saved
    # official table supplies penetration results, not the round sequence.
    gui = json.loads((root/'aces.vromfs.bin_u/config/gui.blkx').read_text(encoding='utf-8'))
    for weapon in weapons:
        if not weapon.get('ammunition_ids'): continue
        definition = json.loads((root/weapon['weapon_source']).read_text(encoding='utf-8'))
        recipes = [('默认', definition.get('bullet', []), 'default')]
        for key, value in definition.items():
            if isinstance(value,dict) and 'bullet' in value:
                suffix = next((s for s in ('universal','ground_targets','air_targets','stealth','armored_targets','armoured_targets') if key.lower().endswith(s)), None)
                if suffix: recipes.append(({'universal':'通用','ground_targets':'对地','air_targets':'对空','stealth':'隐踪','armored_targets':'穿甲','armoured_targets':'穿甲'}[suffix], value['bullet'], key))
        weapon['belt_recipes'] = []
        for label, bullets, key in recipes:
            bullets = bullets if isinstance(bullets,list) else [bullets]
            sequence = [icon(gui['bullet_icons'].get(b.get('guiCustomIcon') or b.get('bulletType'),'bullet_cannon_brown')+'.png') for b in bullets]
            sequence = [f for f in sequence if f]
            if len(sequence)==2: sequence *= 2
            weapon['belt_recipes'].append({'name':label,'key':key,'types':[b.get('bulletType') for b in bullets],'icon_sequence':sequence,'source':weapon['weapon_source']})
    # A belt is a sequence, not an overlay. Preserve the game's round order.
    for table in ref.get('belts',[]):
        for weapon in weapons:
            default = next((r for r in weapon.get('belt_recipes',[]) if r['key']=='default'),None)
            if not default: continue
            expected=[f for x in table['rows'][0]['icon_layers'] if (f:=icon(x))]
            if default['icon_sequence'] != expected: continue
            weapon['belts'] = [{
                'name':LABELS.get(b['belt'],b['belt']), 'filling':b['filling'],
                'icon_sequence':[f for x in b['icon_layers'] if (f:=icon(x))],
                'penetration':b['penetration'],'source':source,
            } for b in table['rows']]
            weapon['belt_distances'] = table['distances']
            recipes = {r['name']:r for r in weapon.get('belt_recipes',[])}
            for belt in weapon['belts']:
                recipe = recipes.get(belt['name'])
                if recipe:
                    if recipe['icon_sequence'] != belt['icon_sequence']:
                        raise ValueError('BLK belt recipe differs from the saved official reference: '+belt['name'])
                    belt['icon_sequence'] = recipe['icon_sequence']
                    belt['recipe_source'] = recipe['source']
    used_ids = {i['id'] for p in loadouts.get('presets',[]) for i in p.get('items',[])}
    raw_slots = model.get('WeaponSlots',{}).get('WeaponSlot',[])
    if isinstance(raw_slots,dict): raw_slots=[raw_slots]
    loadouts['display_slots'] = [{'index':s['index'], 'label':s['tier'], 'side':'center' if s.get('notUseforDisbalanceCalculation') else 'left' if s['tier'] < loadouts['limits'].get('tiers_count_used',13)/2 else 'right'} for s in raw_slots if isinstance(s.get('tier'),int)]
    loadouts['display_slots'].sort(key=lambda s:s['label'])
    matrix = {}
    for slot in loadouts['slots']:
        slot['display_index'] = slot.get('tier') if slot.get('tier') is not None else slot['tier_used']
        raw_slot = next(s for s in raw_slots if s['index'] == slot['index'])
        slot['not_use_for_disbalance'] = bool(raw_slot.get('notUseforDisbalanceCalculation'))
        if slot['not_use_for_disbalance']:
            slot['side'] = 'center'
        else:
            slot['side'] = 'left' if slot['display_index'] < loadouts['limits'].get('tiers_count_used',13)/2 else 'right'
        for option in slot['options']:
            names = []
            for item in option['items']:
                used_ids.add(item['id'])
                names.append(str(item['count']) + ' × ' + catalog[item['id']]['name'])
            if names: option['name'] = ' + '.join(names)
            part = option.get('icon_source_file')
            if part: option['icon_file'] = icon(Path(part).name)
            for item in option['items']:
                key = (item['id'], item['count'])
                triggers = [w.get('trigger') for w in option.get('weapons',[]) if any(i['id']==item['id'] for i in w.get('items',[]))]
                category = next(({'aam':'aam','atgm':'agm','bombs':'bomb','guided bombs':'guided_bomb','rockets':'rocket','torpedoes':'torpedo','cannon':'gun','fuel tanks':'fuel'}.get(t,'pod') for t in triggers), 'pod')
                row = matrix.setdefault(key, {'catalog_id':item['id'],'count':item['count'],'mass_kg':option.get('mass_kg'),'category':category,'cells':{}})
                row['cells'][str(slot['index'])] = {'count':item['count'],'icon_file':option.get('icon_file')}
            # Detailed recursive traces belong in the audit, not every option.
            option['mach_limit'] = min((w['machLimit'] for w in option.get('weapons', []) if isinstance(w.get('machLimit'), (int,float))), default=None)
            option.pop('weapons', None)
            for dependency in option.get('dependencies', []) + option.get('blocking', []):
                dependency.pop('raw', None)
    loadouts['matrix_rows'] = list(matrix.values())
    for preset in loadouts.get('presets',[]):
        if preset.get('items'):
            preset['name'] = ' + '.join(str(i['count'])+' × '+catalog[i['id']]['name'] for i in preset['items'])
        preset.pop('weapons',None)
    loadouts['slots'].sort(key=lambda s:s['display_index'])
    obsolete={'slots.tier_order','slots.side_parity','restrictions','disbalance_centre_inconsistency'}
    loadouts['known_rules']=[r for r in loadouts.get('known_rules',[]) if r['id'] not in obsolete]+[
        {'id':'display.tiers','rule':'Matrix columns use explicit tier ascending; game slot index remains the identity for dependencies.','source':'WeaponSlot.tier; saved official matrix cross-check'},
        {'id':'display.console_mass','rule':'notUseforDisbalanceCalculation slots are central; remaining tier coordinates below tiers_count_used/2 sum to the left, others right.','source':'weaponrypresetsparams.nut:getPresetWeightRestrictionText'},
        {'id':'validation.static','rule':'Browser checks option availability, dependencies, blocking, total/wing mass and imbalance; all modifications assumed researched.','source':'src/vehicle.js:initLoadouts'}]
    loadouts['unknown_rules']=[r for r in loadouts.get('unknown_rules',[]) if r['id'] not in ('mass_limits_not_evaluated','custom_presets')]

    parameter_labels = {
        'Caliber':'口径','Projectile Mass':'弹体重量','Guidance':'制导方式','Aspect':'攻击方向',
        'Lock range in rear-aspect':'尾追锁定距离','Lock range in all-aspect':'全向锁定距离',
        'IRCCM':'红外抗干扰','Launch range':'发射距离','Maximum speed':'最大速度',
        'Maximum overload':'最大过载','Missile guidance time':'制导时间','Explosive Type':'装药类型',
        'Explosive Mass':'装药量','TNT equivalent':'TNT 当量','Band':'波段','Shoot down':'攻击方向',
        'Lock range':'锁定距离','Fuze sensitivity':'引信灵敏度','Fuze delay':'引信延迟',
        'Armor penetration':'穿深','Type':'类型','Drag coefficient':'阻力系数',
    }
    remaining = list(ref['loadout_rows'])
    for row in loadouts['matrix_rows']:
        cells = [row['cells'].get(str(s['index'])) for s in loadouts['display_slots']]
        for official in remaining:
            if abs((official.get('weight_kg') or 0) - (row.get('mass_kg') or 0)) > .01: continue
            if [bool(c) for c in cells] != [bool(c.get('icons')) for c in official['slots']]: continue
            if any(c and not c['icon_file'] == official['slots'][i]['icons'][0] for i,c in enumerate(cells)): continue
            item = catalog[row['catalog_id']]
            item['display_parameters'] = [{'label':parameter_labels.get(p['label'],p['label']),'value':{'All-aspects':'全向','Rear-aspect':'尾追','IR':'红外','SARH':'半主动雷达','ARH':'主动雷达','TV':'电视'}.get(p['value'],p['value']),'source':source} for p in official.get('parameters',[]) if p['value']]
            remaining.remove(official)
            break
    for preset in loadouts['presets']:
        preset['assignments'] = [{k:a[k] for k in ('slot','preset','found') if k in a} for a in preset.get('assignments',[])]
    for slot in loadouts['slots']:
        slot['options'] = [{k:o[k] for k in ('id','name','requires_modification','dependencies','blocking','items','mass_kg','mass_status','icon_file','mach_limit') if o.get(k) is not None and o.get(k)!=[] and o.get(k)!=''} for o in slot['options']]
    for key in list(catalog):
        if key not in used_ids: del catalog[key]
    for item in catalog.values():
        if item.get('icon_source_file'): item['icon_file'] = icon(Path(item['icon_source_file']).name)
        item.pop('used_by_blk', None)
        guidance = item.get('guidance') or {}
        raw_guidance = guidance.get('guidance') or {}
        # Export display/validation fields, leaving simulation tables in the input.
        if isinstance(raw_guidance, dict):
            guidance['guidance'] = {k: raw_guidance[k] for k in ('lockDistance','warmUpTime','workTime','inertialNavigation','lockAfterLaunch','uncageBeforeLaunch') if k in raw_guidance}
    # Image choice belongs to this aircraft and its preset, not the shared
    # munition definition: identical weapons can use different vehicle UI icons.
    loadouts['item_icons'] = {key: item['icon_file'] for key, item in catalog.items() if item.get('icon_file')}
    for preset in loadouts.get('presets', []):
        if preset.get('icon_source_file'):
            preset['icon_file'] = icon(Path(preset['icon_source_file']).name)
        for item in preset.get('items', []):
            item['icon_file'] = (preset.get('icon_file') if len(preset['items']) == 1 else None) or loadouts['item_icons'].get(item['id'])
    # The reference matrix is preserved for parity checks, not as a replacement
    # for the game-resolved editable configuration.
    loadouts['official_matrix_reference'] = {'source':ref['source'],'rows':len(ref['loadout_rows']),'columns':len(ref['slot_headers'])}
