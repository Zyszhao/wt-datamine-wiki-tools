"""Verify all generated branches and render the two additional deployment examples."""
import json,re,sys
from pathlib import Path
from paths import ROOT,REPO,WIKI,WORK,VENDOR
from tree_policy import exclusion_reason
from tree_specs import DEPLOY_TREES
try:
 from lupa import LuaRuntime
except ImportError:
 sys.path.insert(0,str(VENDOR))
 from lupa import LuaRuntime

def main():
 read=lambda p:json.loads(p.read_text(encoding='utf-8'))
 idx=read(WIKI/'pages/vehicles_index_testing.json');shop=read(REPO/'char.vromfs.bin_u/config/shop.blkx');tags=read(REPO/'char.vromfs.bin_u/config/unittags.blkx');economy=read(REPO/'char.vromfs.bin_u/config/wpcost.blkx')
 manifest=read(WIKI/'manifest.json');pages={p['title']:(ROOT/p['file']).read_text(encoding='utf-8') for p in manifest['pages']}
 lua=LuaRuntime(unpack_returned_tuples=True);reads=[]
 def table(x):
  if isinstance(x,dict):return lua.table_from({k:table(v) for k,v in x.items()})
  if isinstance(x,list):return lua.table_from([table(v) for v in x])
  return x
 def content(title):reads.append(title);return pages.get(title)
 lua.globals().read_bridge=content;lua.globals().decode_bridge=lambda s:table(json.loads(s))
 lua.execute('mw={title={new=function(t) return {getContent=function() return read_bridge(t) end} end},text={jsonDecode=function(s) return decode_bridge(s) end}}')
 module=lua.execute((ROOT/'src/catalogue.lua').read_text(encoding='utf-8'));results={}
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8');wiki_files=read(ROOT/'evidence/presentation-map.json')['files']
 for path in sorted((WORK/'exports/trees').glob('*.json')):
  tree=read(path);key=tree['id'];expected=[]
  for col in shop[tree['country']][tree['branch']]['range']:
   nodes=[]
   for code,value in col.items():
    if not isinstance(value,dict):continue
    members=[code] if code in idx['records'] else [u for u,v in value.items() if u in idx['records'] and isinstance(v,dict)]
    members=[u for u in members if not exclusion_reason(u,tags)]
    if members:nodes.append((None if code in idx['records'] else code,members))
   expected.append(nodes)
  assert [[(n['folder'],n['units']) for n in c['nodes']] for c in tree['columns']]==expected,key
  visible=[u for c in tree['columns'] for n in c['nodes'] for u in n['units']]
  assert len(visible)==len(set(visible))==tree['visible_count'],key
  assert all(idx['records'][u]['country']==tree['country'] and idx['records'][u]['category'] for u in visible),key
  for node in tree['layout']['nodes']:
   assert node['left']>=0 and node['left']+120<=tree['layout']['width'],key
   if node['folder']:assert all(u in idx['groups'][node['folder']]['members'] for u in node['units']),key
  expected_edges=[]
  for u in sorted(visible):
   parent=tree['flags'][u].get('reqAir',economy[u].get('reqAir'))
   if parent in visible:expected_edges.append({'from':parent,'to':u})
   elif parent in idx['groups']:
    candidates=[x for x in idx['groups'][parent]['members'] if x in visible]
    if candidates:expected_edges.append({'from':candidates[-1],'to':u})
  assert tree['edges']==expected_edges,key
  assert len(tree['layout']['arrows'])+len(tree['layout']['internal_edges'])==len(tree['edges']),key
  assert len(json.dumps(tree,ensure_ascii=False,indent=4).encode())<2097152,key
  # Exercise the same module for every branch, including undeployed branches.
  title='WTJTreeTesting/data/'+key+'_tree_testing.json';pages[title]=path.read_text(encoding='utf-8')
  reads.clear();frame=table({'args':{'tree':key+'_tree'}});body=module.tree(frame)
  assert 'wtr-error' not in body,(key,body)
  assert body.count('class="wtt-card ')==len(visible),key
  assert reads==['WTJTreeTesting/data/vehicles_index_testing.json',title],reads
  lua.globals().native_bridge=lambda title:table(json.loads(content(title)))
  lua.execute('mw.loadJsonData=function(t) return native_bridge(t) end')
  assert module.tree(frame)==body,key
  lua.execute('mw.loadJsonData=nil')
  result={'visible':len(visible),'groups':sum(bool(n['folder']) for n in tree['layout']['nodes']),'width':tree['layout']['width'],'research_columns':tree['layout']['research_columns'],'json_pages_read':2,'categories':sorted({idx['records'][u]['category'] for u in visible})}
  if key in DEPLOY_TREES:
   missing=[u for u in visible if not tree['assets'][u]['remote'] and not tree['assets'][u]['local']]
   assert not missing,(key,missing)
   result['missing_existing_links']=[u for u in visible if not tree['presentation'][u]['existing_page']]
   result['uploads']=[tree['assets'][u]['file'] for u in visible if not tree['assets'][u]['remote']]
   assets={v['file']:('../assets/'+v['local'] if v['local'] else v['remote']) for v in tree['assets'].values()}
   def img(m):
    filename,size=m[1],m[2];src=assets.get(filename) or wiki_files.get(filename.casefold(),{}).get('url') or '../assets/'+filename
    return '<img '+('height="43"' if size=='x43' else 'width="'+size+'"')+' src="'+str(src)+'">'
   body=re.sub(r'\[\[File:([^|]+)\|(120|10|x43)px\|link=\]\]',img,body)
   body=re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]',lambda m:'<a href="https://wiki.biligame.com/warthunder/'+m[1]+'">'+m[2]+'</a>',body)
   assert '[[' not in body
   (WORK/('preview/'+key+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:16px;background:#eff0f1}a{color:#235779;text-decoration:none}'+css+'</style>'+body+'<script src="../../src/tree.js"></script></html>',encoding='utf-8')
  results[key]=result
 assert results['china_aviation']['visible']==91 and results['germany_boats']['visible']==39
 assert results['china_aviation']['research_columns']==4 and results['germany_boats']['research_columns']==3
 assert 'E_TREE' in module.tree(table({'args':{'tree':'../invalid'}}))
 report={'passed':True,'branches_verified':len(results),'trees':results,'scope':'shop order, membership, policy exclusions, category availability, edge derivation, layout bounds, JSON size and same Lua module both loading paths; whole-site imagery/links and live Scribunto limits are not certified'}
 (WORK/'reports/multi-tree-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'passed':True,'branches_verified':len(results),'examples':{k:results[k] for k in DEPLOY_TREES}},ensure_ascii=False))

if __name__=='__main__':main()
