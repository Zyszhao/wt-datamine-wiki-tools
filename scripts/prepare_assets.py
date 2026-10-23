"""Extract existing Wiki presentation contracts from saved read-only evidence."""
from pathlib import Path
from html.parser import HTMLParser
import base64,json,re,shutil
from paths import ROOT, REPO, WIKI, WORK, ensure_output_dirs
ensure_output_dirs()
class Node:
 def __init__(self,tag='',attrs=(),parent=None):self.tag=tag;self.a=dict(attrs);self.children=[];self.parent=parent;self.words=''
 def all(self,tag=None,cls=None):
  result=[]
  for c in self.children:
   if (tag is None or c.tag==tag) and (cls is None or cls in c.a.get('class','').split()):result.append(c)
   result+=c.all(tag,cls)
  return result
 def text(self):return self.words+''.join(c.text() for c in self.children)
class DOM(HTMLParser):
 def __init__(self,s):super().__init__(convert_charrefs=True);self.root=Node();self.current=self.root;self.feed(s)
 def handle_starttag(self,t,a):
  n=Node(t,a,self.current);self.current.children.append(n)
  if t not in ['img','br','hr','meta','link','input','source','wbr','area','embed']:self.current=n
 def handle_endtag(self,t):
  p=self.current
  while p.parent and p.tag!=t:p=p.parent
  if p.parent:self.current=p.parent
 def handle_data(self,s):self.current.words+=s
def extract_contract(wiki):
 dom=DOM(wiki['text']['*']).root
 mapping={};files={}
 for img in dom.all('img'):
  name=img.a.get('alt','').replace(' ','_');src=img.a.get('src')
  if src and name.lower().endswith('.png'):files[name.casefold()]={'file':name,'url':src}
 for card in dom.all(cls='tree-item'):
  image_nodes=card.all(cls='tree-item-img');background=card.all(cls='tree-item-background');texts=card.all(cls='tree-item-text-scroll')
  if not image_nodes or not background:continue
  image=image_nodes[0].all('img');links=background[0].all('a')
  if not image or not links:continue
  filename=image[0].a.get('alt','').replace(' ','_');code=filename.removesuffix('.png').lower()
  bg=background[0].all('img')[0].a.get('alt','')
  target=links[0].a.get('title')
  mapping[code]={'name':texts[0].text() if texts else None,'page':target,'file':filename,'status':'premium' if 'prem' in bg else 'squadron' if 'squad' in bg else 'research'}
  if mapping[code]['name']==code:mapping[code]['name']=None
  type_icons=[n.a.get('alt','').replace(' ','_') for n in card.all('img') if n.a.get('alt','').replace(' ','_').lower().endswith('_icon.png')]
  if type_icons:mapping[code]['type_icon']=type_icons[0]
 groups={}
 for card in dom.all(cls='tree-group'):
  code=card.a.get('id');texts=card.all(cls='tree-item-text-scroll')
  if code:groups[code]={'name':texts[0].text() if texts else code,'file':code+'.png'}
 for popup in dom.all(cls='tree-group-collapse'):
  code=popup.a.get('id');members=[]
  for card in popup.all(cls='tree-item'):
   image=card.all(cls='tree-item-img')
   if image and image[0].all('img'):members.append(image[0].all('img')[0].a.get('alt','').replace(' ','_').removesuffix('.png').lower())
  if code in groups:groups[code]['members']=members
 return mapping,groups,files

def main():
 evidence=ROOT/'evidence';mapping={};groups={};files={}
 for filename in ('bwiki-usa.json','bwiki-china-aviation.json','bwiki-germany-boats.json'):
  v,g,f=extract_contract(json.loads((evidence/filename).read_text(encoding='utf-8'))['parse'])
  mapping.update(v);groups.update(g);files.update(f)
 css=(evidence/'official-app.css').read_text(encoding='utf-8')
 # Decode saved official assets locally. Wiki rendering uses File links, not data URLs.
 names={'normal':'Item_own.png','premium':'Item_prem.png','squadron':'Item_squad.png','folder':'WTJTreeTesting_folder.png','folder-premium':'WTJTreeTesting_folder_prem.png'}
 for selector,new in [('.wt-tree_item','normal'),('.wt-tree_item--prem','premium'),('.wt-tree_item--squad','squadron'),('.wt-tree_group-folder','folder'),('.wt-tree_group--prem .wt-tree_group-folder','folder-premium')]:
  m=re.search(re.escape(selector)+r'\{([^{}]+)\}',css)
  bg=re.search(r'background-image:(url\([^)]*\))',m[1]) if m else None
  if not bg:raise ValueError('Missing official asset: '+selector)
  encoded=re.search(r'base64,([A-Za-z0-9+/=]+)',bg[1])
  if not encoded:raise ValueError('Expected saved embedded PNG: '+selector)
  (WORK/'assets'/names[new]).write_bytes(base64.b64decode(encoded[1]))
 # Metadata only for remote media. Offline preview uses legally extracted local slots.
 econ=json.loads((REPO/'char.vromfs.bin_u/config/wpcost.blkx').read_text(encoding='utf-8'))
 lower={k.lower():k for k in econ}
 mapping={lower.get(k,k):v for k,v in mapping.items()}
 for group in groups.values():group['members']=[lower.get(k,k) for k in group.get('members',[])]
 icons={}
 source=REPO/'atlases.vromfs.bin_u/units'
 for p in source.glob('*.png'):icons[p.stem.lower()]=p
 used={*mapping,*groups}
 from tree_specs import DEPLOY_TREES, tree_id
 shop=json.loads((REPO/'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))
 for country,branches in shop.items():
  for branch,body in branches.items():
   if tree_id(country,branch) not in DEPLOY_TREES:continue
   for col in body['range']:
    for code,value in col.items():
     if not isinstance(value,dict):continue
     used.add(code)
     used.update(u for u in value if u in econ)
 used.update(k for k,v in econ.items() if isinstance(v,dict) and v.get('country')=='country_usa' and v.get('unitClass') in ['exp_tank','exp_heavy_tank','exp_tank_destroyer','exp_SPAA'])
 missing=[]
 for code in used:
  p=icons.get(code.lower())
  if p:shutil.copyfile(p,WORK/'assets'/(code+'.png'))
  else:missing.append(code)
 (ROOT/'evidence/presentation-map.json').write_text(json.dumps({'vehicles':mapping,'groups':groups,'files':files,'missing_local_slots':missing},ensure_ascii=False,indent=2),encoding='utf-8')
 print('existing cards',len(mapping),'folders',len(groups),'missing slots',missing)
if __name__=='__main__':main()
