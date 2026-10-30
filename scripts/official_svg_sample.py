"""Offline sample and structural checks for captured official class SVGs."""
import json,xml.etree.ElementTree as ET
from paths import WORK

def main():
 root=WORK/'research/official-svg';rows=[];details=[]
 for kind,label in [('light','轻型坦克'),('medium','中型坦克'),('heavy','重型坦克'),('destroyer','坦克歼击车'),('aa','自行防空炮')]:
  name='icon_tank_'+kind+'.svg';svg=ET.parse(root/'verified'/name).getroot()
  paths=list(svg.iter('{http://www.w3.org/2000/svg}path'))
  assert paths and not list(svg.iter('{http://www.w3.org/2000/svg}image'))
  details.append({'kind':kind,'viewBox':svg.get('viewBox'),'paths':len(paths)})
  rows.append('<tr><td>'+label+'</td>'+''.join('<td><img src="verified/'+name+'" style="width:'+str(width)+'px;height:auto"></td>' for width in (10,24,104))+'<td>'+svg.get('viewBox')+'</td></tr>')
 html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>官方陆战 SVG 图标验证</title><style>body{background:#242e33;color:#eee;font:16px sans-serif;margin:28px}table{border-collapse:collapse}td,th{border:1px solid #607d8b;padding:16px}img{display:block}</style><h1>官方陆战兵种 SVG 图标</h1><p>原始 SVG，通过 img 直接渲染。载具主体 PNG 与类别轮廓是不同素材。</p><table><tr><th>类别</th><th>10px</th><th>24px</th><th>104px</th><th>viewBox</th></tr>'+''.join(rows)+'</table><p>来源：https://wiki.warthunder.com/ground。当前规则与抓取信息见同目录 current-rendering-excerpts.css 和 current-fetch.json。</p></html>'
 (root/'verified-svg.html').write_text(html,encoding='utf-8')
 (root/'verified-svg-structure.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
 print(json.dumps({'passed':True,'icons':len(details)}))

if __name__=='__main__':main()
