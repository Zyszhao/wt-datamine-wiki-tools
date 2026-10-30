"""Validate complete generated CSS through BWiki's read-only parse API.

The CSS extension can silently replace the entire sheet with insecure input.
Browser previews must use the returned CSS, not just the original source.
"""
import base64
import hashlib
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paths import ROOT, WIKI


def verify(css, destination=None):
    destination = destination or WIKI / 'production'
    destination.mkdir(parents=True, exist_ok=True)
    report = {'passed': False, 'read_only': True,
              'css_sha256': hashlib.sha256(css.encode('utf-8')).hexdigest(), 'cases': {}}
    accepted = None
    try:
        # Keep this negative control: one unsupported var() broke every tree.
        cases = [('rejected_var_control', '.wtt{color:red}.wtt-toolbar{top:var(--wtt-sticky-top,0px)}'),
                 ('complete_generated_css', css)]
        for name, value in cases:
            text = '{{#css:\n' + value.replace('}}', '} }') + '\n}}\n<div class="wtt">CSS regression</div>'
            params = urlencode({'action': 'parse', 'format': 'json',
                                'title': 'WTJTreeTesting/CSSRegression', 'text': text,
                                'prop': 'text|headhtml'})
            request = Request('https://wiki.biligame.com/warthunder/api.php?' + params,
                              headers={'User-Agent': 'WTJ-read-only-css-check/1.0'})
            with urlopen(request, timeout=30) as response:
                data = json.load(response)
            head = data['parse']['headhtml']['*']
            encoded = re.findall(r'data:text/css;charset=UTF-8;base64,([^"\s]+)', head)
            sheets = [base64.b64decode(item).decode('utf-8') for item in encoded]
            report['cases'][name] = {'response': data, 'decoded_css': sheets}
            assert sheets, 'CSS extension returned no stylesheet'
            if name == 'rejected_var_control':
                assert any('insecure input' in sheet for sheet in sheets), 'Negative control no longer reproduces rejection'
            else:
                assert all('insecure input' not in sheet for sheet in sheets), 'BWiki rejected the complete CSS'
                accepted = '\n'.join(sheets)
                for selector in ('.wtt-card', '.wtt-toolbar', '.wtt-br-grb'):
                    assert selector in accepted, 'Missing parsed selector: ' + selector
                assert 'position:sticky' in accepted and 'top:0' in accepted
        (destination / 'site-parsed-tree.css').write_text(accepted, encoding='utf-8')
        report['passed'] = True
        return accepted
    except Exception as error:
        report['error'] = str(error)
        # A previous passing artifact must never mask the current failure.
        (destination / 'site-parsed-tree.css').unlink(missing_ok=True)
        raise
    finally:
        (destination / 'wiki-css-validation.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    verify((ROOT / 'src/tree.css').read_text(encoding='utf-8'))
    print('BWiki complete CSS parse: PASS (read-only)')
