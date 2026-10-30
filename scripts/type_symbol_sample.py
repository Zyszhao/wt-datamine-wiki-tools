"""Render the captured class_icon family offline, preserving shape/color separately."""
import json,html,xml.etree.ElementTree as ET
from paths import WORK
ET.register_namespace('', 'http://www.w3.org/2000/svg')

def main():
 root=WORK/'research/type-symbols'
 data=json.loads((root/'catalogue.json').read_text(encoding='utf8'))
 definitions=[]
 for href in data['resources']:
  name=href.rsplit('/',1)[-1];svg=ET.fromstring((root/name).read_text(encoding='utf8'))
  assert all(e.tag.rsplit('}',1)[-1] in {'svg','path','g'} for e in svg.iter()),name
  assert all(e.get('fill','currentColor')=='currentColor' for e in svg.iter()),name
  assert svg.get('id')=='icon',name
  key=name.removesuffix('.svg')
  inner=''.join(ET.tostring(e,encoding='unicode') for e in svg)
  definitions.append('<symbol id="type-'+key+'" viewBox="'+svg.get('viewBox')+'">'+inner+'</symbol>')
 rows=[]
 for m in data['mappings']:
  key=m['href'].rsplit('/',1)[-1].split('.')[0]
  def icon(size):return '<svg width="'+str(size)+'" height="'+str(size)+'" viewBox="0 0 10 10" color="'+m['color']+'"><use href="#type-'+key+'" width="10" height="10"/></svg>'
  rows.append('<tr><td>'+html.escape(m['branch'])+'</td><td>'+html.escape(m['role'])+'</td><td>'+key+'</td><td>'+m['color']+'</td><td>'+icon(10)+'</td><td>'+icon(18)+'</td><td>'+icon(48)+'</td></tr>')
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WTJTreeTesting SVG 类型图标对照</title><style>body{font:15px system-ui;background:#242e33;color:#eee;padding:24px}table{border-collapse:collapse}td,th{padding:10px 16px;border:1px solid #55626a;text-align:left}svg{vertical-align:middle}p{max-width:900px;line-height:1.6}</style><h1>WTJTreeTesting · 官方 SVG 类型小图标</h1><p>16 个形状资源，19 种军种／类别映射。形状使用 currentColor，由每个实例传入颜色。此页将源文件根 SVG 规范化为本地 symbol，保留各自 viewBox，避免 file:// 外部 use 的跨域限制。</p><svg style="position:absolute;width:0;height:0" aria-hidden="true"><defs>'+''.join(definitions)+'</defs></svg><table><thead><tr><th>军种</th><th>类别</th><th>形状</th><th>颜色</th><th>10px</th><th>18px</th><th>48px</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></html>'
 (root/'sample.html').write_text(page,encoding='utf8')
 print(json.dumps({'resources':len(definitions),'mappings':len(rows),'sample':str(root/'sample.html')}))

if __name__=='__main__':main()
