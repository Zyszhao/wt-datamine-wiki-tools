"""Read-only BWiki parser checks; never saves a page or uploads files."""
import base64
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paths import ROOT, WIKI


def main():
    css = (ROOT / 'src/vehicle.css').read_text(encoding='utf-8')
    css_sha256 = __import__('hashlib').sha256(css.encode()).hexdigest()
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S).lstrip().replace('}}', '} }')
    markup = ('<div class="wtv-block"><div class="wtv-block-header">Basic info '
              '<span class="wtv-content-edit">[[Special:EditPage/'
              'il_leopard_2a6_hel/basic-info|Edit]]</span></div><div class="wtv-mod-node">'
              '<div role="button" tabindex="0" class="wtv-mod-card">Modification</div>'
              '<div class="wtv-mod-info">Cost</div></div></div>')
    markup += ('<div class="wtv-loadout-editor" data-open="0"><div role="button" tabindex="0" class="wtv-loadout-toggle">Custom loadout</div>'
               '<div class="wtv-slot-choice" data-slot="4"><div role="button" tabindex="0" '
               'class="wtv-store-choice" aria-pressed="false" data-option="kab_500l" '
               'data-selected="0" data-dependencies="7:t220" data-mass="560">KAB-500L</div></div>'
               '<div class="wtv-loadout-result"></div></div>'
               '<span class="wtv-belt-icon"><span>[[File:Bullet cannon red green.png|32px|link=|alt=]]</span></span>')
    markup += ('<div class="wtv-slot-trigger" role="button" tabindex="0">Select</div>'
               '<div class="wtv-slot-options"><div class="wtv-store-choice">Icon and name</div></div>'
               '<div class="wtv-popover-trigger" role="button" tabindex="0" data-popup="store-test">Name</div>'
               '<div class="wtv-popup-source" data-popup-id="store-test">Parameters</div>'
               '<table><tbody data-category="aam"><tr><th class="wtv-hardpoint-left">1</th></tr></tbody></table>')
    report = {'css_sha256': css_sha256, 'read_only': True, 'live_wiki_written': False, 'cases': {}}
    for name, value in [('markup', markup), ('css', '{{#css:\n' + css + '\n}}')]:
        try:
            params = urlencode({'action': 'parse', 'format': 'json',
                                'title': 'il_leopard_2a6_hel',
                                'text': value, 'prop': 'text|headhtml'}).encode()
            request = Request('https://wiki.biligame.com/warthunder/api.php', data=params,
                              headers={'User-Agent': 'WTJ-read-only-vehicle-check/1.0',
                                       'Content-Type': 'application/x-www-form-urlencoded'})
            with urlopen(request, timeout=20) as response:
                data = json.load(response)
            parsed = data['parse']
            rendered = parsed['text']['*']
            sheets = [base64.b64decode(x).decode('utf-8') for x in re.findall(
                r'data:text/css;charset=UTF-8;base64,([^"\s]+)', parsed['headhtml']['*'])]
            passed = (('wtv-mod-card' in rendered and '/basic-info' in rendered and '&lt;div' not in rendered and
                       'class="wtv-loadout-toggle"' in rendered and 'data-selected="0"' in rendered and 'data-dependencies="7:t220"' in rendered and 'data-mass="560"' in rendered and 'data-popup="store-test"' in rendered and 'data-popup-id="store-test"' in rendered and 'wtv-slot-options' in rendered and 'data-category="aam"' in rendered)
                      if name == 'markup' else bool(sheets) and all('insecure input' not in s for s in sheets))
            report['cases'][name] = {'passed': passed, 'response': data, 'decoded_css': sheets}
        except Exception as error:
            report['cases'][name] = {'passed': False, 'error': str(error)}
    report['passed'] = all(case['passed'] for case in report['cases'].values())
    destination = WIKI / 'vehicle-prototype/site-parse-validation.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'cases': {k: v['passed'] for k, v in report['cases'].items()}}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
