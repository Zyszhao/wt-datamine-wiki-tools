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
 # Validate the exported ground RB independently against every aircraft input.
 from decimal import Decimal, ROUND_HALF_UP
 for code,record in idx['records'].items():
  if record['class'] in {'exp_fighter','exp_assault','exp_bomber'}:
   raw=economy[code].get('economicRankTankHistorical')
   if raw is None:raw=economy[code].get('economicRankHistorical')
   expected=None if raw is None else float((Decimal(str(raw))/3+1).quantize(Decimal('0.1'),rounding=ROUND_HALF_UP))
   assert record['br_ground_rb']==expected,(code,record.get('br_ground_rb'),expected)
  else:assert 'br_ground_rb' not in record,code
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
   assert node['top']+48<=tree['layout']['height'],key
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
  if tree['branch']=='helicopters':
   assert tree['layout']['mode']=='rank_position'
   assert len(tree['requirements'])==1 and tree['requirements'][0]['operator']=='any_of'
   conditions=tree['requirements'][0]['conditions']
   assert {c['unitClass'] for c in conditions}=={'tank','aircraft'}
   assert all(c['era']==5 and c['num']==1 and not c['rankExactly'] and c['premium'] and c['clanUnits'] and c['country']==tree['country'] for c in conditions)
   assert not any(u.endswith('_killstreak') or u=='ah_1f_event' for u in visible)
   for node in tree['layout']['nodes']:
    assert tree['flags'][node['units'][0]]['rankPosXY']==[node['column'],node['row']]
   for edge in tree['layout']['arrows']:
    points=edge['points'];assert len(points)>=2
    assert all(0<=x<=tree['layout']['width'] and 0<=y<=tree['layout']['height'] for x,y in points)
    source=next(n for n in tree['layout']['nodes'] if n['id']==edge['source'])
    target=next(n for n in tree['layout']['nodes'] if n['id']==edge['target'])
    if source['top']==target['top']:
     assert points[-1][1]==target['top']+24 and points[-2][1]==points[-1][1]
     assert (points[-1][0]-points[-2][0])*(target['left']-source['left'])>0
    else:
     assert points[-1]==[target['left']+60,target['top']-8]
     assert points[-2][0]==points[-1][0] and points[-2][1]<points[-1][1]
    for (x,y),(xx,yy) in zip(points,points[1:]):
     assert x==xx or y==yy,(key,edge)
     for node in tree['layout']['nodes']:
      a,b,c,d=node['left']-3,node['top']-7,node['left']+123,node['top']+51
      assert not ((a<x<c and max(min(y,yy),b)<min(max(y,yy),d)) if x==xx else (b<y<d and max(min(x,xx),a)<min(max(x,xx),c))),(key,edge,node['id'])
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
  if key in DEPLOY_TREES or tree['branch']=='helicopters' or key in json.loads((ROOT/'config/vehicle-examples.json').read_text(encoding='utf-8'))['trees']:
   missing=[u for u in visible if not tree['assets'][u]['remote'] and not tree['assets'][u]['local']]
   assert not missing,(key,missing)
   result['missing_existing_links']=[u for u in visible if not tree['presentation'][u]['existing_page']]
   result['uploads']=[tree['assets'][u]['file'] for u in visible if not tree['assets'][u]['remote']]
   assets={v['file']:('../assets/'+v['local'] if v['local'] else v['remote']) for v in tree['assets'].values()}
   def img(m):
    filename,size=m[1],m[2];src=assets.get(filename) or wiki_files.get(filename.casefold(),{}).get('url') or '../assets/'+filename
    return '<img '+('height="43"' if size=='x43' else 'width="'+size+'"')+' src="'+str(src)+'">'
   body=re.sub(r'\[\[File:([^|]+)\|(120|10|x43)px\|link=\]\]',img,body)
   def article_link(m):
    code=m[1].removeprefix('WTJTreeTesting/vehicle/')
    folders={v['id']:v['folder'] for v in json.loads((ROOT/'config/vehicle-examples.json').read_text(encoding='utf-8'))['vehicles']}
    target='../../wiki/'+folders[code]+'/preview/index.html' if code in folders else 'https://wiki.biligame.com/warthunder/'+m[1]
    return '<a href="'+target+'">'+m[2]+'</a>'
   body=re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]',article_link,body)
   assert '[[' not in body
   (WORK/('preview/'+key+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:16px;background:#eff0f1}a{color:#235779;text-decoration:none}'+css+'</style>'+body+'<script src="../../src/tree.js"></script></html>',encoding='utf-8')
  results[key]=result
 assert results['china_aviation']['visible']==91 and results['germany_boats']['visible']==39
 assert results['china_aviation']['research_columns']==4 and results['germany_boats']['research_columns']==3
 assert {k:v['visible'] for k,v in results.items() if k.endswith('_helicopters')}=={'usa_helicopters':19,'germany_helicopters':12,'ussr_helicopters':15,'britain_helicopters':10,'japan_helicopters':8,'china_helicopters':13,'italy_helicopters':9,'france_helicopters':12,'sweden_helicopters':6,'israel_helicopters':8}
 usa=read(WORK/'exports/trees/usa_helicopters_tree_testing.json')
 assert {'uh_1c','ah_6m'}=={e['to'] for e in usa['edges'] if e['from']=='uh_1b'}
 assert {'ah_1w','ah_64a'}=={e['to'] for e in usa['edges'] if e['from']=='ah_1f'}
 assert any(e['from']=='uh_1b' and e['to']=='uh_1c' and e['points'][0][1]==e['points'][-1][1] for e in usa['layout']['arrows'])
 branch=next(e for e in usa['layout']['arrows'] if e['from']=='uh_1b' and e['to']=='ah_6m')
 rank6=next(r for r in usa['layout']['ranks'] if r['rank']==6)
 assert all(y<rank6['top'] for (x,y),(xx,yy) in zip(branch['points'],branch['points'][1:]) if x!=xx and y==yy)
 for edge in usa['layout']['arrows']:
  points=edge['points']
  assert abs(points[-1][0]-points[-2][0])+abs(points[-1][1]-points[-2][1])>=18
 france=read(WORK/'exports/trees/france_helicopters_tree_testing.json')
 assert {'tiger_hac_france','tiger_had_block2_france','ah_64e_netherlands'}=={e['to'] for e in france['edges'] if e['from']=='tiger_had_france'}
 links=''.join('<li><a href="'+k+'.html">'+read(WORK/('exports/trees/'+k+'_tree_testing.json'))['label']+'</a>：'+str(v['visible'])+' 架</li>' for k,v in results.items() if k.endswith('_helicopters'))
 (WORK/'preview/helicopters.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>直升机科技树本地测试</title><style>body{font:16px sans-serif;max-width:900px;margin:40px auto;padding:16px;line-height:1.8}a{color:#235779}</style><h1>直升机科技树本地测试</h1><p>数据版本 '+idx['game_version']+'；十国合计 112 架。已排除 *_killstreak 和 ah_1f_event。入口条件使用说明条；载具文章链接为 WTJTreeTesting 测试链接。</p><ul>'+links+'</ul><p>检查横向研发、跨列分叉、法国文件夹，以及桌面与手机横向滚动。此预览不代表线上 Wiki 验收。</p></html>',encoding='utf-8')
 assert 'E_TREE' in module.tree(table({'args':{'tree':'../invalid'}}))
 report={'passed':True,'branches_verified':len(results),'trees':results,'scope':'shop order, membership, policy exclusions, category availability, edge derivation, layout bounds, JSON size and same Lua module both loading paths; whole-site imagery/links and live Scribunto limits are not certified'}
 (WORK/'reports/multi-tree-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'passed':True,'branches_verified':len(results),'examples':{k:results[k] for k in DEPLOY_TREES}},ensure_ascii=False))

if __name__=='__main__':main()
