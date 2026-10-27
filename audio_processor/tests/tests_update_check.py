import os
import unittest
from unittest import mock

import update_check
from update_check import (
    app_version,
    check_for_update,
    is_development,
    newer_release,
    release_from_json,
    version_key,
)


class UpdateCheckTests(unittest.TestCase):
    def test_version_key_orders_releases_and_prereleases(self):
        self.assertLess(version_key('1.1.0'), version_key('v1.2.0'))
        self.assertLess(version_key('1.2.0-beta.1'), version_key('1.2.0'))
        self.assertLess(version_key('1.9.0'), version_key('1.10.0'))
        self.assertIsNone(version_key('dev'))
        # Tags of the April 2026 pre-releases read as pre-releases of 1.0.0.
        self.assertLess(version_key('v1.0.0-beta-20260429-152734-a4db4a5'), version_key('1.0.0'))
        self.assertIsNone(version_key('1.2'))

    def test_development_builds_never_report_updates(self):
        self.assertTrue(is_development('dev'))
        self.assertTrue(is_development('0.0.0-dev.c702f84'))
        self.assertFalse(is_development('1.1.0'))
        self.assertIsNone(newer_release('0.0.0-dev.c702f84', 'v9.0.0'))

    def test_newer_release_only_for_greater_versions(self):
        self.assertEqual(newer_release('1.1.0', 'v1.2.0'), 'v1.2.0')
        self.assertEqual(newer_release('1.2.0-beta.1', 'v1.2.0'), 'v1.2.0')
        self.assertIsNone(newer_release('1.2.0', 'v1.2.0'))
        self.assertIsNone(newer_release('1.3.0', 'v1.2.0'))
        self.assertIsNone(newer_release('1.1.0', 'not-a-version'))

    def test_release_from_json_ignores_drafts_and_prereleases(self):
        url = 'https://github.com/tomduca/lu2met-nr/releases/tag/v1.2.0'
        self.assertEqual(
            release_from_json({'tag_name': 'v1.2.0', 'html_url': url}),
            ('v1.2.0', url),
        )
        self.assertIsNone(release_from_json({'tag_name': 'v1.3.0-beta.1', 'prerelease': True}))
        self.assertIsNone(release_from_json({'tag_name': 'v1.3.0', 'draft': True}))
        self.assertIsNone(release_from_json({'message': 'Not Found'}))

    def test_check_for_update_handles_network_failure(self):
        with mock.patch.object(update_check.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertIsNone(check_for_update('1.1.0'))

    def test_check_for_update_reports_newer_release(self):
        with mock.patch.object(update_check, 'fetch_latest_release', return_value=('v1.2.0', 'u')):
            self.assertEqual(check_for_update('1.1.0'), ('v1.2.0', 'u'))
            self.assertIsNone(check_for_update('1.2.0'))

    def test_app_version_override_and_source_default(self):
        with mock.patch.dict(os.environ, {'LU2MET_NR_VERSION': '1.1.0'}):
            self.assertEqual(app_version(), '1.1.0')
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app_version(), 'dev')
