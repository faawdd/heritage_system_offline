import gzip
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import HeritageSite


class HeritageMapPagingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('map-admin', password='test-pass')
        HeritageSite.objects.bulk_create([
            HeritageSite(
                name=f'Site {index}', sip_code=f'SITE-{index}', category='GYZ',
                level='DS', longitude=87, latitude=42,
                body_boundary='[[[87,42],[88,42],[87,43]]]' if index < 23 else None,
                protection_zone='[[[87,42],[88,42],[87,43]]]' if index == 0 else None,
            )
            for index in range(501)
        ])

    def setUp(self):
        self.client.force_login(self.user)

    def test_points_are_lightweight_and_cursor_pages_are_complete(self):
        first = self.client.get('/api/v1/heritage/map-points/', {'view': 'points'}).json()
        self.assertEqual(len(first['rows']), 500)
        self.assertNotIn('body_boundary', first['rows'][0])
        self.assertIn('preview_url', first['rows'][0])
        second = self.client.get('/api/v1/heritage/map-points/', {
            'view': 'points', 'cursor': first['next_cursor'],
        }).json()
        self.assertEqual(len(second['rows']), 1)
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(len({row['id'] for row in first['rows'] + second['rows']}), 501)

    def test_geometry_pages_include_all_ranges_and_body_mode_omits_other_ranges(self):
        first = self.client.get('/api/v1/heritage/map-points/', {'view': 'geometry'}).json()
        self.assertEqual(len(first['rows']), 20)
        self.assertTrue(first['rows'][0]['protection_zone'])
        second = self.client.get('/api/v1/heritage/map-points/', {
            'view': 'geometry', 'cursor': first['next_cursor'],
        }).json()
        self.assertEqual(len(second['rows']), 3)
        self.assertIsNone(second['next_cursor'])
        body = self.client.get('/api/v1/heritage/map-points/', {'view': 'body'}).json()
        self.assertEqual(set(body['rows'][0]), {'id', 'body_boundary'})

    def test_geometry_page_byte_budget_never_drops_oversized_row(self):
        sites = list(HeritageSite.objects.order_by('id')[:3])
        for site in sites:
            site.body_boundary = json.dumps([[['x' * 300000, 42]]])
        HeritageSite.objects.bulk_update(sites, ['body_boundary'])
        first = self.client.get('/api/v1/heritage/map-points/', {'view': 'body'}).json()
        self.assertEqual(len(first['rows']), 1)
        second = self.client.get('/api/v1/heritage/map-points/', {
            'view': 'body', 'cursor': first['next_cursor'],
        }).json()
        self.assertEqual(second['rows'][0]['id'], sites[1].id)
        self.assertEqual(len(second['rows'][0]['body_boundary'][0][0][0]), 300000)

    def test_oversized_unicode_boundary_is_returned_alone(self):
        first_site, second_site = list(HeritageSite.objects.order_by('id')[:2])
        first_site.body_boundary = json.dumps([[['中' * 180000, 42]]], ensure_ascii=False)
        first_site.save(update_fields=['body_boundary'])
        first = self.client.get('/api/v1/heritage/map-points/', {'view': 'body'}).json()
        self.assertEqual(len(first['rows']), 1)
        self.assertEqual(first['rows'][0]['body_boundary'][0][0][0], '中' * 180000)
        second = self.client.get('/api/v1/heritage/map-points/', {
            'view': 'body', 'cursor': first['next_cursor'],
        }).json()
        self.assertEqual(second['rows'][0]['id'], second_site.id)

    def test_legacy_response_validation_and_gzip(self):
        legacy = self.client.get('/api/v1/heritage/map-points/').json()
        self.assertEqual(len(legacy['rows']), 501)
        self.assertIn('body_boundary', legacy['rows'][0])
        self.assertEqual(self.client.get('/api/v1/heritage/map-points/', {
            'view': 'geometry', 'cursor': '-1',
        }).status_code, 400)
        response = self.client.get('/api/v1/heritage/map-points/', {'view': 'points'}, HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response['Content-Encoding'], 'gzip')
        self.assertEqual(len(json.loads(gzip.decompress(response.content))['rows']), 500)
