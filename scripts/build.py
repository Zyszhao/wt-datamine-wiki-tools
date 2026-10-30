"""Offline global catalogues and complete USA ground shop tree. No network writes."""
from pathlib import Path
import csv,hashlib,html,json,re,shutil,sys
from datetime import datetime, timezone
from tree_policy import GAME_TYPES, game_type, exclusion_reason
from tree_specs import DEPLOY_TREES, BRANCH_CLASSES, tree_id, tree_label
from xml.etree import ElementTree as ET
from paths import ROOT, REPO, WIKI, WORK, SCRIPT_USER, ensure_output_dirs
ensure_output_dirs()
PREFIX='WTJTreeTesting'
MAX=2097152

def dump(o):return json.dumps(o,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(dump(o),encoding='utf-8')
def read(p):return json.loads((REPO/p).read_text(encoding='utf-8'))
def digest(o):return hashlib.sha256(dump(o).encode()).hexdigest()[:16]

def main():
 version=(REPO/'version').read_text().strip();lang={}
 for name in ['units','units_weaponry','units_modifications','menu']:
  with (REPO/f'lang.vromfs.bin_u/lang/{name}.csv').open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f,delimiter=';'):
    key=r['<ID|readonly|noverify>'];lang[key.casefold()]=r
 def tr(key):
  r=lang.get(key.casefold(),{});return (r.get('<Chinese>','').replace('\u200b','').replace('\ufeff','') or None)
 def text(key):return tr(key) or lang.get(key.casefold(),{}).get('<English>') or key
 economy=read('char.vromfs.bin_u/config/wpcost.blkx');shop=read('char.vromfs.bin_u/config/shop.blkx');defs=read('char.vromfs.bin_u/config/modifications.blkx')['modifications']
 ammo_names={};weapon_ammo={}
 for path in (REPO/'aces.vromfs.bin_u/gamedata/weapons').rglob('*.blkx'):
  weapon=json.loads(path.read_text(encoding='utf-8'))
  for ammo,value in weapon.items():
   if not isinstance(value,dict) or 'bullet' not in value:continue
   bullets=value['bullet'] if isinstance(value['bullet'],list) else [value['bullet']]
   for bullet in bullets:
    if not isinstance(bullet,dict) or not isinstance(bullet.get('bulletName'),str):continue
    key=bullet['bulletName'];name=tr(key) or tr(key+'/name')
    if name:
     ammo_names.setdefault(ammo.casefold(),set()).add(name)
     weapon_ammo.setdefault(str(path.relative_to(REPO)).replace('\\','/').lower(),{}).setdefault(ammo.casefold(),set()).add(name)
 unit_tags=read('char.vromfs.bin_u/config/unittags.blkx')
 unlocks={u['id']:u for u in read('char.vromfs.bin_u/config/unlocks.blkx')['unlockable'] if 'id' in u}
 units={};placements={};trees={};groups={}
 presentation=json.loads((ROOT/'evidence/presentation-map.json').read_text(encoding='utf-8'))
 # shop range order is significant; preserve folders and flags, never sort columns.
 for country,branches in shop.items():
  for branch,body in branches.items():
   columns=[]
   for col_no,col in enumerate(body.get('range',[]),1):
    nodes=[]
    for key,value in col.items():
     if not isinstance(value,dict):continue
     if key in economy:members=[(key,value)];folder=None
     else:members=[(u,v) for u,v in value.items() if u in economy and isinstance(v,dict)];folder=key
     if not members:continue
     if folder:
      old=presentation['groups'].get(folder,{})
      name=old.get('name') or tr(folder+'_shop') or tr(folder) or ' / '.join(text(u+'_shop') for u,v in members)
      group={'name':name,'country':country,'branch':branch,'members':[u for u,v in members],'file':old.get('file',folder+'.png'),'name_source':'bwiki_group' if old.get('name') else 'game_localization' if tr(folder+'_shop') or tr(folder) else 'member_names'}
      if folder in groups and groups[folder]!=group:raise ValueError('conflicting group definition: '+folder)
      groups[folder]=group
     node={'folder':folder,'units':[u for u,v in members]}
     nodes.append(node)
     for u,v in members:
      inherited={k:x for k,x in value.items() if not isinstance(x,dict) and k!='image'} if folder else {}
      placement={'country':country,'branch':branch,'column':col_no,'node':len(nodes),'folder':folder,'rank':v.get('rank'),'flags':{**inherited,**{k:x for k,x in v.items() if k!='rank'}}}
      placements.setdefault(u,[]).append(placement)
    columns.append({'column':col_no,'nodes':nodes})
   trees[(country,branch)]=columns
 modes=['Arcade','Historical','Simulation']
 class_names={k:text('mainmenu/type_'+k.removeprefix('exp_')) for k in {e.get('unitClass') for e in economy.values() if isinstance(e,dict) and e.get('unitClass')}}
 for code,e in economy.items():
  if not isinstance(e,dict) or not e.get('country') or not e.get('unitClass'):continue
  raw=[e.get('economicRank'+mode) for mode in modes]
  br=[(int(x/3*10+10+0.5)/10 if x is not None else None) for x in raw]
  model=REPO/('aces.vromfs.bin_u/gamedata/units/tankmodels/'+code.lower()+'.blkx')
  model_type=json.loads(model.read_text(encoding='utf-8')).get('type') if model.exists() else None
  role,role_source=game_type(unit_tags.get(code,{}),model_type)
  category=GAME_TYPES.get(role)
  if e['unitClass'] not in BRANCH_CLASSES['army']:
   role=e['unitClass'];category=class_names[role];role_source='wpcost.unitClass + mainmenu/type localization'
  units[code]={'name':text(code+'_shop'),'country':e['country'],'class':e['unitClass'],'category':category,'game_type':role,'category_source':role_source,'rank':e.get('rank'),'br':br}
  if e['unitClass'] in BRANCH_CLASSES['aviation']:
   ground_rank=e.get('economicRankTankHistorical')
   if ground_rank is None:ground_rank=e.get('economicRankHistorical')
   units[code]['br_ground_rb']=int(ground_rank/3*10+10+0.5)/10 if ground_rank is not None else None
 classes={k:text('mainmenu/type_'+k.removeprefix('exp_')) for k in sorted({r['class'] for r in units.values()})}
 for code,old in presentation['groups'].items():
  if code not in groups:
   members=old.get('members',[]);first=placements.get(members[0],[{}])[0] if members else {}
   groups[code]={'name':old['name'],'file':old['file'],'country':first.get('country'),'branch':first.get('branch'),'members':members,'name_source':'bwiki_group','legacy_only':True}
 index={'schema':1,'kind':'vehicle_index','game_version':version,'br_modes':['ab','rb','sb'],'br_formula':'round_half_up(economicRankMODE/3+1,0.1)','classes':classes,'records':units,'groups':groups}
 # Global definitions, plus shared override variants. No per-vehicle prices or tiers.
 registry={};missing=[];unresolved_icons=[];icon_registry={}
 atlas=REPO/'atlases.vromfs.bin_u/gameuiskin';available={p.stem:p for p in atlas.iterdir() if p.is_file()}
 def entry(code,d,base=None):
  key='modification/'+code
  # Ammo packs have dynamic in-game names: preserve generic recipe and explicit status.
  title=tr(key);description=tr(key+'/desc');status='translated' if title else 'missing'
  if code.endswith('_ammo_pack') and not title:
   short=code.removesuffix('_ammo_pack');names=d.get('_ammo_names',sorted(ammo_names.get(short.casefold(),[])));title=tr(short+'/name/short') or tr(short+'/name') or tr(short) or tr('modification/'+short) or (' / '.join(names) if names else None);description=description or tr('modification/ammo_pack/desc');status=('ammo_vehicle_resolved' if '_ammo_names' in d else 'ammo_candidates') if title else 'dynamic_ammo_unresolved'
   if title and description:description=description.replace('%s',title)
  title=title or (text(key) if key.casefold() in lang else code)
  images={k:v for k,v in d.items() if k in ['image','image_tank','image_aircraft']}
  resolved={}
  for k,v in images.items():
   match=re.search(r'#ui/gameuiskin#([^/]+)$',v)
   p=available.get(Path(match[1]).stem) if match else None
   iid='i_'+digest(v);resolved[k]=iid
   icon_registry[iid]={'game':v,'file':('WTJTreeTesting_'+p.name) if p else None,'source':str(p.relative_to(REPO)).replace('\\','/') if p else None}
   if not p:unresolved_icons.append({'code':code,'field':k,'game':v})
  result={'name':title,'description':description,'text_status':status,'icons':resolved,'category':d.get('modClass',''),'hidden':bool(d.get('isHidden',False))}
  if description is None:missing.append(code)
  return result
 for code,d in defs.items():registry[code]=entry(code,d)
 variants={};local={}
 for unit,e in economy.items():
  if unit not in units:continue
  context={};model=REPO/('aces.vromfs.bin_u/gamedata/units/tankmodels/'+unit.lower()+'.blkx')
  if model.exists():
   mounts=json.loads(model.read_text(encoding='utf-8')).get('commonWeapons',{}).get('Weapon',[])
   if isinstance(mounts,dict):mounts=[mounts]
   for mount in mounts:
    if not isinstance(mount,dict) or not isinstance(mount.get('blk'),str):continue
    path=('aces.vromfs.bin_u/'+mount['blk'].replace('.blk','.blkx')).lower()
    for ammo,names in weapon_ammo.get(path,{}).items():context.setdefault(ammo,set()).update(names)
  mods=[];order={}
  for code,d in e.get('modifications',{}).items():
   if not isinstance(d,dict) or d.get('tier',0)<=0:continue
   base=defs.get(code,{})
   override={k:v for k,v in d.items() if k in ['image','image_tank','image_aircraft','modClass','isHidden'] and v!=base.get(k)}
   if code.endswith('_ammo_pack') and code.removesuffix('_ammo_pack').casefold() in context:
    override['_ammo_names']=sorted(context[code.removesuffix('_ammo_pack').casefold()])
   if code not in registry:registry[code]=entry(code,{})
   ref=code
   if override:
    ref=code+'@'+digest(override)
    if ref not in variants:variants[ref]={**entry(code,{**base,**override}),'base':code}
   cls=d.get('modClass',base.get('modClass',''));tier=d['tier'];pos=(cls,tier);order[pos]=order.get(pos,0)+1
   mods.append({'ref':ref,'position':{'tier':tier,'category':cls,'order':order[pos]},'rp':d.get('reqExp'),'sl':d.get('value'),'ge':d.get('costGold',0),'unlock_ge':d.get('openCostGold'),'requires':d.get('reqModification',[]),'previous':d.get('prevModification')})
  local[unit]={'modifications':mods}
 registry.update(variants)
 modindex={'schema':1,'kind':'modification_index','game_version':version,'icons':icon_registry,'records':registry}
 ground={'exp_tank','exp_heavy_tank','exp_tank_destroyer','exp_SPAA'}
 us={u for u,v in units.items() if v['country']=='country_usa' and v['class'] in ground}
 from tree_layout import enrich
 generated={};coverage={}
 for (country,branch),raw_columns in trees.items():
  key=tree_id(country,branch)
  raw_shop={u for c in raw_columns for n in c['nodes'] for u in n['units']}
  excluded={u:exclusion_reason(u,unit_tags) for u in sorted(raw_shop) if exclusion_reason(u,unit_tags)}
  columns=[{'column':c['column'],'nodes':[{**n,'units':[u for u in n['units'] if u not in excluded]} for n in c['nodes'] if any(u not in excluded for u in n['units'])]} for c in raw_columns]
  in_shop={u for c in columns for n in c['nodes'] for u in n['units']}
  scope={u for u,v in units.items() if v['country']==country and v['class'] in BRANCH_CLASSES[branch]} | raw_shop
  extra=sorted(scope-raw_shop)
  flags={u:next(p['flags'] for p in placements[u] if p['country']==country and p['branch']==branch) for u in in_shop}
  edges=[]
  for u in sorted(in_shop):
   parent=flags[u].get('reqAir',economy[u].get('reqAir'))
   if parent in in_shop:edges.append({'from':parent,'to':u})
   elif parent in groups:
    candidates=[v for v in groups[parent]['members'] if v in in_shop]
    if candidates:edges.append({'from':candidates[-1],'to':u})
  item={'schema':1,'kind':'tech_tree','game_version':version,'id':key,'label':tree_label(country,branch),'country':country,'branch':branch,'columns':columns,'flags':flags,'unplaced':extra,'excluded':excluded,'raw_shop_count':len(raw_shop),'visible_count':len(in_shop),'edges':edges,'ranks':sorted({units[u]['rank'] for u in in_shop if units[u]['rank'] is not None})}
  if branch=='helicopters':
   requirements=[]
   for u,f in flags.items():
    if not f.get('reqUnlock'):continue
    unlock=unlocks[f['reqUnlock']]['mode'];conditions=[]
    if unlock['type']!='char_unlocks' or unlock['num']!=1:raise ValueError('Unsupported helicopter unlock: '+u)
    for ref in unlock['unlock']:
     condition=unlocks[ref]['mode']
     if condition['type']!='char_aircrafts_in_era':raise ValueError('Unsupported helicopter condition: '+ref)
     conditions.append({'id':ref,**condition})
    requirements.append({'unit':u,'unlock':f['reqUnlock'],'operator':'any_of','conditions':conditions})
   item['requirements']=requirements
  item=enrich(item,index,economy,ROOT,REPO);generated[key]=item
  coverage[key]={'country':country,'branch':branch,'raw_shop':len(raw_shop),'visible':len(in_shop),'excluded':excluded,'unplaced':extra,'columns':len(columns),'research_columns':item['layout']['research_columns'],'groups':sum(bool(n['folder']) for c in columns for n in c['nodes']),'category_missing':[u for u in in_shop if not units[u]['category']]}
  save(WORK/('exports/trees/'+key+'_tree_testing.json'),item)
 tree=generated['usa_army'];raw_shop_count=tree['raw_shop_count'];in_shop={u for c in tree['columns'] for n in c['nodes'] for u in n['units']};excluded=tree['excluded'];extra=tree['unplaced']
 save(WORK/'reports/tree-coverage.json',{'game_version':version,'trees':coverage,'deployed':list(DEPLOY_TREES),'note':'All shop branches generated; only three demo trees packaged. Structural verification is separate from whole-site asset and live-limit certification.'})
 # A small real vehicle record demonstrates shared mod lookup; no display strings/icons here.
 sample={'schema':1,'kind':'vehicle_modifications','game_version':version,'unit':'us_m1a2_abrams',**local['us_m1a2_abrams']}
 out=WIKI;out.mkdir(exist_ok=True);pages=[];page_contents={}
 def page(title,content,model,filename):
  target=out/'pages'/filename;target.parent.mkdir(exist_ok=True);target.write_text(content,encoding='utf-8')
  pages.append({'title':title,'model':model,'file':'wiki/pages/'+filename,'bytes':len(content.encode()),'owner':'generated'})
  page_contents[title]=content
 for filename,obj in [('vehicles_index_testing.json',index),('modifications_index_testing.json',modindex),*[(key+'_tree_testing.json',generated[key]) for key in DEPLOY_TREES],('us_m1a2_modifications_testing.json',sample)]:
  content=dump(obj)
  if max(len(content.encode()),len(json.dumps(obj,ensure_ascii=False,indent=4).encode()))>=MAX:raise ValueError(filename+' exceeds site article limit (compact or formatted)')
  page(PREFIX+'/data/'+filename,content,'json',filename)
 # Ship the article/component dependencies with the same testing import.
 from vehicle_page import write_output, load_json, merge_ordnance_pages
 article_routes={}
 article_config=load_json(ROOT/'config/vehicle-examples.json')
 if article_config['namespace']!='WTJ':raise ValueError('Formal article namespace must be WTJ')
 article_page_titles=set()
 for example in article_config['vehicles']:
  code,folder=example['id'],example['folder']
  bundle=write_output(code,article_config['namespace'],WIKI/folder,REPO)
  for item in bundle['pages']:
   if item['title'].endswith(('/user-content','/basic-info','/player-content')) or item.get('owner')!='generated':
    raise ValueError('常规构建不得包含玩家编辑页：'+item['title'])
   existing=next((p for p in pages if p['title']==item['title']),None)
   if existing:
    if '/data/ordnance/' in item['title'] and existing['model']==item['model']=='json':
     merged=merge_ordnance_pages(page_contents[item['title']],item['content'])
     (ROOT/existing['file']).write_text(merged,encoding='utf-8')
     existing['bytes']=len(merged.encode('utf-8'));page_contents[item['title']]=merged
     article_page_titles.add(item['title']);continue
    if page_contents[item['title']]!=item['content'] or existing['model']!=item['model']:
     raise ValueError('重复页面标题内容不一致：'+item['title'])
    article_page_titles.add(item['title']);continue
   filename=('article_vehicle_'+code+'.wiki' if item['title']==code
             else 'article_'+item['file'].replace('/','_'))
   page(item['title'],item['content'],item['model'],filename)
   article_page_titles.add(item['title'])
  article_routes[code]=code
  units[code]['local_page']=article_routes[code]
 save(out/'pages/vehicles_index_testing.json',index)
 for item in pages:
  if item['title']==PREFIX+'/data/vehicles_index_testing.json':item['bytes']=(ROOT/item['file']).stat().st_size
 page('模块:'+PREFIX+'/catalogue',(ROOT/'src/catalogue.lua').read_text(encoding='utf-8'),'Scribunto','catalogue.lua')
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8').replace('}}','} }')
 page('模板:'+PREFIX+'/styles','<includeonly>{{ResourceLoader|'+PREFIX+'}}\n{{#css:\n'+css+'\n}}</includeonly>','wikitext','styles.wiki')
 page('MediaWiki:'+PREFIX+'.js',(ROOT/'src/tree.js').read_text(encoding='utf-8'),'javascript','tree_testing.js')
 for title,fn in [*[(key+'_tree_testing','tree') for key in DEPLOY_TREES],('us_m1a2_modifications_testing','modifications'),('diagnostics_testing','check')]:
  content='__NOINDEX__\n__NOTOC__\n{{'+PREFIX+'/styles}}\n{{#invoke:'+PREFIX+'/catalogue|'+fn+('|tree='+title.removesuffix('_testing') if fn=='tree' else '')+'}}\n'
  if fn=='modifications':content='__NOINDEX__\n{{'+PREFIX+'/modifications|id=il_leopard_2a6_hel}}\n'
  page(PREFIX+'/'+title,content,'wikitext',title+'.wiki')
 # Full USA per-unit costs/positions are an offline export, not read by the tech tree.
 for key in article_config['trees']:
  page(PREFIX+'/data/'+key+'_tree_testing.json',dump(generated[key]),'json',key+'_tree_testing.json')
  page(PREFIX+'/'+key+'_tree_testing','__NOINDEX__\n__NOTOC__\n{{'+PREFIX+'/styles}}\n{{#invoke:'+PREFIX+'/catalogue|tree|tree='+key+'_tree}}\n','wikitext',key+'_tree_testing.wiki')
 save(WORK/'exports/usa_army_local_modifications.json',{'game_version':version,'records':{u:local[u] for u in sorted(us)}})
 upload={}
 for folder in (example['folder'] for example in article_config['vehicles']):
  for filename,info in load_json(WIKI/folder/'manifest.json')['uploads'].items():
   src=Path(info['source'])
   target=WIKI/'uploads'/filename
   shutil.copyfile(WIKI/folder/'uploads'/filename,target)
   # The isolated article exporter may transform the hero image.
   asset=WORK/'assets'/filename
   shutil.copyfile(target,asset)
   upload[filename]='@work/assets/'+filename
 for item in sample['modifications']:
  r=registry[item['ref']];icons=r['icons'];icon=icon_registry.get(icons.get('image_tank') or icons.get('image'))
  if icon and icon['source']:
   filename=icon['file'];shutil.copyfile(REPO/icon['source'],WORK/'assets'/filename);upload[filename]=icon['source']
 report={'game_version':version,'global_vehicles':len(units),'global_groups':len(groups),'global_modifications':len(registry),'base_modifications':len(defs),'override_variants':len(variants),'usa_ground_total':len(us),'usa_raw_shop_total':raw_shop_count,'usa_shop_total':len(in_shop),'excluded':excluded,'usa_unplaced':extra,'tree_examples':{k:coverage[k] for k in DEPLOY_TREES},'missing_description_count':sum(r['description'] is None for r in registry.values()),'unresolved_icons':unresolved_icons,'pages':pages,'uploads':upload,'live_wiki_written':False}

 for obsolete in ('WTJTreeTesting_us_m551_football.png','WTJTreeTesting_us_m8_scott_snowball.png'):
  old=WIKI/'uploads'/obsolete
  if old.exists():shutil.move(str(old),str(WORK/'assets'/obsolete))
 for filename,source in upload.items():shutil.copyfile((ROOT/source[1:]) if source.startswith('@') else REPO/source,WIKI/'uploads'/filename)
 for key in DEPLOY_TREES:
  item=generated[key];visible={u for c in item['columns'] for n in c['nodes'] for u in n['units']}
  used=visible | {n['folder'] for c in item['columns'] for n in c['nodes'] if n['folder']}
  for code in used:
   asset=item['assets'][code]
   if not asset['remote'] and asset['local']:
    filename=asset['file'];shutil.copyfile(WORK/'assets'/asset['local'],WIKI/'uploads'/filename)
    upload[filename]='@work/assets/'+asset['local']
 for filename in ('WTJTreeTesting_folder.png','WTJTreeTesting_folder_prem.png'):
  shutil.copyfile(WORK/'assets'/filename,WIKI/'uploads'/filename)
  upload[filename]='@work/assets/'+filename
 # Retire stale generated uploads when a naming policy changes.
 current_pages={Path(p['file']).name for p in pages}
 stale=[p for p in (WIKI/'uploads').iterdir() if p.name not in upload]
 stale += [p for p in (WIKI/'pages').iterdir() if p.is_file() and p.name not in current_pages]
 if stale:
  import uuid
  archive=WORK/'history'/('obsolete-generated-uploads-'+uuid.uuid4().hex[:8]);archive.mkdir(parents=True)
  for p in stale:
   retired=archive/p.parent.name/p.name;retired.parent.mkdir(exist_ok=True)
   shutil.move(str(p),str(retired))
 save(out/'manifest.json',report)
 sources=['char.vromfs.bin_u/config/shop.blkx','char.vromfs.bin_u/config/wpcost.blkx','char.vromfs.bin_u/config/unittags.blkx','char.vromfs.bin_u/config/modifications.blkx','lang.vromfs.bin_u/lang/units.csv','lang.vromfs.bin_u/lang/units_modifications.csv','lang.vromfs.bin_u/lang/units_weaponry.csv']
 save(WORK/'reports/sources.json',{p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in sources})
 sections=[];lines=['# 精确页面与文件清单','','全部页面使用 WTJTreeTesting 前缀。JSON 必须使用 json 内容模型。','','| 页面名 | 模型 | 完整内容 |','|---|---|---|']
 ns='http://www.mediawiki.org/xml/export-0.11/';ET.register_namespace('',ns);xml=ET.Element('{'+ns+'}mediawiki',{'version':'0.11'})
 site=ET.SubElement(xml,'{'+ns+'}siteinfo')
 for key,value in [('sitename','War Thunder BWiki offline testing bundle'),('dbname','warthunder'),('base','https://wiki.biligame.com/warthunder/'),('generator','WTJTreeTesting offline builder'),('case','first-letter')]:ET.SubElement(site,'{'+ns+'}'+key).text=value
 namespaces=ET.SubElement(site,'{'+ns+'}namespaces')
 for number,name in [(0,''),(2,'用户'),(6,'文件'),(8,'MediaWiki'),(10,'模板'),(828,'模块')]:ET.SubElement(namespaces,'{'+ns+'}namespace',{'key':str(number),'case':'first-letter'}).text=name
 for p in pages:
  source=(ROOT/p['file']).read_text(encoding='utf-8');lines.append('| `'+p['title']+'` | '+p['model']+' | ['+Path(p['file']).name+']('+str(Path(p['file']).relative_to('wiki')).replace('\\','/')+') |')
  sections.append('<details><summary>'+html.escape(p['title'])+' · '+p['model']+'</summary><textarea readonly rows="12">'+html.escape(source)+'</textarea></details>')
  pe=ET.SubElement(xml,'{'+ns+'}page');ET.SubElement(pe,'{'+ns+'}title').text=p['title'];ET.SubElement(pe,'{'+ns+'}ns').text=str(828 if p['model']=='Scribunto' else 10 if p['title'].startswith('模板:') else 8 if p['title'].startswith('MediaWiki:') else 2 if p['title'].startswith('用户:') else 0);rev=ET.SubElement(pe,'{'+ns+'}revision');ET.SubElement(rev,'{'+ns+'}model').text=p['model'];ET.SubElement(rev,'{'+ns+'}format').text={'json':'application/json','Scribunto':'text/plain','wikitext':'text/x-wiki','javascript':'text/javascript','css':'text/css'}[p['model']];ET.SubElement(rev,'{'+ns+'}text').text=source
  rev.insert(0,ET.Element('{'+ns+'}timestamp'));rev[0].text=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  textnode=rev.find('{'+ns+'}text');textnode.set('{http://www.w3.org/XML/1998/namespace}space','preserve');textnode.set('bytes',str(len(source.encode('utf-8'))))
 ET.ElementTree(xml).write(out/'import-testing.xml',encoding='utf-8',xml_declaration=True)
 shutil.copyfile(out/'import-testing.xml',out/'WTJTreeTesting-all-testing.xml')
 from install_helper import TREE_FILES, render
 tree_titles={p['title'] for p in pages if Path(p['file']).name in TREE_FILES}
 tree_xml=ET.Element('{'+ns+'}mediawiki',{'version':'0.11'})
 for pe in xml:
  if pe.tag!='{'+ns+'}page':continue
  if pe.find('{'+ns+'}title').text in tree_titles:tree_xml.append(pe)
 ET.ElementTree(tree_xml).write(out/'import-tree-only.xml',encoding='utf-8',xml_declaration=True)
 update=ET.Element('{'+ns+'}mediawiki',{'version':'0.11'})
 update_titles={PREFIX+'/data/vehicles_index_testing.json',*[PREFIX+'/data/'+key+'_tree_testing.json' for key in DEPLOY_TREES],*[PREFIX+'/'+key+'_tree_testing' for key in DEPLOY_TREES],'模块:'+PREFIX+'/catalogue','模板:'+PREFIX+'/styles','MediaWiki:'+PREFIX+'.js'}
 update_titles.update(article_page_titles)
 if any(title.endswith(('/user-content','/basic-info','/player-content')) for title in update_titles):raise ValueError('更新集合误含玩家编辑子页。')
 for pe in xml:
  if pe.tag!='{'+ns+'}page':continue
  if pe.find('{'+ns+'}title').text in update_titles:update.append(pe)
 ET.ElementTree(update).write(out/'import-update.xml',encoding='utf-8',xml_declaration=True)
 lines+=['','## M1A2 改装图标上传清单','','科技树不需要上传图片；只有改装演示用到以下图标。']
 for filename in upload:
  if not filename.startswith('WTJTreeTesting_folder'):lines.append('- `文件:'+filename+'` ← [本地文件](uploads/'+filename+')')
 lines+=['','## 科技树图片与脚本','','载具与卡片底板复用已有 BWiki 图片；另上传以下两张从已保存官方 CSS 解码的折叠底板：','','- `文件:WTJTreeTesting_folder.png` ← [图片](uploads/WTJTreeTesting_folder.png)','- `文件:WTJTreeTesting_folder_prem.png` ← [图片](uploads/WTJTreeTesting_folder_prem.png)','','`tree_testing.js` 对应 MediaWiki:WTJTreeTesting.js，由样式模板中的 ResourceLoader 标记加载，见 ../docs/DEPLOYMENT.md。无需个人 JS/CSS；创建 MediaWiki 脚本页需要相应权限。']
 lines=[x.replace('科技树不需要上传图片；只有改装演示用到以下图标。','以下图标只用于改装演示；科技树新增图标另列于文末。') for x in lines]
 lines+=['','## 中国空军与德国近岸海军新增图片','','部署助手：MULTI-TREE.html。完整步骤与限制：../docs/MULTI-TREE.md。']
 for filename in upload:
  if filename in ('WTJTreeTesting_a6m5_zero_china.png','WTJTreeTesting_pe-2-359_china.png','WTJTreeTesting_germ_s_700_s_706.png'):lines.append('- `文件:'+filename+'` ← [本地图片](uploads/'+filename+')')
 (WIKI/'PAGE-LIST.md').write_text('\n'.join(lines),encoding='utf-8')
 render(pages)
 from testing_cleanup import write_cleanup
 write_cleanup(WIKI/'Cleanup', [p['title'] for p in pages] + ['文件:'+name for name in upload],
               active_contents=[(ROOT/p['file']).read_text(encoding='utf-8') for p in pages])
 with (WIKI/'PAGE-LIST.md').open('a',encoding='utf-8') as stream:
  stream.write('\n\n## 历史测试页清理（每次导入必做）\n\n见 [清理要求](Cleanup/CLEANUP.md) 和 [管理员入口](Cleanup/CLEANUP.html)。当前测试标题须先迁移到确定的正式标题，验收后删除；不能把此历史原型作为默认正式交付。\n')
 print(dump({k:v for k,v in report.items() if k not in ['pages','unresolved_icons','uploads']}))
if __name__=='__main__':main()
