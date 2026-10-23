"""Generate an offline Special:Export request; never contacts or edits the Wiki."""
import html
import json
from paths import REPO, WORK
from tree_specs import COUNTRIES, BRANCHES


def main():
    shop = json.loads((REPO / 'char.vromfs.bin_u/config/shop.blkx').read_text(encoding='utf-8'))
    trees = [COUNTRIES[country.removeprefix('country_')] +
             ('陆军' if branch == 'army' else BRANCHES[branch])
             for country, branches in shop.items() for branch in branches
             if branch != 'helicopters']
    support = ['MediaWiki:Common.js', 'MediaWiki:Common.css',
               '模板:ResourceLoader', '模板:Tree-Start', '模板:Tree-End',
               '模板:Tree-Unit', '模板:Tree-Group', '模板:Tree-Arrow',
               '模板:tr', '模板:UnitTypeIcon']
    titles = list(dict.fromkeys(trees + support))
    assert len(trees) == 34 and len(titles) == 44
    output = WORK / 'exports/production-source-request'
    output.mkdir(parents=True, exist_ok=True)
    # No BOM, headings, blank lines, URL encoding, or bullet markers in the list.
    (output / 'BWiki-Special-Export-pages.txt').write_text('\n'.join(titles) + '\n', encoding='utf-8')
    instructions = '''# 正式科技树源码导出请求

用途：保存 34 张现有科技树的导航、分类和原始内容，核对旧载具链接及全站 JS/CSS 加载方式，并为正式部署生成回退包。

1. 打开 https://wiki.biligame.com/warthunder/特殊:导出页面 （Special:Export）。
2. 将 BWiki-Special-Export-pages.txt 的全部内容粘贴到页面名称框；每行一个标题，共 44 行。
3. 勾选“仅包含当前修订”（或同义选项），不要勾选“包含模板”，不要使用按分类追加。
4. 若有“保存为文件”选项，勾选后点击导出，保留原始 XML，不要再导入。
5. 将下载的 XML 的本地绝对路径告诉维护者。若一次导出被限制，可分成前 34 行科技树和后 10 行依赖，分别导出并提供两个文件。

这不是部署包，也不包含游戏直升机树。导出不会改动站点页面。模板:tr 用于解析游戏代码对应的中文名称/旧词条链接；若它进一步引用模块或数据页，需在读完此次 XML 后再列出确切依赖。当前列表不能代替最终全部载具链接存在性核对。
'''
    (output / 'README.md').write_text(instructions, encoding='utf-8')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>BWiki 正式科技树源码导出助手</title>
<style>body{max-width:950px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui}textarea{width:100%;box-sizing:border-box;height:440px;font:15px/1.6 monospace}button,a{display:inline-block;margin:8px 12px 8px 0}button{padding:8px 18px}pre{white-space:pre-wrap}</style>
<h1>正式科技树：源码导出助手</h1>
<p>共 44 个标题：34 张正式科技树及 10 张现有依赖页。此助手只提供页面列表，不请求 API，不登录或写入 Wiki。</p>
<a href="https://wiki.biligame.com/warthunder/Special:Export" target="_blank" rel="noopener">打开 BWiki 导出页面</a>
<a href="BWiki-Special-Export-pages.txt" download>下载纯文本列表</a>
<button id="copy">复制全部页面名</button><span id="status" role="status"></span>
<textarea id="pages" readonly aria-label="导出页面标题列表">TITLE_LIST</textarea>
<p>在站内导出页粘贴以上列表，勾选“仅包含当前修订”，不要勾选“包含模板”；若有“保存为文件”，请勾选。导出后保留 XML，并告诉我文件的本地路径。无需编辑或导入任何页面。</p>
<p>如果一次导出受限，可分成前 34 行科技树和后 10 行依赖分别导出。读取模板:tr 后，若发现其他模块或数据依赖，我会再给出确切的补充列表。</p>
<script>document.getElementById('copy').onclick=async()=>{const t=document.getElementById('pages'),s=document.getElementById('status');t.focus();t.select();try{await navigator.clipboard.writeText(t.value);s.textContent='已复制 44 个页面名';}catch(e){s.textContent=document.execCommand('copy')?'已复制 44 个页面名':'已全选，请按 Ctrl+C 复制';}};</script></html>'''
    (output / 'EXPORT-HELPER.html').write_text(page.replace('TITLE_LIST', html.escape('\n'.join(titles))), encoding='utf-8')
    # Confirmed references in the user's 2026-10-23 export, not guessed titles.
    (output / 'BWiki-Special-Export-additional-pages.txt').write_text(
        '模板:Tr/db\n模块:Tr\n', encoding='utf-8')
    print(json.dumps({'trees': len(trees), 'support': len(support), 'titles': len(titles),
                      'directory': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
