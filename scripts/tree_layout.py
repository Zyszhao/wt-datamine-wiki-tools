from pathlib import Path
import json
def enrich(tree,index,economy,root,repo,presentation=None):
 if presentation is None:presentation=json.loads((root/'evidence/presentation-map.json').read_text(encoding='utf-8'))
 vehicles=presentation['vehicles'];folders=presentation['groups'];files=presentation['files'];assets={};missing=[]
 def asset(code):
  filename=vehicles.get(code,folders.get(code,{})).get('file',code+'.png')
  if filename.casefold() not in files:
   filename='WTJTreeTesting_'+code+'.png';missing.append({'code':code,'file':filename,'local_exists':(root/'work/assets'/(code+'.png')).exists()})
  assets[code]={'file':filename,'local':code+'.png' if (root/'work/assets'/(code+'.png')).exists() else None,'remote':files.get(filename.casefold(),{}).get('url')}
  return filename
 for c in tree['columns']:
  for n in c['nodes']:
   if n['folder']:
    asset(n['folder'])
   for code in n['units']:asset(code)
 for code in tree['unplaced']:asset(code)
 tree['presentation']={u:{'name':vehicles.get(u,{}).get('name') or index['records'][u]['name'],'type_icon':vehicles.get(u,{}).get('type_icon'),'type_key':vehicles.get(u,{}).get('type_key'),'existing_page':vehicles.get(u,{}).get('page'),'status':vehicles.get(u,{}).get('status') or ('squadron' if tree['flags'].get(u,{}).get('isClanVehicle') else 'premium' if economy[u].get('costGold',0)>0 else 'research')} for u in assets if u in index['records']}
 tree['assets']=assets
 # Derive the research/special boundary from explicit shop prerequisite overrides.
 special=[]
 for c in tree['columns']:
  members=[u for n in c['nodes'] for u in n['units']]
  special.append(bool(members) and all(tree['flags'][u].get('reqAir')=='' or tree['flags'][u].get('isClanVehicle') or economy[u].get('costGold',0)>0 for u in members))
 split=next((i for i in range(len(special)) if all(special[i:])),len(special))
 gap=18 if split<len(special) else 0
 width=len(tree['columns'])*132+8+gap
 divider=split*132-9
 def x(col):return (col-1)*132+(gap if col>split else 0)
 # Fixed 120x48 official card pitch; all column counts share this algorithm.
 y=30;nodes=[];positions={};ranks=[]
 for rank in tree['ranks']:
  columns=[]
  for c in tree['columns']:
   ns=[n for n in c['nodes'] if index['records'][n['units'][0]]['rank']==rank]
   columns.append(ns)
  rows=max(map(len,columns));height=22+max(1,rows)*78
  ranks.append({'rank':rank,'top':y,'height':height})
  for col,ns in enumerate(columns):
   for row,node in enumerate(ns):
    key=node['folder'] or node['units'][0];p={'id':key,'column':col+1,'left':x(col+1),'top':y+27+row*78,'folder':node['folder'],'units':node['units']}
    nodes.append(p)
    for code in node['units']:positions[code]=p
  y+=height
 # Every economic reqAir edge remains explicit. Group-internal edges render in popup.
 rendered=[];internal=[]
 for edge in tree['edges']:
  a=positions.get(edge['from']);b=positions.get(edge['to'])
  if not a or not b:continue
  if a['id']==b['id']:internal.append(edge);continue
  rendered.append({**edge,'source':a['id'],'target':b['id'],'c1':a['column'],'c2':b['column'],'x1':a['left']+60,'x2':b['left']+60,'y1':a['top']+52,'y2':b['top']-4})
 tree['layout']={'width':width,'research_columns':split,'divider':divider,'height':y+10,'ranks':ranks,'nodes':nodes,'arrows':rendered,'internal_edges':internal}
 if tree['branch']=='helicopters':
  from helicopter_layout import layout
  tree['layout']=layout(tree,index,economy)
 from tree_specs import BRANCH_CLASSES
 old_scope={u for u in vehicles if u in index['records'] and index['records'][u]['country']==tree['country'] and index['records'][u]['class'] in BRANCH_CLASSES[tree['branch']]}
 shown={u for n in nodes for u in n['units']}
 differences={'old_card_count':len(old_scope),'new_shop_card_count':len(shown),'old_only':sorted(old_scope-shown),'new_only':sorted(shown-old_scope),'missing_asset_files':missing,'existing_link_count':sum(bool(tree['presentation'][u]['existing_page']) for u in shown),'source':'Saved read-only BWIKI parse and official /ground HTML/CSS; game shop/economy controls new data.'}
 (root/('work/reports/compatibility-'+tree['id']+'.json')).write_text(json.dumps(differences,ensure_ascii=False,indent=2),encoding='utf-8')
 return tree
