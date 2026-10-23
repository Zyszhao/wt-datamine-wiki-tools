"""Build production tree import packages from local datamine and read-only site evidence.

Never edits the Wiki. Keep snapshots and all generated materials outside Git.
"""
import csv,hashlib,html,json,re,shutil,sys,time
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from paths import ROOT,REPO,WORK,WIKI,VENDOR
from tree_specs import COUNTRIES,BRANCHES,tree_id
from prepare_assets import extract_contract
from tree_layout import enrich

BASE='https://wiki.biligame.com/warthunder/'
OUT=WIKI/'production';EVIDENCE=ROOT/'evidence/production'
PREFIX='WTJ';NS='http://www.mediawiki.org/xml/export-0.11/'
LAST_REQUEST=0
def dump(x):return json.dumps(x,ensure_ascii=False,indent=2)+'\n'
def api(**params):
 global LAST_REQUEST
 url=BASE+'api.php?'+urlencode({'format':'json',**params})
 for attempt in range(3):
  try:
   time.sleep(max(0,1.5-(time.monotonic()-LAST_REQUEST)));LAST_REQUEST=time.monotonic()
   with urlopen(Request(url,headers={'User-Agent':'WTJ-offline-export/1.0'}),timeout=45) as r:return json.load(r)
  except Exception:
   if attempt==2:raise
   time.sleep(1+attempt)
def query_titles(titles):
 result={}
 unique=list(dict.fromkeys(titles))
 for start in range(0,len(unique),40):
  batch=unique[start:start+40]
  cache=EVIDENCE/('query-'+hashlib.sha256('\n'.join(batch).encode()).hexdigest()[:20]+'.json')
  if cache.exists():data=json.loads(cache.read_text(encoding='utf-8'))
  else:
   data=api(action='query',titles='|'.join(batch),prop='info|imageinfo',iiprop='url');cache.write_text(dump(data),encoding='utf-8')
  normalized={x['from']:x['to'] for x in data.get('query',{}).get('normalized',[])}
  pages={x['title']:x for x in data['query']['pages'].values()}
  for title in batch:result[title]=pages.get(normalized.get(title,title),{'title':title,'missing':''})
 return result
def fetch(title):
 data=api(action='parse',page=title,prop='text|wikitext|revid|categories')
 if 'error' in data:raise ValueError((title,data['error']))
 return data['parse']
def snapshot():
 EVIDENCE.mkdir(parents=True,exist_ok=True)
 shop=json.loads((REPO/'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))
 targets={tree_id(country,branch):COUNTRIES[country.removeprefix('country_')]+('陆军' if branch=='army' else BRANCHES[branch]) for country,branches in shop.items() for branch in branches if branch!='helicopters'}
 info=query_titles(list(targets.values())+['MediaWiki:Common.js','模板:ResourceLoader'])
 for key,title in targets.items():
  if 'missing' in info[title]:raise ValueError('Expected existing tree page missing: '+title)
 def task(pair):
  key,title=pair
  path=EVIDENCE/(key+'.json')
  if not path.exists():
   data=fetch(title);path.write_text(dump(data),encoding='utf-8')
  return key
 for pair in targets.items():print('snapshot',task(pair),flush=True)
 for title,name in [('MediaWiki:Common.js','common-js'),('模板:ResourceLoader','resource-loader')]:
  path=EVIDENCE/(name+'.json')
  if not path.exists():
   data=api(action='query',titles=title,prop='revisions',rvprop='content|ids',rvslots='main');path.write_text(dump(data),encoding='utf-8')
 (EVIDENCE/'targets.json').write_text(dump(targets),encoding='utf-8')

def xml_file(pages,path):
 ET.register_namespace('',NS);root=ET.Element('{'+NS+'}mediawiki',{'version':'0.11'})
 site=ET.SubElement(root,'{'+NS+'}siteinfo')
 for key,value in [('sitename','War Thunder BWiki'),('dbname','warthunder'),('base',BASE),('generator','WTJ production exporter'),('case','first-letter')]:ET.SubElement(site,'{'+NS+'}'+key).text=value
 spaces=ET.SubElement(site,'{'+NS+'}namespaces')
 for key,name in [(0,''),(8,'MediaWiki'),(10,'模板'),(828,'模块')]:ET.SubElement(spaces,'{'+NS+'}namespace',{'key':str(key),'case':'first-letter'}).text=name
 stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
 for p in pages:
  node=ET.SubElement(root,'{'+NS+'}page')
  for key,value in [('title',p['title']),('ns',str(828 if p['model']=='Scribunto' else 8 if p['title'].startswith('MediaWiki:') else 10 if p['title'].startswith('模板:') else 0))]:ET.SubElement(node,'{'+NS+'}'+key).text=value
  rev=ET.SubElement(node,'{'+NS+'}revision')
  for key,value in [('timestamp',stamp),('model',p['model']),('format',{'json':'application/json','javascript':'text/javascript','Scribunto':'text/plain','wikitext':'text/x-wiki'}[p['model']])]:ET.SubElement(rev,'{'+NS+'}'+key).text=value
  ET.SubElement(rev,'{'+NS+'}text',{'bytes':str(len(p['content'].encode())), '{http://www.w3.org/XML/1998/namespace}space':'preserve'}).text=p['content']
 ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)

def import_exports(paths):
 """Read current-revision exports while retaining separately captured rendered evidence."""
 EVIDENCE.mkdir(parents=True,exist_ok=True); exported={}
 for path in paths:
  root=ET.parse(path).getroot();ns={'m':root.tag.split('}')[0].strip('{')}
  for node in root.findall('m:page',ns):
   title=node.findtext('m:title',namespaces=ns);rev=node.find('m:revision',ns)
   exported[title]={'content':rev.findtext('m:text',default='',namespaces=ns),'revid':rev.findtext('m:id',namespaces=ns)}
 shop=json.loads((REPO/'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))
 targets={tree_id(c,b):COUNTRIES[c.removeprefix('country_')]+('陆军' if b=='army' else BRANCHES[b]) for c,bs in shop.items() for b in bs if b!='helicopters'}
 for key,title in targets.items():
  source=exported[title];path=EVIDENCE/(key+'.json')
  old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
  # Historical parsed HTML is evidence, not a replacement for the newly exported source.
  old.update(title=title,wikitext={'*':source['content']},revid=source['revid'])
  path.write_text(dump(old),encoding='utf-8')
 for title,key in [('MediaWiki:Common.js','common-js'),('模板:ResourceLoader','resource-loader')]:
  data={'query':{'pages':{'export':{'title':title,'revisions':[{'slots':{'main':{'*':exported[title]['content']}}}]}}}}
  (EVIDENCE/(key+'.json')).write_text(dump(data),encoding='utf-8')
 (EVIDENCE/'targets.json').write_text(dump(targets),encoding='utf-8')
 (EVIDENCE/'exported-sources.json').write_text(dump(exported),encoding='utf-8')

def source_mapping(index,snapshots):
 """Reproduce only direct Tr lookups; never pretend to evaluate arbitrary wikitext."""
 path=EVIDENCE/'exported-sources.json'
 if not path.exists():return {},{}
 sources=json.loads(path.read_text(encoding='utf-8'));text=sources['模板:Tr/db']['content']
 names={};links={}
 for kind,code,value in re.findall(r'\|ct(PN)?-([^|{}\n]+)\|([^|{}\n]+)',text):
  (links if kind else names)[code.strip().lower()]=value.strip()
 lower={u.lower():u for u in index['records']};mapping={};groups={}
 for code in index['records']:
  key=code.lower();name=names.get(key)
  if name or key in links:mapping[code]={'name':name or index['records'][code]['name'],'page':links.get(key,name),'file':code+'.png','link_source':'exported Tr direct lookup'}
 for code in index['groups']:
  if code.lower() in names:groups[code]={'name':names[code.lower()],'file':code+'.png'}
 # Tree-Unit calls have scalar arguments in the captured sources. Reject nested
 # manual values rather than guessing their expansion. Match members inside groups too.
 icons=dict(re.findall(r'\|([^|=\n]+)=\[\[(?:文件|File):([^|\]]+)\|',sources['模板:UnitTypeIcon']['content']))
 for key,data in snapshots.items():
  for call in re.findall(r'\{\{Tree-Unit\|([^{}]*)\}\}',data['wikitext']['*'],re.I):
   args=[x.strip() for x in call.split('|')];code=lower.get(args[0].lower())
   if not code:continue
   row=mapping.setdefault(code,{'file':code+'.png'})
   if len(args)>3 and args[2] in icons:row['type_icon']=icons[args[2]].replace(' ','_')
   elif len(args)>2 and args[2] in icons:row['type_icon']=icons[args[2]].replace(' ','_')
   named=dict(a.split('=',1) for a in args[1:] if '=' in a)
   if named.get('manualname'):row['name']=named['manualname'].strip()
   # The deployed template honours manuallink only in explicit status branches.
   if len(args)>1 and args[1] in ('高级','联队','研发') and named.get('manuallink'):
    row.update(page=named['manuallink'].strip(),link_source='exported Tree-Unit manuallink')
 return mapping,groups

def main():
 if '--export-xml' in sys.argv:
  import_exports([Path(p) for p in sys.argv[sys.argv.index('--export-xml')+1:] if not p.startswith('--')])
 if '--snapshot-file' in sys.argv:
  source=Path(sys.argv[sys.argv.index('--snapshot-file')+1]);captured=json.loads(source.read_text(encoding='utf-8'))
  EVIDENCE.mkdir(parents=True,exist_ok=True)
  assert len(captured['pages'])==34
  for key,data in captured['pages'].items():(EVIDENCE/(key+'.json')).write_text(dump(data),encoding='utf-8')
  for key,data in captured['support'].items():(EVIDENCE/(key+'.json')).write_text(dump(data),encoding='utf-8')
  (EVIDENCE/'targets.json').write_text(dump(captured['targets']),encoding='utf-8')
 if '--fetch' in sys.argv:snapshot()
 if '--refresh-rendered' in sys.argv:
  targets=json.loads((EVIDENCE/'targets.json').read_text(encoding='utf-8'))
  for key,title in targets.items():
   path=EVIDENCE/(key+'.json');data=json.loads(path.read_text(encoding='utf-8'))
   cache=EVIDENCE/(key+'-live.html')
   if not cache.exists():
    time.sleep(1.5)
    with urlopen(Request(BASE+'index.php?'+urlencode({'title':title}),headers={'User-Agent':'WTJ-offline-export/1.0'}),timeout=30) as response:body=response.read().decode('utf-8')
    if 'tree-item' not in body:raise ValueError('Not a rendered tree: '+title)
    cache.write_text(body,encoding='utf-8')
   data['text']={'*':cache.read_text(encoding='utf-8')}
   data['rendered_evidence']='read-only public HTML; exported wikitext retained independently'
   path.write_text(dump(data),encoding='utf-8');print('rendered',key,flush=True)
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'pages').mkdir(exist_ok=True);(OUT/'uploads').mkdir(exist_ok=True)
 # These two directories contain only this generator's managed output files.
 # Remove stale uploads so an older run cannot silently enlarge the upload list.
 for path in (OUT/'uploads').iterdir():
  if path.is_file():path.unlink()
 for path in OUT.glob('WTJ-part-*.xml'):path.unlink()
 targets=json.loads((EVIDENCE/'targets.json').read_text(encoding='utf-8'))
 index=json.loads((WIKI/'pages/vehicles_index_testing.json').read_text(encoding='utf-8'))
 economy=json.loads((REPO/'char.vromfs.bin_u/config/wpcost.blkx').read_text(encoding='utf-8'))
 lower={u.lower():u for u in index['records']};mapping={};groups={};files={};snapshots={}
 for key,title in targets.items():
  data=json.loads((EVIDENCE/(key+'.json')).read_text(encoding='utf-8'));snapshots[key]=data
  if data.get('text'):
   v,g,f=extract_contract(data)
   for row in v.values():row['link_source']='saved rendered tree target'
   mapping.update({lower.get(u,u):r for u,r in v.items()});groups.update(g);files.update(f)
 source_vehicles,source_groups=source_mapping(index,snapshots)
 for code,row in source_vehicles.items():
  # Actual rendered targets take priority over Tr; manual overrides in current
  # source take priority over both. Tr supplies only otherwise absent fields.
  target=mapping.setdefault(code,{})
  if row.get('link_source')=='exported Tree-Unit manuallink':target.update(row)
  else:
   for k,v in row.items():target.setdefault(k,v)
 for code,row in source_groups.items():groups.setdefault(code,row)
 for g in groups.values():g['members']=[lower.get(u,u) for u in g.get('members',[])]
 # Confirm destinations, rather than treating red links in the old tree as existing articles.
 trees={key:json.loads((WORK/('exports/trees/'+key+'_tree_testing.json')).read_text(encoding='utf-8')) for key in targets}
 codes={u for tree in trees.values() for col in tree['columns'] for n in col['nodes'] for u in n['units']}
 candidates=[]
 for code,r in mapping.items():
  if r.get('page'):candidates.append(r['page'])
 # Existing old tree destinations first; only query game-name alternatives for unresolved records.
 resolved_path=EVIDENCE/'resolved-articles.json'
 resolved=json.loads(resolved_path.read_text(encoding='utf-8')) if resolved_path.exists() else query_titles(candidates)
 resolved.update(query_titles([t for t in candidates if t not in resolved]))
 alternatives=[t for code in codes if not mapping.get(code,{}).get('page') or 'missing' in resolved.get(mapping[code]['page'],{'missing':''}) for t in (index['records'][code]['name'],code)]
 resolved.update(query_titles([t for t in alternatives if t not in resolved]));resolved_path.write_text(dump(resolved),encoding='utf-8')
 missing_links=[]
 for code,r in index['records'].items():
  item=mapping.setdefault(code,{})
  item['legacy_page']=item.get('page')
  choices=[item.get('page'),r['name'],code]
  destination=next((resolved[t]['title'] for t in choices if t in resolved and 'missing' not in resolved[t] and resolved[t].get('ns')==0),None)
  # Preserve exact legacy destinations even when the API reports them missing;
  # replacing a disambiguated title with a display name can point at another unit.
  item['page']=destination or item.get('page') or r['name']
  item['link_verified']=bool(destination)
 # Query missing image titles in batches, reusing existing site files wherever available.
 groupcodes={n['folder'] for tree in trees.values() for c in tree['columns'] for n in c['nodes'] if n['folder']}
 image_titles=['文件:'+mapping.get(u,groups.get(u,{})).get('file',u+'.png') for u in codes|groupcodes if mapping.get(u,groups.get(u,{})).get('file',u+'.png').casefold() not in files]
 image_cache=EVIDENCE/'resolved-images.json'
 images=json.loads(image_cache.read_text(encoding='utf-8')) if image_cache.exists() else query_titles(image_titles)
 image_cache.write_text(dump(images),encoding='utf-8')
 for title,data in images.items():
  if 'missing' not in data and data.get('imageinfo'):
   filename=data['title'].split(':',1)[1].replace(' ','_');files[filename.casefold()]={'file':filename,'url':data['imageinfo'][0]['url']}
 for code in codes|groupcodes:
  source=REPO/'atlases.vromfs.bin_u/units'/(code.lower()+'.png')
  if source.exists():shutil.copyfile(source,WORK/'assets'/(code+'.png'))
 presentation={'vehicles':mapping,'groups':groups,'files':files}
 (EVIDENCE/'presentation-map.json').write_text(dump(presentation),encoding='utf-8')
 pages=[];rollback=[];reports={};uploads={}
 def page(title,model,content,filename):
  if model=='json' and max(len(content.encode()),len(json.dumps(json.loads(content),ensure_ascii=False,indent=4).encode()))>=2097152:raise ValueError('JSON exceeds limit: '+title)
  (OUT/'pages'/filename).write_text(content,encoding='utf-8');pages.append({'title':title,'model':model,'content':content,'file':filename,'bytes':len(content.encode())})
 for code,g in index['groups'].items():
  if code in groups and groups[code].get('name') and groups[code]['name']!=code:g['name']=groups[code]['name']
 page(PREFIX+'/data/vehicles_index.json','json',json.dumps(index,ensure_ascii=False,separators=(',',':'))+'\n','vehicles_index.json')
 for key,tree in trees.items():
  tree=enrich(tree,index,economy,ROOT,REPO,presentation)
  visible={u for c in tree['columns'] for n in c['nodes'] for u in n['units']}
  used=visible|{n['folder'] for c in tree['columns'] for n in c['nodes'] if n['folder']}
  tree['assets']={u:v for u,v in tree['assets'].items() if u in used}
  tree['presentation']={u:v for u,v in tree['presentation'].items() if u in visible}
  for code in visible:
   if not mapping[code]['link_verified']:missing_links.append({'tree':key,'code':code,'fallback':mapping[code]['page'],'source':mapping[code].get('link_source','game Chinese name')})
  for code,asset in tree['assets'].items():
   if code not in used:continue
   if not asset['remote'] and asset['local']:
    filename=code+'.png';shutil.copyfile(WORK/'assets'/asset['local'],OUT/'uploads'/filename);asset['file']=filename;uploads[filename]=code
   elif not asset['remote']:
    asset['file']=code+'.png'
  for col in tree['columns']:
   for node in col['nodes']:
    folder=node['folder']
    if folder and not tree['assets'][folder].get('remote') and not tree['assets'][folder].get('local'):
     first=next((u for u in node['units'] if tree['assets'][u].get('remote') or tree['assets'][u].get('local')),None)
     if first:tree['assets'][folder]={**tree['assets'][first],'fallback_member':first}
  page(PREFIX+'/data/'+key+'_tree.json','json',json.dumps(tree,ensure_ascii=False,separators=(',',':'))+'\n',key+'_tree.json')
  old=snapshots[key]['wikitext']['*'];match=re.search(r'\{\{Tree-Start\b.*?\{\{Tree-End\s*\}\}',old,re.S|re.I)
  if not match:raise ValueError('Cannot safely identify existing tree region: '+targets[key])
  replacement='{{WTJ/styles}}\n{{#invoke:WTJ/catalogue|tree|tree='+key+'_tree|links=existing}}'
  content=old[:match.start()]+replacement+old[match.end():]
  page(targets[key],'wikitext',content,key+'.wiki');rollback.append({'title':targets[key],'model':'wikitext','content':old})
  reports[key]={'title':targets[key],'visible':tree['visible_count'],'old_revision':snapshots[key].get('revid'),'verified_links':sum(mapping[u]['link_verified'] for u in visible),'groups':sum(bool(n['folder']) for c in tree['columns'] for n in c['nodes'])}
 lua=(ROOT/'src/catalogue.lua').read_text(encoding='utf-8').replace("local prefix='WTJTreeTesting'","local prefix='WTJ'").replace("..'_testing.json'","..'.json'")
 lua=lua.replace("local existing=args.links=='existing'","local existing=args.links~='testing'")
 lua=lua.replace("prefix..'/vehicle/'..code..'_testing'","r.name")
 lua=lua.replace('WTJTreeTesting_folder_prem.png','Item_group_prem.png').replace('WTJTreeTesting_folder.png','Item_group.png')
 lua=lua.replace('现有 BWiki 页面（缺映射时回退测试页）','现有 BWiki 页面（缺映射时回退中文名称）').replace('独立测试页面','中文名称页面')
 lua=lua.replace("exp_torpedo_boat='PT_icon.png'", "exp_destroyer='DD_icon.png',exp_cruiser='CL_icon.png',exp_gun_boat='PC_icon.png',exp_torpedo_boat='PT_icon.png'")
 # Production package contains trees only, without the unrelated M1A2 demo APIs.
 lua=lua.split('\nfunction p.modifications()',1)[0]+'\nreturn p\n'
 lua=re.sub(r'<span class="wtt-search-hint">.*?</span>','',lua)
 page('模块:WTJ/catalogue','Scribunto',lua,'catalogue.lua')
 js=(ROOT/'src/tree.js').read_text(encoding='utf-8')
 js=re.sub(r"root\.querySelector\('\.wtt-search-hint'\)\.textContent=.*?;root\.classList",'root.classList',js)
 if "querySelector('.wtt-search-hint')" in js:raise ValueError('Hint removal incomplete')
 page('MediaWiki:WTJ.js','javascript',js,'tree.js')
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8').replace('}}','} }')
 page('模板:WTJ/styles','wikitext','<includeonly>{{ResourceLoader|WTJ}}\n{{#css:\n'+css+'\n}}</includeonly>','styles.wiki')
 # Existing site files, confirmed by read-only imageinfo. A renamed File without
 # redirect must be referenced at its new title; no replacement upload is needed.
 background_cache=EVIDENCE/'background-files-current.json'
 if not background_cache.exists():
  background_cache.write_text(dump(api(action='query',titles='|'.join('文件:'+f for f in ('Item group.png','Item group prem.png','Item own.png','Item prem.png','Item squad.png')),prop='imageinfo',iiprop='url|size')),encoding='utf-8')
 background_data=json.loads(background_cache.read_text(encoding='utf-8'))
 background_files={}
 for entry in background_data['query']['pages'].values():
  assert 'missing' not in entry and entry.get('imageinfo'),entry['title']
  filename=entry['title'].split(':',1)[1].replace(' ','_')
  background_files[filename]={'file':filename,'url':entry['imageinfo'][0]['url']}
 assert set(background_files)=={'Item_group.png','Item_group_prem.png','Item_own.png','Item_prem.png','Item_squad.png'}
 (OUT/'existing-backgrounds.json').write_text(dump(background_files),encoding='utf-8')
 files.update({k.casefold():v for k,v in background_files.items()})
 (EVIDENCE/'presentation-map.json').write_text(dump({'vehicles':mapping,'groups':groups,'files':files}),encoding='utf-8')
 # Production runtime must not depend on test page names or image uploads.
 for p in pages:
  if p['model']=='Scribunto':
   p['bytes']=len(p['content'].encode('utf-8'))
  if 'WTJTreeTesting' in p['content'] or '_testing' in p['title']:raise ValueError('Testing dependency: '+p['title'])
 xml_file(pages,OUT/'WTJ-all-trees-production.xml');xml_file(rollback,OUT/'WTJ-rollback-existing-trees.xml')
 # Bounded optional slices: complete all-in-one XML remains the requested main deliverable.
 slices=[];batch=[];size=0
 ordered=sorted(pages,key=lambda p:0 if p['model'] in ('json','Scribunto','javascript') or p['title'].startswith('模板:') else 1)
 for p in ordered:
  if batch and (len(batch)>=15 or size+p['bytes']>1500000):slices.append(batch);batch=[];size=0
  batch.append(p);size+=p['bytes']
 if batch:slices.append(batch)
 for i,batch in enumerate(slices,1):xml_file(batch,OUT/f'WTJ-part-{i:02d}-of-{len(slices):02d}.xml')
 missing_images=[{'tree':key,'code':code} for key in trees for code,asset in json.loads((OUT/'pages'/(key+'_tree.json')).read_text(encoding='utf-8'))['assets'].items() if not asset.get('remote') and not asset.get('local')]
 manifest={'game_version':index['game_version'],'prefix':PREFIX,'trees':reports,'page_count':len(pages),'pages':[{k:v for k,v in p.items() if k!='content'} for p in pages],'uploads':uploads,'unverified_links':missing_links,'missing_images':missing_images,'slices':len(slices),'online_written':False,'common_js_replaced':False}
 with (OUT/'link-audit.csv').open('w',encoding='utf-8-sig',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(['game_code','game_zh_name','legacy_target','deployed_target','api_exists','mapping_source'])
  for code in sorted(codes):
   row=mapping[code];writer.writerow([code,index['records'][code]['name'],row.get('legacy_page'),row['page'],row['link_verified'],row.get('link_source','game Chinese name')])
 (OUT/'manifest.json').write_text(dump(manifest),encoding='utf-8')
 validate(pages,trees,index,OUT)
 common_data=json.loads((EVIDENCE/'common-js.json').read_text(encoding='utf-8'))
 common=next(iter(common_data['query']['pages'].values()))['revisions'][0]['slots']['main']['*']
 loader_data=json.loads((EVIDENCE/'resource-loader.json').read_text(encoding='utf-8'))
 loader=next(iter(loader_data['query']['pages'].values()))['revisions'][0]['slots']['main']['*']
 assert '.resourceLoader' in common and 'mw.loader.load' in common and 'MediaWiki:' in common and 'resourceLoader' in loader
 (OUT/'common-js-compatibility.json').write_text(dump({'existing_loader_verified':True,'common_js_sha256':hashlib.sha256(common.encode()).hexdigest(),'replacement_common_js':False,'global_script':'MediaWiki:WTJ.js','trigger':'模板:WTJ/styles → 模板:ResourceLoader → existing MediaWiki:Common.js loader','personal_scripts_required':False}),encoding='utf-8')
 instructions(pages,manifest,slices)
 print(dump({'trees':len(trees),'pages':len(pages),'vehicles':len(codes),'missing_article_links':len(missing_links),'uploads':len(uploads),'xml':str(OUT/'WTJ-all-trees-production.xml')}))

def instructions(pages,manifest,slices):
 lines=['# WTJ 正式科技树部署包','','游戏数据版本：'+manifest['game_version']+'。生成日期：'+datetime.now(timezone.utc).astimezone().isoformat()+'.','',
 '## 导入方式','','主文件：WTJ-all-trees-production.xml，包含 34 棵非直升机树、全局简化索引、本树数据库、模块、样式模板与全站脚本，共 72 页。',
 '在 Special:Import 上传 XML，按原命名空间导入，不将所有页重映射到同一空间。没有导入权限或 MediaWiki 脚本权限时请由有权限者执行。此包只在本地生成，未写入线上。',
 '若完整 XML 超过本站上传或处理限制，使用编号 WTJ-part-*.xml 按序导入，全部片完成后再验收。分片每片最多 15 页、页面文本合计最多 1500000 字节；最终 XML 文件额外含转义/包装开销，以各文件实际大小为准。',
 '','## 页面与兼容性','','34 个正式科技树页面采用原名并仅替换旧 Tree-Start 至 Tree-End 区域，保留切换导航、分类和其他内容。没有创建新载具文章，没有改直升机页面。回退文件 WTJ-rollback-existing-trees.xml 保存这 34 页抓取时的源码，仅供需恢复时导入。',
 '新增支持页面使用 WTJ 前缀，不依赖测试页。MediaWiki:WTJ.js 为全站可用资源，由模板:WTJ/styles 的 ResourceLoader 标记通过本站已有 MediaWiki:Common.js 加载，不替换全站 Common.js、不要求用户 common.js。',
 '右上角的数量/展开提示已移除；筛选时仍有结果栏。链接优先采用旧树实际渲染目标，当前源码手动链接优先于其余映射，Tr 仅补充缺项。再核对旧目标及游戏中文名/代码备选的存在性；未确认时保留原目标，缺原目标时回退中文名。详见 link-audit.csv 和 manifest.json，不把 API 返回缺失的目标伪报为已存在。',
 '本包 '+str(len(manifest['unverified_links']))+' 个载具目标未获 API 存在性确认；这不等于全部由本次改动新增的红链。原页面实际输出亦含这类链接，包中保留并逐项报告，尚不能宣布所有载具链接可用。',
 '','## 图片','','XML 只包含页面，不包含二进制文件。仅需上传 uploads/ 中列出的游戏代码命名图片，文件名保持不变，不加 WTJ 前缀。JSON 的 assets.file 与上传名称一致，Lua 按此字段生成 File 内链。',
 '五张背景均复用已存在的本站文件：Item own.png、Item prem.png、Item squad.png、Item group.png、Item group prem.png；模块内使用等价的下划线写法。不再上传 WTJ_folder 或 WTJ_folder_prem，也不依赖已移动且没有重定向的测试文件名。existing-backgrounds.json 记录只读核对结果。',
 '','## 验收','','导入后清除正式科技树页面的解析缓存并强制刷新；用匿名窗口确认筛选栏、三模式 BR、列表、折叠与宽度。全量 Lua 和 XML 回读检查见 validation.json；本地验证不等于生产导入与 Scribunto 内存/时间预算已通过。',
 '','## 原页面替换清单','','| 页面 | 数据键 | 卡片数 | 抓取版本 |','|---|---|---:|---:|']
 for key,r in manifest['trees'].items():lines.append(f"| {r['title']} | {key} | {r['visible']} | {r['old_revision']} |")
 lines+=['','## 上传清单','']+[f'- 文件:{f}' for f in manifest['uploads']]
 (OUT/'DEPLOY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 rows=[]
 upload_rows=''.join('<li><a href="uploads/'+html.escape(f,quote=True)+'">'+html.escape(f)+'</a> · <a target="_blank" rel="noopener" href="'+html.escape(BASE+'index.php?'+urlencode({'title':'Special:Upload','wpDestFile':f}),quote=True)+'">打开本站上传页</a></li>' for f in manifest['uploads'])
 for p in pages:
  url=BASE+'index.php?'+urlencode({'title':p['title'],'action':'edit','contentmodel':p['model']})
  rows.append('<details><summary>'+html.escape(p['title'])+' · '+p['model']+'</summary><a target="_blank" href="'+html.escape(url)+'">打开编辑</a><button onclick="copy(this)">复制全部源码</button><span></span><textarea readonly>'+html.escape(p['content'])+'</textarea></details>')
 (OUT/'INSTALL.html').write_text('<!doctype html><meta charset="utf-8"><title>WTJ 正式科技树部署</title><style>body{max-width:1100px;margin:24px auto;font:15px/1.6 system-ui;padding:16px}details{border:1px solid #ccc;padding:12px;margin:12px 0}textarea{width:100%;height:250px;display:block;box-sizing:border-box}button{margin:10px}</style><h1>34 棵正式科技树部署</h1><p><a href="WTJ-all-trees-production.xml">完整 XML（72 页）</a> · <a href="DEPLOY.md">部署和上传说明</a> · <a href="manifest.json">报告清单</a> · <a href="link-audit.csv">链接核对表</a></p><p>由本站 ResourceLoader 加载 MediaWiki:WTJ.js，无个人脚本设置，不替换全站 Common.js。XML 不携带图片，先按说明上传。没有线上自动保存。</p><p>有 '+str(len(manifest['unverified_links']))+' 个链接目标未获 API 存在性确认；保留旧树目标或按报告回退，不代表全部链接已可用。</p><details><summary>先上传 '+str(len(manifest['uploads']))+' 个图片文件</summary><ul>'+upload_rows+'</ul></details>'+''.join(rows)+'<script>async function copy(b){let t=b.parentElement.querySelector("textarea");t.select();try{await navigator.clipboard.writeText(t.value);b.nextElementSibling.textContent="已复制"}catch(e){b.nextElementSibling.textContent="已全选，请 Ctrl+C"}}</script>',encoding='utf-8')
 target=WORK/'packages/WTJ-all-trees-production.zip'
 with ZipFile(target,'w',ZIP_DEFLATED) as z:
  for path in OUT.rglob('*'):
   if path.is_file():z.write(path,path.relative_to(OUT).as_posix())

def validate(pages,trees,index,out):
 try:from lupa import LuaRuntime
 except ImportError:
  sys.path.insert(0,str(VENDOR));from lupa import LuaRuntime
 lua=LuaRuntime(unpack_returned_tuples=True);bytitle={p['title']:p['content'] for p in pages};reads=[]
 def table(x):
  if isinstance(x,dict):return lua.table_from({k:table(v) for k,v in x.items()})
  if isinstance(x,list):return lua.table_from([table(v) for v in x])
  return x
 def load(title):reads.append(title);return table(json.loads(bytitle[title]))
 lua.globals().load_bridge=load;lua.execute('mw={loadJsonData=function(t) return load_bridge(t) end}')
 module=lua.execute(bytitle['模块:WTJ/catalogue']);rendered={}
 preview=WORK/'preview/production';preview.mkdir(parents=True,exist_ok=True)
 files=json.loads((EVIDENCE/'presentation-map.json').read_text(encoding='utf-8'))['files']
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8')
 shop=json.loads((REPO/'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))
 from tree_policy import exclusion_reason
 tags=json.loads((REPO/'char.vromfs.bin_u/config/unittags.blkx').read_text(encoding='utf-8'))
 for key,tree in trees.items():
  reads.clear();body=module.tree(table({'args':{'tree':key+'_tree','links':'existing'}}))
  assert 'wtr-error' not in body,(key,body)
  assert body.count('class="wtt-card ')==tree['visible_count'],key
  assert 'wtt-search-hint' not in body and '/vehicle/' not in body and '_testing' not in body,key
  assert len(reads)==2,key
  native_reads=list(reads)
  lua.globals().content_bridge=lambda title:bytitle[title]
  lua.globals().decode_bridge=lambda s:table(json.loads(s))
  lua.execute('mw.loadJsonData=nil; mw.title={new=function(t) return {getContent=function() return content_bridge(t) end} end}; mw.text={jsonDecode=function(s) return decode_bridge(s) end}')
  assert module.tree(table({'args':{'tree':key+'_tree','links':'existing'}}))==body,key
  lua.execute('mw.loadJsonData=function(t) return load_bridge(t) end')
  expected=[]
  for col in shop[tree['country']][tree['branch']]['range']:
   nodes=[]
   for code,value in col.items():
    if not isinstance(value,dict):continue
    members=[code] if code in index['records'] else [u for u,v in value.items() if u in index['records'] and isinstance(v,dict)]
    members=[u for u in members if not exclusion_reason(u,tags)]
    if members:nodes.append((None if code in index['records'] else code,members))
   expected.append(nodes)
  assert [[(n['folder'],n['units']) for n in c['nodes']] for c in tree['columns']]==expected,key
  actual=json.loads(bytitle['WTJ/data/'+key+'_tree.json'])
  for code,asset in actual['assets'].items():
   if asset.get('local') and not asset.get('remote'):
    assert (out/'uploads'/asset['file']).is_file(),(key,code,asset['file'])
    assert not asset['file'].startswith(('WTJ_','WTJTreeTesting_')),asset['file']
  assert not any(old in body for old in ('WTJ_folder','WTJTreeTesting_folder')),key
  def image_link(m):
   filename,size=m[1],m[2];asset=next((a for a in actual['assets'].values() if a['file']==filename),None)
   if asset and asset['local']:src='../../assets/'+asset['local']
   elif filename in ('Item_group.png','Item_group_prem.png'):src='../../assets/'+('WTJTreeTesting_folder_prem.png' if filename=='Item_group_prem.png' else 'WTJTreeTesting_folder.png')
   elif (WORK/'assets'/filename).exists():src='../../assets/'+filename
   else:src=(asset or {}).get('remote') or files.get(filename.casefold(),{}).get('url') or BASE+'Special:Redirect/file/'+filename
   return '<img '+('height="43"' if size=='x43' else 'width="'+size+'"')+' src="'+html.escape(src,quote=True)+'">'
  preview_body=re.sub(r'\[\[File:([^|]+)\|(120|10|x43)px\|link=\]\]',image_link,body)
  preview_body=re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]',lambda m:'<a href="'+html.escape(BASE+'index.php?'+urlencode({'title':html.unescape(m[1])}),quote=True)+'">'+m[2]+'</a>',preview_body)
  assert '[[' not in preview_body,key
  (preview/(key+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+key+'</title><style>body{margin:0;padding:16px;background:#eff0f1}a{text-decoration:none}'+css+'</style>'+preview_body+'<script src="../../../wiki/production/pages/tree.js"></script></html>',encoding='utf-8')
  rendered[key]={'cards':tree['visible_count'],'json_reads':native_reads,'both_lua_load_paths':True,'datamine_shop_membership_verified':True}
 ns={'m':NS};xmlpages=ET.parse(out/'WTJ-all-trees-production.xml').findall('m:page',ns)
 assert len(xmlpages)==len(pages)
 for p in xmlpages:assert p.find('m:revision/m:text',ns).text==bytitle[p.find('m:title',ns).text]
 exported=json.loads((EVIDENCE/'exported-sources.json').read_text(encoding='utf-8'))
 for title,content in bytitle.items():
  if title in exported:
   original=exported[title]['content'];pattern=r'\{\{Tree-Start\b.*?\{\{Tree-End\s*\}\}'
   match=re.search(pattern,original,re.S|re.I)
   assert content==original[:match.start()]+'{{WTJ/styles}}\n{{#invoke:WTJ/catalogue|tree|tree='+next(k for k,v in json.loads((EVIDENCE/'targets.json').read_text(encoding='utf-8')).items() if v==title)+'_tree|links=existing}}'+original[match.end():],title
 slice_titles=[]
 for path in sorted(out.glob('WTJ-part-*.xml')):
  nodes=ET.parse(path).findall('m:page',ns);assert len(nodes)<=15
  assert sum(len((n.findtext('m:revision/m:text',default='',namespaces=ns)).encode('utf-8')) for n in nodes)<=1500000
  slice_titles.extend(n.findtext('m:title',namespaces=ns) for n in nodes)
 assert len(slice_titles)==len(set(slice_titles))==len(pages) and set(slice_titles)==set(bytitle)
 assert len(trees)==34 and all(t['branch']!='helicopters' for t in trees.values())
 runtime=bytitle['模块:WTJ/catalogue']
 assert "'Item_group_prem.png'" in runtime and "'Item_group.png'" in runtime
 assert not any(p.name.startswith('WTJ_') for p in (out/'uploads').iterdir())
 (out/'validation.json').write_text(dump({'passed':True,'trees':rendered,'xml_roundtrip':True,'upload_filenames_match_json':True,'existing_folder_backgrounds':'Item_group.png / Item_group_prem.png','live_import_verified':False}),encoding='utf-8')
 (preview/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>34 棵正式科技树本地预览</title><h1>34 棵正式科技树本地预览</h1><p>本地 Lua 输出及正式 JS/CSS；不代表线上导入已经验收。</p>'+''.join('<p><a href="'+k+'.html">'+v+'</a></p>' for k,v in json.loads((EVIDENCE/'targets.json').read_text(encoding='utf-8')).items()),encoding='utf-8')

if __name__=='__main__':main()
