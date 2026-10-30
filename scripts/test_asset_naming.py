import unittest

from asset_naming import vehicle_image_name, mediawiki_file_key


class AssetNamingTests(unittest.TestCase):
    def test_statcard_uses_existing_wiki_convention(self):
        local = vehicle_image_name('cn_ztz_99a.png', large=True)
        self.assertEqual(local, 'cn_ztz_99a_资料卡.png')
        self.assertEqual(mediawiki_file_key(local), mediawiki_file_key('Cn_ztz_99a_资料卡.png'))
        self.assertEqual(mediawiki_file_key(local), mediawiki_file_key('Cn ztz 99a 资料卡.png'))
        self.assertNotEqual(mediawiki_file_key(local), mediawiki_file_key('CN_ZTZ_99A_资料卡.png'))
        self.assertNotEqual(mediawiki_file_key(local), mediawiki_file_key('cn_ztz_99a_statcard.png'))
        self.assertEqual(vehicle_image_name('cn_ztz_99a.png'), 'cn_ztz_99a.png')
