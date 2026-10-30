"""Read-only BWiki parse regression for the generated tree's version label.

Run after production.py. No pages are saved. Reports stay outside ImportPack.
The old footer is a negative control: a browser preview alone accepts it.
"""
import html
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paths import WORK, WIKI


def main():
    preview = WORK / 'preview/production/italy_aviation.html'
    source = preview.read_text(encoding='utf-8')
    assert 'wtt-extra' not in source.split('</style>', 1)[-1], 'Data notes remain'
    match = re.search(r'<span class="wtt-version">[^<]+</span>', source)
    assert match, 'Missing generated version label'
    current = match.group(0)
    old = '<details class="wtt-extra"><summary>数据说明</summary><p>兼容性对照</p></details>'
    report = {'passed': False, 'read_only': True, 'preview': str(preview), 'cases': {}}
    destination = WIKI / 'production/wiki-markup-validation.json'
    try:
        for name, text in [('old_negative_control', old), ('generated_version', current)]:
            query = urlencode({'action': 'parse', 'format': 'json', 'title': 'WTJTreeTesting/MarkupRegression',
                               'text': text, 'contentmodel': 'wikitext', 'prop': 'text'})
            url = 'https://wiki.biligame.com/warthunder/api.php?' + query
            request = Request(url, headers={'User-Agent': 'WTJ-read-only-markup-check/1.0'})
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            rendered = data['parse']['text']['*']
            report['cases'][name] = {'input': text, 'response': data}
            if name == 'old_negative_control':
                assert '<details' in html.unescape(rendered) and '<details' not in rendered, 'Negative control did not reproduce escaping'
            else:
                assert current in rendered
                assert not re.search(r'&lt;/?span\b', rendered, re.I), 'Generated tags escaped'
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(destination)


if __name__ == '__main__':
    main()
