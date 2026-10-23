"""Self-contained manual installer: links and copyable source, no Wiki writes."""
import html
from urllib.parse import urlencode
from paths import ROOT, WIKI, SCRIPT_USER

BASE = 'https://wiki.biligame.com/warthunder/'
TREE_FILES = ('vehicles_index_testing.json', 'usa_army_tree_testing.json',
              'china_aviation_tree_testing.json', 'germany_boats_tree_testing.json',
              'catalogue.lua', 'styles.wiki', 'tree_testing.js',
              'usa_army_tree_testing.wiki', 'china_aviation_tree_testing.wiki',
              'germany_boats_tree_testing.wiki', 'diagnostics_testing.wiki')
def common_script():
    return ('// WTJTreeTesting self-contained personal script; no external user JS/CSS.\n'
            '(function(){\n'
            "if (!window.mw || String(mw.config.get('wgPageName') || '').indexOf('WTJTreeTesting/') !== 0) return;\n"
            + (ROOT / 'src/tree.js').read_text(encoding='utf-8') + '\n})();\n')

def link(title, **query):
    return BASE + 'index.php?' + urlencode({'title': title, **query})

def render(pages):
    LOADER = common_script()
    by_file = {p['file'].split('/')[-1]: p for p in pages}
    sections = []
    for number, filename in enumerate(TREE_FILES, 1):
        p = by_file[filename]
        title, model = p['title'], p['model']
        source = (ROOT / p['file']).read_text(encoding='utf-8')
        sections.append('<section class="page"><h2>'+str(number)+'. '+html.escape(title)+'</h2>'
            '<p>内容模型：<strong>'+html.escape(model)+'</strong>。粘贴完整内容并手动保存。已有同名测试页时完整替换。</p>'
            '<p><a target="_blank" rel="noopener" href="'+html.escape(link(title, action='edit', contentmodel=model))+'">打开创建／编辑页 ↗</a> · '
            '<a target="_blank" rel="noopener" href="'+html.escape(link(title))+'">查看页面 ↗</a> · '
            '<a href="pages/'+filename+'">本地源文件</a></p>'
            '<details><summary>展开完整源码（'+str(p['bytes'])+' 字节）</summary>'
            '<button class="copy" type="button">复制完整源码</button><span class="copy-status" role="status"></span>'
            '<textarea readonly spellcheck="false" data-title="'+html.escape(title)+'">'+html.escape(source)+'</textarea></details></section>')
    optional = []
    for p in pages:
        if p['file'].split('/')[-1] not in TREE_FILES:
            optional.append('<li>'+html.escape(p['title'])+'：<a href="pages/'+p['file'].split('/')[-1]+'">完整源码</a></li>')
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WTJTreeTesting · 从零安装助手</title><style>
body{max-width:1100px;margin:24px auto;padding:0 16px;font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif;color:#243340;background:#f4f6f8}h1{font-size:26px}h2{font-size:18px;overflow-wrap:anywhere}.page,.intro{background:white;border:1px solid #d3dce2;border-radius:8px;padding:18px 24px;margin:16px 0}a{color:#1264a0}textarea{display:block;width:100%;box-sizing:border-box;height:280px;margin-top:10px;padding:12px;font:13px/1.5 Consolas,monospace;white-space:pre;overflow:auto}button{padding:7px 12px;cursor:pointer;margin:8px 8px 0 0}summary{cursor:pointer}.copy-status{color:#456}code{overflow-wrap:anywhere}.note{border-left:4px solid #c69c36;padding:8px 14px;background:#fff8e5}
</style><h1>美国陆战科技树 · 从零安装助手</h1>
<div class="intro"><p>当前版本：游戏五类、特殊模式过滤、金色折叠底板、三模式 BR 滑块，以及保留上下文的树筛选与独立卡片列表。常规树 154 辆。</p>
<p>本助手只提供链接和复制窗口，不登录、不提交、不上传。请先登录 BWiki，按 1—7 顺序保存测试页面，然后完成第 8 步个人脚本配置。所有页面隔离在 WTJTreeTesting 前缀内，无需修改正式美国陆军页。</p>
<p class="note">前提：站点启用 Scribunto 和现有 {{#css:}}。JSON 页必须是 JSON 内容模型。创建链接带 contentmodel 参数，但现有页面的模型不会因此自动改变；若编辑器显示 wikitext，请在页面信息核查，必要时由有权限者通过 Special:ChangeContentModel 改为 json。不要把 JSON 包在 pre、nowiki 或代码块中。</p>
<p>科技树只需额外上传两张折叠底板，卡片底板复用已有 Item_own / Item_prem / Item_squad 文件。全部使用 File 内链，无 base64，无用户 CSS。当前脚本目标用户为 319206634。<a href="import-tree-only.xml">七页科技树 XML</a> 可供有导入权限者使用；导入不包含个人 common.js。</p></div>
'''+''.join(sections)
    body += '<section class="page"><h2>上传两张折叠底板</h2><p>先在本地打开并保存以下文件，然后在上传窗口按精确文件名上传。仅从已保存的官方 CSS 解码，没有重新绘制。</p><ul>'
    for filename in ('WTJTreeTesting_folder.png', 'WTJTreeTesting_folder_prem.png'):
        body += '<li><code>文件:'+filename+'</code> · <a href="uploads/'+filename+'">本地图片</a> · <a target="_blank" rel="noopener" href="'+html.escape(link('Special:Upload', wpDestFile=filename))+'">打开上传窗口 ↗</a></li>'
    body += '</ul><p>旧用户 CSS 不再需要，若 common.js 中还有 WTJTreeTesting.css 加载段，请移除该段。只保留下一步 JS 加载代码。</p></section>'
    body += '<section class="page"><h2>8. 启用自己的测试脚本</h2><p><a target="_blank" rel="noopener" href="'+html.escape(link('Special:MyPage/common.js', action='edit'))+'">打开我的 common.js ↗</a>。本次已核对用户 319206634 的线上 common.js，仅含错误的旧科技树加载段，可完整替换为下方内容。若你此后新增了其他代码，先保留这些新增代码，只替换科技树部分。不修改全站 Common.js。</p><button class="copy" type="button">复制加载代码</button><span class="copy-status" role="status"></span><textarea readonly spellcheck="false">'+html.escape(LOADER)+'</textarea><p>个人脚本只对当前登录用户生效。已安装本站当前旧配置时，第 5 步完整替换已足够；第 8 步为同一份代码的备用复制窗口，勿重复粘贴。保存后强制刷新；第 5 步是自包含 common.js，已包含全部交互代码，不再加载 WTJTreeTesting.js 或 WTJTreeTesting.css。当前 common.js 本身包含全部代码；不要再添加外部 WTJTreeTesting.js / .css loader。</p></section>'
    body += '<section class="page"><h2>9. 打开与验收</h2><p><a target="_blank" rel="noopener" href="'+html.escape(link('WTJTreeTesting/usa_army_tree_testing'))+'">打开科技树 ↗</a> · <a target="_blank" rel="noopener" href="'+html.escape(link('WTJTreeTesting/diagnostics_testing'))+'">打开诊断 ↗</a></p><p>诊断应为 global_vehicles=3420、global_groups=402、usa_ground=159、json_pages_read=2。usa_ground 包含被排除的特殊模式及树外记录；树上实际显示 154 辆。</p><ol><li>未筛选时共 154 辆；没有足球、雪球、赛车变体。</li><li>筛选轻型坦克：树中非匹配项变暗，匹配项突出，显示结果数量。</li><li>切到列表：仅保留匹配项，折叠组成员独立换行；清除筛选后恢复全部 154 辆。</li><li>切回树，测试文件夹外点击关闭、Escape、类别与三模式权重滑块。</li></ol><p>若交互未出现，核查第 8 步；若仍是旧行为，清除展示页缓存并强制刷新浏览器。测试页默认载具链接指向尚可能未创建的测试载具页，不会自动创建全套载具文章。</p></section>'
    body += '<section class="page"><h2>可选：指向已有 BWiki 载具条目</h2><p>只替换第 6 步展示页内容为以下调用。已有映射使用现有条目，不编辑被链接页面。</p><button class="copy" type="button">复制展示页</button><span class="copy-status" role="status"></span><textarea readonly spellcheck="false">'+html.escape('__NOINDEX__\n__NOTOC__\n{{WTJTreeTesting/styles}}\n{{#invoke:WTJTreeTesting/catalogue|tree|mode=rb|links=existing}}\n')+'</textarea></section>'
    body += '<details class="page"><summary>可选 M1A2 改装演示，不属于科技树必装项</summary><p>除上述七页外，再创建以下三页，并按 <a href="PAGE-LIST.md">文件清单</a> 上传 18 个改装图标。</p><ul>'+''.join(optional)+'</ul></details>'
    body += '''<script>
document.querySelectorAll('button.copy').forEach(function(button){button.addEventListener('click',async function(){var box=button.parentElement.querySelector('textarea'),status=button.parentElement.querySelector('.copy-status');box.focus();box.select();try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(box.value);}else if(!document.execCommand('copy')){throw Error('copy unavailable');}status.textContent='已复制完整内容';}catch(error){status.textContent='已全选，请按 Ctrl+C 复制';}});});
</script></html>'''
    (WIKI / 'INSTALL.html').write_text(body, encoding='utf-8')
    # Current repair uses the site's existing ResourceLoader template.
    def box(title, source):
        return ('<section class="page"><h2>'+html.escape(title)+'</h2><a target="_blank" rel="noopener" href="'+html.escape(link(title,action='edit'))+'">打开创建／编辑页 ↗</a><br><button class="copy" type="button">复制完整内容</button><span class="copy-status" role="status"></span><textarea readonly spellcheck="false">'+html.escape(source)+'</textarea></section>')
    start=body[:body.index('<h1>')]
    script=body[body.rindex('<script>'):]
    repair=start+'<h1>修复实际脚本加载入口</h1><div class="intro"><p>已在实际站点验证：手动执行线上 common.js 会出现筛选与自适应；问题在个人脚本没有自动执行。本站已有模板:ResourceLoader 及其自动加载器，且只允许 MediaWiki 命名空间的 JavaScript。</p><ol><li>有权限者创建 MediaWiki:WTJTreeTesting.js，粘贴下方完整 JS。可能需要管理员或界面管理员权限。</li><li>替换模板:WTJTreeTesting/styles。它在加载样式的同时通过本站现有 ResourceLoader 请求上述脚本。</li><li>清除测试页缓存并刷新。搜索、类别、权重、列表应自动出现，含匿名读者。</li><li>确认正常后可清空个人 common.js 中整段旧科技树代码；保留与科技树无关的代码。两个旧用户 WTJTreeTesting.js/.css 不再依赖，可移除。</li></ol><p>不需要修改 MediaWiki:Common.js，不需要注册新的 Gadget，不需要重贴 JSON/Lua/展示页或上传图片。本站权限要求来自已读取的 ResourceLoader 实现；没有相应权限时请将第一步源码交给有权限者，修改个人文件无法代替站点脚本入口。</p><p>脚本只在含 .wtt 的页面执行，卡片保持 120×48px，宽屏只调整列间距，窄屏内部滚动；字体继承本站设置。本助手不写入任何线上页面。</p></div>'
    repair+=box('MediaWiki:WTJTreeTesting.js',(ROOT/'src/tree.js').read_text(encoding='utf-8'))
    repair+=box('模板:WTJTreeTesting/styles',(WIKI/'pages/styles.wiki').read_text(encoding='utf-8'))
    repair+='<section class="page"><h2>验收</h2><p><a target="_blank" href="'+html.escape(link('WTJTreeTesting/usa_army_tree_testing'))+'">打开科技树 ↗</a>。确认筛选栏、自适应宽度、列表都可用。建议退出登录或无痕窗口检查，证明不再依赖个人脚本。未创建脚本页前，只有样式正常仍不足以证明 JS 自动加载成功。</p></section>'
    repair+='<section class="page"><h2>最新宽屏与字体修复</h2><p>已取消整体放大，卡片保持 120×48px，宽屏增加列间距；字体继承本站。完整替换上述两页即可修复。也可一次导入 <a href="WTJTreeTesting-all-testing.xml">全部 14 个测试页 XML</a>；图片仍需单独上传。详见 ../docs/LAYOUT-AND-IMPORT.md。</p></section>'
    repair+=script
    (WIKI/'REPAIR.html').write_text(repair,encoding='utf-8')
    # Avoid presenting the superseded personal-script installation instructions.
    (WIKI/'INSTALL.html').write_text(repair.replace('修复实际脚本加载入口','当前科技树交互安装助手')+'<p>从零安装的数据、模块与展示页见 <a href="PAGE-LIST.md">完整页面清单</a>；诊断页可选。当前助手两项是交互入口，初次安装仍需其余数据页。</p>',encoding='utf-8')
    selected=('vehicles_index_testing.json','catalogue.lua','styles.wiki','tree_testing.js','china_aviation_tree_testing.json','germany_boats_tree_testing.json','china_aviation_tree_testing.wiki','germany_boats_tree_testing.wiki')
    multi=start+'<h1>中国空军与德国近岸海军 · 部署助手</h1><div class="intro"><p>先完整替换四项共享页面，再创建两份树 JSON 和两张展示页。没有国家专用脚本：这次是对同一套 Lua、样式与现有 JS 的一次通用升级。以后扩树只需数据页和带 tree 参数的展示页。</p><p>JSON 页必须使用 json 内容模型。MediaWiki 脚本页需要对应编辑权限；无需修改全站 Common.js 或个人 JS/CSS。助手仅提供复制和链接，不会提交。</p></div>'
    for filename in selected:
        page=by_file[filename]
        multi+=box(page['title'],(ROOT/page['file']).read_text(encoding='utf-8'))
    multi+='<section class="page"><h2>新增上传文件</h2><p>以下三个拆包缩略图是旧 BWiki 科技树中缺失的新增卡片，需上传；两张折叠底板已安装则不必重传。</p>'
    for filename in ('WTJTreeTesting_a6m5_zero_china.png','WTJTreeTesting_pe-2-359_china.png','WTJTreeTesting_germ_s_700_s_706.png'):
        multi+='<p><code>文件:'+filename+'</code> · <a href="uploads/'+filename+'">本地图片</a> · <a target="_blank" href="'+html.escape(link('Special:Upload',wpDestFile=filename))+'">打开上传窗口</a></p>'
    multi+='</section><section class="page"><h2>验收</h2><p>中国空军 91 架（12 个 group），德国近岸海军 39 艘。搜索、类别、等级、三模式权重滑块、列表、宽度适配应使用同一套脚本工作。默认指向隔离的测试载具页，缺文章红链不表示科技树生成失败。</p>'
    for key in ('china_aviation','germany_boats'):
        multi+='<p><a target="_blank" href="'+html.escape(link('WTJTreeTesting/'+key+'_tree_testing'))+'">打开 '+key+' 测试页</a></p>'
    multi+='</section><section class="page"><h2>一次导入</h2><p><a href="WTJTreeTesting-all-testing.xml">下载全部 14 个测试页 XML</a>，包含三棵树、所有共享数据与运行组件、M1A2 演示和诊断。使用 Special:Import 按原命名空间导入，图片单独上传。当前修复取消整体缩放并继承本站字体。</p></section>'+script
    (WIKI/'MULTI-TREE.html').write_text(multi,encoding='utf-8')
