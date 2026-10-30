"""Isolated USA ground SVG-arrow trial; does not change packaged tree data."""
import json,re,sys
from paths import ROOT,WORK,WIKI,VENDOR
from research_edges import research_edges,clear_path
try:
 from lupa import LuaRuntime
except ImportError:
 sys.path.insert(0,str(VENDOR))
 from lupa import LuaRuntime


def main():
 read=lambda p:json.loads(p.read_text(encoding='utf-8'))
 tree=read(WORK/'exports/trees/usa_army_tree_testing.json')
 index=read(WIKI/'pages/vehicles_index_testing.json')
 original=tree['layout'];nodes=original['nodes']
 arrows,internal=research_edges(nodes,tree['edges'],channel_offset=54,target_gap=4)
 original.update(arrows=arrows,internal_edges=internal)
 boxes=[(n['left']-3,n['top']-3,n['left']+123,n['top']+49) for n in nodes]
 for edge in arrows:
  assert clear_path(edge['points'],boxes),(edge['from'],edge['to'])
  assert all(0<=x<=original['width'] and 0<=y<=original['height'] for x,y in edge['points']),edge
 assert len(arrows)+len(internal)==len(tree['edges'])
 lua=LuaRuntime(unpack_returned_tuples=True)
 def table(value):
  if isinstance(value,dict):return lua.table_from({k:table(v) for k,v in value.items()})
  if isinstance(value,list):return lua.table_from([table(v) for v in value])
  return value
 data={'WTJTreeTesting/data/vehicles_index_testing.json':index,'WTJTreeTesting/data/usa_army_tree_testing.json':tree}
 lua.globals().load_bridge=lambda title:table(data[title])
 lua.execute('mw={loadJsonData=function(t) return load_bridge(t) end}')
 module=lua.execute((ROOT/'src/catalogue.lua').read_text(encoding='utf-8'))
 body=module.tree(table({'args':{'tree':'usa_army_tree'}}))
 assert 'wtr-error' not in body
 files=read(ROOT/'evidence/presentation-map.json')['files']
 assets={a['file']:'../assets/'+a['local'] if a['local'] else a['remote'] for a in tree['assets'].values()}
 def image(m):
  name,size=m.groups();src=assets.get(name) or files.get(name.casefold(),{}).get('url') or '../assets/'+name
  return '<img '+('height="43"' if size=='x43' else 'width="'+size+'"')+' src="'+src+'">'
 body=re.sub(r'\[\[File:([^|]+)\|(120|10|x43)px\|link=\]\]',image,body)
 body=re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]',r'<a href="#">\2</a>',body)
 css=(ROOT/'src/tree.css').read_text(encoding='utf-8')
 (WORK/'preview/usa_army_svg_arrows.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>美国陆战 SVG 箭头试验</title><style>body{margin:0;padding:16px;background:#eff0f1}'+css+'</style><p>美国陆战 SVG 箭头本地试验 · 原列/等级/文件夹布局 · 154 辆 · <a href="usa_army.html">原箭头版本</a></p>'+body+'<script src="../../src/tree.js"></script></html>',encoding='utf-8')
 (WORK/'exports/usa_army_svg_arrows.json').write_text(json.dumps(tree,ensure_ascii=False),encoding='utf-8')
 report={'passed':True,'tree':tree['id'],'visible':tree['visible_count'],'routed_edges':len(arrows),'internal_edges':len(internal),'unchanged_nodes':True,'card_collision_free':True,'scope':'isolated local preview, packaged tree unchanged'}
 (WORK/'reports/ground-arrow-trial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report))


if __name__=='__main__':main()
