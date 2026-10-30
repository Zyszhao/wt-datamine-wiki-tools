"""Compact vehicle-local sensor definitions, installation references and display rows.

Only explicit game fields and named game operating modes are exported. Null is
unknown; false remains false. Simulation state machines are never embedded.
"""
import json
from pathlib import Path


def as_list(v):
    return v if isinstance(v,list) else [] if v is None else [v]


def read_sensor(root, ref):
    base = root/'aces.vromfs.bin_u'/ref.lower().replace('.blk','.blkx')
    if base.is_file():
        return json.loads(base.read_text(encoding='utf-8-sig')), base.relative_to(root).as_posix()
    return {}, ref


def compact_definition(code, raw, source):
    kind = raw.get('type','sensor')
    if 'laser' in code.lower() and kind not in ('lws',): kind='laser_designator'
    tx = raw.get('transivers',{})
    patterns = raw.get('scanPatterns',{})
    signals = raw.get('signals',{})
    fields = ('band','range','rangeMax','rcs','visibilityType','active')
    receivers = {k:{f:v[f] for f in fields if f in v} for k,v in tx.items() if isinstance(v,dict)}
    for k,v in tx.items():
        if isinstance(v,dict) and isinstance(v.get('receiver'),dict):
            receivers[k]['receiver']={f:v['receiver'][f] for f in fields if f in v['receiver']}
    scan = {k:{f:v[f] for f in ('type','azimuthLimits','elevationLimits','period','width','barsCount','tws','hmd') if f in v} for k,v in patterns.items() if isinstance(v,dict)}
    modes = []
    for key,v in raw.get('fsms',{}).get('main',{}).get('actionsTemplates',{}).items():
        if isinstance(v,dict) and v.get('setModeName',{}).get('name'):
            modes.append(v['setModeName']['name'])
    bands={k:v for k,v in raw.items() if k.startswith('band') and k[4:].isdigit()}
    flags={k:raw[k] for k in ('detectTracking','detectLaunch','friendFoeId','targetTracking','targetRangeFinder','trackedTargetsMax','matchSector','range','rxAngle','rangeTargetToSpot','rangeOwnerToSpot') if k in raw}
    groups=as_list(raw.get('groups',{}).get('group'))
    if groups:
        flags['launch_detection_by_group']=any(g.get('detectLaunch') is True and g.get('launch') is True for g in groups if isinstance(g,dict))
    return {'id':code,'kind':kind,'name':raw.get('name',code),'source':source,
            'transceivers':receivers,'scan_patterns':scan,'modes':list(dict.fromkeys(modes)),
            'signal_flags':{k:{f:v[f] for f in ('friendFoeId','track','rangeFinder','groundClutter','targetId') if f in v} for k,v in signals.items() if isinstance(v,dict)},
            'bands':bands,'properties':flags}


def sensor_rows(d):
    source=d['source']; rows=[]
    def row(label,value,unit=None):
        rows.append({'label':label,'value':value,'unit':unit or '', 'source':source})
    row('型号',d['name'])
    tx=d['transceivers']; patterns=d['scan_patterns']; signals=d['signal_flags']
    if d['kind']=='radar':
        bands=[]
        for v in tx.values():
            # IRST transceivers use a different optical band numbering.
            if v.get('visibilityType')=='infraRed': continue
            bands += as_list(v.get('band'))
        if bands: row('雷达波段', ' / '.join(chr(65+n) for n in sorted(set(bands)) if isinstance(n,int) and 0<=n<=14))
        row('工作模式',' / '.join(d['modes']) if d['modes'] else None)
        row('边扫边跟（TWS）',any(v.get('tws') is True for v in patterns.values()) if patterns else None)
        row('敌我识别（IFF）',any(v.get('friendFoeId') is True for v in signals.values()) if signals else None)
        row('IRST',any(v.get('visibilityType')=='infraRed' for v in tx.values()) if tx else None)
        for name,v in tx.items():
            receiver=v.get('receiver',v)
            if receiver.get('range') is not None:
                row(name+' 标称探测距离',receiver['range']/1000,'km')
            if receiver.get('rangeMax') is not None:
                row(name+' 量程上限',receiver['rangeMax']/1000,'km')
        row('距离条件','各模式按原始 transceiver 参数显示；实际发现距离受目标与环境影响')
    if d['bands']:
        indices=[int(k[4:]) for k,v in d['bands'].items() if any(as_list(v))]
        row('告警波段',' / '.join(chr(65+n) if n<15 else str(n) for n in sorted(indices)))
    labels={'range':'作用距离','rxAngle':'接收角范围','detectTracking':'跟踪告警','detectLaunch':'通用发射告警','friendFoeId':'敌我识别','targetTracking':'目标跟踪','targetRangeFinder':'距离指示','trackedTargetsMax':'最大跟踪目标数','matchSector':'识别扇区（°）','launch_detection_by_group':'按威胁类别识别发射','rangeTargetToSpot':'目标至激光光斑距离','rangeOwnerToSpot':'本机至激光光斑距离'}
    for k,v in d['properties'].items():
        row(labels.get(k,k),v/1000 if k=='range' else v,'km' if k=='range' else None)
    return rows


def build_sensors(model, root):
    root=Path(root);definitions={};installations=[];features=[];warnings=[]
    def install(ref,station='机载',option=None,requires=None):
        raw,source=read_sensor(root,ref)
        if not raw:
            warnings.append('未能读取传感器：'+ref);return
        code=Path(ref).stem
        if code not in definitions: definitions[code]=compact_definition(code,raw,source)
        d=definitions[code]; iid=station+'-'+code
        record={'id':iid,'definition_id':code,'role':station,'activation':'loadout' if option else 'modification' if requires else 'always','option':option,'requires_modification':requires,'source':source}
        if record not in installations: installations.append(record)
        if any(f.get('definition_id')==code and f.get('installation_id')==iid for f in features):return
        labels={'radar':'雷达 / 光电探测','rwr':'雷达告警（RWR）','lws':'激光告警（LWS）','laser_designator':'激光指示器','irst':'红外搜索与跟踪'}
        features.append({'id':iid,'label':labels.get(d['kind'],'传感器')+' · '+d['name'],'name':d['name'],'definition_id':code,'installation_id':iid,'rows':sensor_rows(d)})
    for s in as_list(model.get('sensors',{}).get('sensor')):
        if isinstance(s,dict) and isinstance(s.get('blk'),str):install(s['blk'])
    for slot in as_list(model.get('WeaponSlots',{}).get('WeaponSlot')):
        for option in as_list(slot.get('WeaponPreset')):
            for sensor in as_list(option.get('sensors',{}).get('sensor')):
                if isinstance(sensor,dict) and sensor.get('blk'):install(sensor['blk'],'挂点 '+str(slot['index']),option.get('name'),option.get('reqModification'))
            for w in as_list(option.get('Weapon')):
                for s in as_list(w.get('sensors',{}).get('sensor')):
                    if isinstance(s,dict) and s.get('blk'): install(s['blk'],'挂点 '+str(slot['index']),option.get('name'),option.get('reqModification'))
    for mod_id,mod in model.get('modifications',{}).items():
        if not isinstance(mod,dict):continue
        for sensor in as_list(mod.get('effects',{}).get('sensors',{}).get('sensor')):
            if isinstance(sensor,dict) and sensor.get('blk') and Path(sensor['blk']).stem not in definitions:
                install(sensor['blk'],'改装设备',requires=mod_id)
    computer=[]
    for key,label in [('haveCCIPForGun','航炮 CCIP'),('haveCCIPForRocket','火箭 CCIP'),('haveCCIPForBombs','炸弹 CCIP'),('haveCCRPForBombs','炸弹 CCRP'),('haveCCRPForGun','航炮 CCRP'),('gyroSight','陀螺瞄准具'),('hasAimingPointsMemory','瞄准点记忆'),('laserDesignator','激光指示')]:
        if key in model:computer.append({'label':label,'value':model[key],'source':'model.'+key})
    if computer: features.append({'id':'ballistic_computer','name':'弹道计算机','label':'弹道计算机','rows':computer})
    hmd={k:v for k,v in model.items() if ('hmd' in k.lower() or 'helmet' in k.lower()) and isinstance(v,bool)}
    if hmd: features.append({'id':'hmd','name':'头盔瞄准具','label':'头盔瞄准具','rows':[{'label':'头盔目标指示','value':any(hmd.values()),'source':'model.'+' / '.join(hmd)}]})
    night=[]
    blocks=[('基础',model.get('nightVision',{}))]
    for mod in ('night_vision_system','nvd'):
        blocks.append(('改装',model.get('modifications',{}).get(mod,{}).get('effects',{}).get('nightVision',{})))
    labels={'sightTPodThermal':'吊舱热成像','sightThermal':'机载光电热成像','gunnerThermal':'炮手热成像','commanderViewThermal':'车长热成像','driverIr':'驾驶员夜视','gunnerIr':'炮手夜视','pilotIr':'飞行员夜视'}
    for config,block in blocks:
        for name,d in block.items():
            if isinstance(d,dict) and isinstance(d.get('resolution'),list):
                did='night-'+name+'-'+config;definitions[did]={'id':did,'kind':'thermal' if 'thermal' in name.lower() else 'night_vision','name':labels.get(name,name),'resolution':d['resolution'],'generation':d.get('generation'),'source':'model.nightVision.'+name}
                is_pod='tpod' in name.lower()
                installations.append({'id':did,'definition_id':did,'role':name,'activation':'loadout' if is_pod else 'modification' if config=='改装' else 'always','configuration':config})
                night.append({'label':labels.get(name,name)+'（'+('需瞄准吊舱' if is_pod else config)+'）','value':' × '.join(map(str,d['resolution'])),'source':'model.nightVision.'+name+'.resolution'})
    if night:features.append({'id':'night_vision','name':'夜视 / 热成像','label':'夜视 / 热成像','rows':night})
    for station,label in [('cockpit','炮手'),('commanderView','车长'),('driverView','驾驶员')]:
        block=model.get(station,{})
        rows=[{'label':label+text,'value':block[k],'unit':'°','source':'model.'+station+'.'+k} for k,text in [('zoomOutFov','广角视场'),('zoomInFov','放大视场')] if k in block]
        if rows:
            did='optics-'+station; definitions[did]={'id':did,'kind':'optics','name':label+'观瞄','source':'model.'+station,'fov':{k:block[k] for k in ('zoomOutFov','zoomInFov') if k in block}}
            installations.append({'id':did,'definition_id':did,'role':label,'activation':'always'})
            features.append({'id':did,'label':label+'观瞄','name':label+'观瞄','definition_id':did,'installation_id':did,'rows':rows})
    return {'schema':1,'kind':'vehicle_sensors','definitions':definitions,'installations':installations,'features':features,'warnings':warnings,'unknown':['未声明代数时保留 null，不用分辨率猜测代数；标称探测参数不等于实战发现距离']}