from pathlib import Path
import json,re,sys
from xml.etree import ElementTree as ET
from tree_policy import GAME_TYPES, exclusion_reason
from paths import ROOT, REPO, WIKI, WORK, VENDOR, ensure_output_dirs
ensure_output_dirs()
try:
 from lupa import LuaRuntime
except ImportError:
 sys.path.insert(0,str(VENDOR))
 from lupa import LuaRuntime

def main():
 manifest=json.loads((WIKI/'manifest.json').read_text(encoding='utf-8'))
 pages={p['title']:(ROOT/p['file']).read_text(encoding='utf-8') for p in manifest['pages']}
 assert {p.name for p in (WIKI/'uploads').iterdir()}==set(manifest['uploads'])
 for filename,source in manifest['uploads'].items():assert (WIKI/'uploads'/filename).read_bytes()==((ROOT/source[1:]) if source.startswith('@') else REPO/source).read_bytes()
 assert {p.name for p in (WIKI/'pages').iterdir()}=={Path(p['file']).name for p in manifest['pages']}
 records={p['title']:json.loads(pages[p['title']]) for p in manifest['pages'] if p['model']=='json'}
 prefix='WTJTreeTesting/data/'
 idx=records[prefix+'vehicles_index_testing.json'];tree=records[prefix+'usa_army_tree_testing.json'];mods=records[prefix+'modifications_index_testing.json'];core=records[prefix+'us_m1a2_modifications_testing.json']
 shop=json.loads((REPO/'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))['country_usa']['army']['range']
 tags=json.loads((REPO/'char.vromfs.bin_u/config/unittags.blkx').read_text(encoding='utf-8'))
 for c,source in zip(tree['columns'],shop):
  expected=[]
  for code,value in source.items():
   if code in idx['records']:
    if not exclusion_reason(code,tags):expected.append((None,[code]))
   elif isinstance(value,dict):
    members=[k for k in value if k in idx['records'] and not exclusion_reason(k,tags)]
    if members:expected.append((code,members))
  assert [(n['folder'],n['units']) for n in c['nodes']]==expected
 visible=[u for c in tree['columns'] for n in c['nodes'] for u in n['units']]
 assert len(visible)==tree['visible_count']==154
 assert set(tree['excluded'])=={'us_m551_football','us_m8_scott_snowball','us_m18_hellcat_black_cat_race'}
 assert not set(visible)&set(tree['excluded'])
 assert {idx['records'][u]['category'] for u in visible}==set(GAME_TYPES.values())
 found=visible+tree['unplaced']+list(tree['excluded'])
 assert len(found)==len(set(found))==159
 assert all(idx['records'][u]['country']=='country_usa' for u in found)
 assert idx['records']['us_m1a2_abrams']['br']==[12,12,12]
 assert idx['records']['us_m1a2_abrams']['category']=='中型坦克'
 assert idx['records']['us_m1a2_abrams']['game_type']=='typeMediumTank'
 assert len(idx['records'])==3420 and len(mods['records'])==manifest['global_modifications']
 assert len(idx['groups'])==402
 assert idx['groups']['us_sherman_group']['name']=='M4'
 for group in idx['groups'].values():assert group['name'] and all(u in idx['records'] for u in group['members'])
 for node in tree['layout']['nodes']:
  if node['folder']:
   assert node['folder'] in idx['groups'] and idx['groups'][node['folder']]['members']==node['units']
   assert 'name' not in node
 positions={n['id']:n for n in tree['layout']['nodes']}
 for edge in tree['layout']['arrows']:
  a,b=positions[edge['source']],positions[edge['target']]
  assert edge['y1']==a['top']+52 and edge['y2']==b['top']-4
  assert edge['y2']>edge['y1']
 all_local=json.loads((WORK/'exports/usa_army_local_modifications.json').read_text(encoding='utf-8'))['records']
 for unit,data in all_local.items():
  for mod in data['modifications']:
   assert mod['ref'] in mods['records']
   assert not set(mod)&{'name','description','image','icons'}
 assert len(all_local)==159
 for r in mods['records'].values():
  assert all(v in mods['icons'] for v in r['icons'].values())
 for obj in records.values():assert max(len(json.dumps(obj,ensure_ascii=False,indent=4).encode()),len(json.dumps(obj,ensure_ascii=False).encode()))<2097152
 lua=LuaRuntime(unpack_returned_tuples=True);reads=[];active=dict(pages)
 def table(v):
  if isinstance(v,dict):return lua.table_from({k:table(x) for k,x in v.items()})
  if isinstance(v,list):return lua.table_from([table(x) for x in v])
  return v
 def content(title):reads.append(title);return active.get(title)
 lua.globals().read_bridge=content;lua.globals().decode_bridge=lambda s:table(json.loads(s))
 lua.execute('mw={title={new=function(t) return {getContent=function() return read_bridge(t) end} end},text={jsonDecode=function(s) return decode_bridge(s) end}}')
 module=lua.execute((ROOT/'src/catalogue.lua').read_text(encoding='utf-8'));render={};loads={}
 for fn in ['tree','modifications','check']:
  reads.clear();render[fn]=module[fn]();assert 'wtr-error' not in render[fn],(fn,render[fn]);assert len(reads)==2;loads[fn]=list(reads)
 assert '/modifications_index_' not in ' '.join(loads['tree'])
 assert render['tree'].count('class="wtt-card ')==154
 assert 'wtt-folder-premium' in render['tree']
 assert sum(bool(v['existing_page']) for v in tree['presentation'].values())==154
 existing=module.tree(table({'args':{'links':'existing'}}))
 assert '[[M2A4|' in existing
 emitted=re.findall(r'class="wtt-(?:arrow|edge)" data-from="([^"]+)" data-to="([^"]+)"',render['tree'])
 expected=[(e['from'],e['to']) for e in tree['layout']['arrows']]
 assert sorted(emitted)==sorted(expected)
 assert len(expected)+len(tree['layout']['internal_edges'])==len(tree['edges'])
 for node in tree['layout']['nodes']:
  assert node['top']+48<=tree['layout']['height']
 if 'E_MODE' not in module.tree(table({'args':{'mode':'invalid'}})):raise AssertionError('invalid mode')
 assert render['modifications'].count('class="wtr-mod"')==20
 removed=active.pop(prefix+'modifications_index_testing.json');assert 'wtr-error' not in module.tree();assert 'E_DATA_MISSING' in module.modifications();active[prefix+'modifications_index_testing.json']=removed
 lua.globals().native_bridge=lambda title:table(json.loads(content(title)))
 lua.execute('mw.loadJsonData=function(t) return native_bridge(t) end');assert module.tree()==render['tree']
 ns={'m':'http://www.mediawiki.org/xml/export-0.11/'}
 for pe in ET.parse(WIKI/'import-testing.xml').findall('m:page',ns):assert pe.find('m:revision/m:text',ns).text==pages[pe.find('m:title',ns).text]
 assert (WIKI/'WTJTreeTesting-all-testing.xml').read_bytes()==(WIKI/'import-testing.xml').read_bytes()
 imported=ET.parse(WIKI/'WTJTreeTesting-all-testing.xml').findall('m:page',ns)
 assert len(imported)==len(pages)==14
 for pe in imported:
  title=pe.find('m:title',ns).text;revision=pe.find('m:revision',ns)
  assert revision.find('m:timestamp',ns).text.endswith('Z')
  assert int(revision.find('m:text',ns).get('bytes'))==len(pages[title].encode('utf-8'))
 from install_helper import TREE_FILES
 tree_xml=ET.parse(WIKI/'import-tree-only.xml').findall('m:page',ns)
 assert len(tree_xml)==len(TREE_FILES)
 for pe in tree_xml:assert pe.find('m:revision/m:text',ns).text==pages[pe.find('m:title',ns).text]
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8')
 for fn,name in [('tree','index'),('modifications','modifications')]:
  body=render[fn]
  asset_lookup={v['file']:('../assets/'+v['local'] if v['local'] else v['remote']) for v in tree['assets'].values()}
  wiki_files=json.loads((ROOT/'evidence/presentation-map.json').read_text(encoding='utf-8'))['files']
  body=re.sub(r'\[\[File:([^|]+)\|120px\|link=\]\]',lambda m:'<img width="120" src="../assets/'+m[1]+'">',body)
  body=re.sub(r'\[\[File:([^|]+)\|10px\|link=\]\]',lambda m:'<img width="10" src="'+wiki_files[m[1].casefold()]['url']+'">',body)
  body=re.sub(r'\[\[File:([^|]+)\|x43px\|link=\]\]',lambda m:'<img height="43" src="'+asset_lookup[m[1]]+'">',body)
  body=re.sub(r'\[\[File:([^|]+)\|48px\|link=\]\]',lambda m:'<img width="48" height="48" src="../assets/'+m[1]+'">',body)
  body=re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]',lambda m:'<a href="https://wiki.biligame.com/warthunder/'+m[1]+'">'+m[2]+'</a>',body)
  assert '[[' not in body
  (WORK/f'preview/{name}.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:16px;background:#eff0f1}a{color:#235779;text-decoration:none}'+css+'</style>'+body+'<script src="../../src/tree.js"></script></html>',encoding='utf-8')
 report={'passed':True,'global_vehicles':3420,'global_modifications':manifest['global_modifications'],'usa_ground':159,'raw_shop_vehicles':157,'visible_tree_vehicles':154,'excluded':tree['excluded'],'unplaced':tree['unplaced'],'json_reads':loads,'checks':['shop columns/folders/order after explicit special-mode policy','159 USA units partitioned into visible/excluded/unplaced','game five categories from tags/model type','all USA modification refs valid','prices and positions contain no duplicated presentation','compact and pretty JSON under site article limit','Lua fallback and native same output','missing mod library leaves tech tree working','XML roundtrip'],'live_wiki_verified':False}
 (WORK/'reports/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
