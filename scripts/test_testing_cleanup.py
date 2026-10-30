"""Synthetic regressions for title identity and protected cleanup categories."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import testing_cleanup as cleanup


class CleanupTests(unittest.TestCase):
    def test_title_identity_and_boundary(self):
        self.assertEqual(cleanup.canonical('Module:WTJTreeTesting/a_b'), '模块:WTJTreeTesting/a b')
        for title in ('模块:WTJ/catalogue', 'MediaWiki:Common.js', '模板:ResourceLoader',
                      'WTJTreeTestingUnrelated/article', '文件:Item_group.png'):
            self.assertIsNone(cleanup.family(title))

    def test_merge_aliases_and_generation_is_not_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wiki = root / 'wiki'
            wiki.mkdir()
            (wiki / 'pages.xml').write_text('<mediawiki><page><title>Module:WTJTreeTesting/a_b</title></page>'
                                           '<page><title>模块:WTJTreeTesting/a b</title></page>'
                                           '<page><title>模块:WTJ/catalogue</title></page></mediawiki>', encoding='utf-8')
            (wiki / 'manifest.json').write_text(json.dumps({'pages': [{'title': 'WTJTreeTesting/generated'}]}), encoding='utf-8')
            with patch.multiple(cleanup, ROOT=root, WIKI=wiki, WORK=root/'work',
                                IMPORT_PACK=root/'ImportPack', OUT=root/'report'):
                report = cleanup.inventory()
            rows = {row['title']: row for row in report['pages']}
            self.assertEqual(sum('Testing/a b' in title for title in rows), 1)
            self.assertNotIn('模块:WTJ/catalogue', rows)
            self.assertEqual(rows['WTJTreeTesting/generated']['site_status'], 'unknown')
            self.assertNotIn('screenshot-import-confirmed', rows['WTJTreeTesting/generated']['evidence'])

    def test_active_references_and_human_pages_are_held(self):
        titles = ['WTJTreeTesting/article', '模块:WTJTreeTesting/dependency',
                  'WTJTreeTesting/article/basic-info', '文件:WTJTreeTesting_icon.png', 'WTJTesting/retired']
        report = {'pages': [{'title': title, 'family': 'test', 'sources': [], 'evidence': [],
                             'site_status': 'unknown'} for title in titles], 'errors': []}
        with tempfile.TemporaryDirectory() as directory, patch.object(cleanup, 'inventory', return_value=report):
            result = cleanup.write_cleanup(Path(directory), ['WTJTreeTesting/article'],
                                           active_contents=['{{#invoke:WTJTreeTesting/dependency|main}}'])
        dispositions = {r['title']: r['disposition'] for r in result['pages']}
        self.assertEqual(dispositions[titles[0]], 'hold-current-import')
        self.assertEqual(dispositions[titles[1]], 'hold-current-import')
        self.assertEqual(dispositions[titles[2]], 'preserve-human-content')
        self.assertEqual(dispositions[titles[3]], 'review-file-usage')
        self.assertEqual(dispositions[titles[4]], 'retire-after-dependency-check')


if __name__ == '__main__':
    unittest.main()
