"""Capture public official HTML and its actual CSS/JS references, read-only."""
import datetime,json,re,urllib.request
from pathlib import Path
from paths import WORK

def main():
 root=WORK/'research/official-svg';root.mkdir(parents=True,exist_ok=True)
 def get(url):
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:return response.read(),dict(response.headers)
 url='https://wiki.warthunder.com/ground'
 body,headers=get(url);(root/'ground-current.html').write_bytes(body)
 refs=re.findall(r'''(?:src|href)=["']([^"']+\.(?:js|css)(?:\?[^"']*)?)["']''',body.decode())
 results=[]
 for ref in dict.fromkeys(refs):
  if not ref.startswith(('/js/','/css/')):continue
  target='https://wiki.warthunder.com'+ref
  try:
   data,h=get(target);name=ref.split('/')[-1].split('?')[0];(root/name).write_bytes(data);results.append({'url':target,'file':name,'bytes':len(data)})
  except Exception as error:results.append({'url':target,'error':str(error)})
 raw=root/'verified';raw.mkdir(exist_ok=True)
 for kind in ('light','medium','heavy','destroyer','aa'):
  target='https://wiki.warthunder.com/static/class_svg/icon_tank_'+kind+'.svg'
  data,h=get(target);name='icon_tank_'+kind+'.svg';(raw/name).write_bytes(data)
  results.append({'url':target,'file':'verified/'+name,'bytes':len(data)})
 safe_headers={k:v for k,v in headers.items() if k.lower() in ('content-type','date','cache-control')}
 report={'url':url,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'headers':safe_headers,'assets':results}
 (root/'current-fetch.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
