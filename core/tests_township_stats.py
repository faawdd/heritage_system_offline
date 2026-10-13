from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import HeritageSite, ImmovableHeritage
from core.services.heritage_service import (
    _extract_township_name,
    get_heritage_stats_meta,
    normalize_township_name,
    site_township,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class TownshipStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_superuser('town-admin', password='x'))
        self.url = '/api/v1/heritage/classification-stats/'

    def site(self, code, address, registration=None):
        return HeritageSite.objects.create(
            name=code, sip_code=code, category='GJZ', level='XB',
            address=address, longitude=90, latitude=42, registration=registration,
        )

    def registration(self, code, township):
        return ImmovableHeritage.objects.create(
            name=code, survey_code=code, era='清', category='GJZ',
            province='新疆维吾尔自治区', city='吐鲁番市', county='鄯善县',
            township=township, address='鄯善县辟展乡甲村', longitude=90, latitude=42,
            preservation_status='较好', ownership='state', protection_level='XB',
        )

    def test_extracts_location_not_nearby_township(self):
        for address, expected in [
            ('新疆维吾尔自治区吐鲁番市鄯善县辟展乡甲村，七克台镇西南15千米', '辟展镇'),
            ('鄯善县鲁克沁镇甲村，北距七克台镇55千米', '鲁克沁镇'),
            ('鄯善县吐鲁番市鄯善县东北七克台镇甲村', '七克台镇'),
            ('鄯善县东巴扎乡甲村', '东巴扎回族乡'),
            ('鄯善县达浪坎乡甲村', '达朗坎乡'),
            ('鄯善县七台镇甲村', '七克台镇'),
            ('甲省乙市丙县东门镇甲村', '东门镇'),
            ('鄯善县某地，距七克台镇政府10千米', ''),
            ('', ''),
        ]:
            with self.subTest(address=address):
                self.assertEqual(_extract_township_name(address), expected)

    def test_group_meta_and_filter_use_same_canonical_township(self):
        self.site('a', '鄯善县辟展乡甲村，七克台镇西南15千米')
        self.site('b', '鄯善县辟展镇乙村')
        self.site('c', '鄯善县七克台镇甲村')
        self.site('d', '未知')
        payload = self.client.get(self.url, {'group_by': 'township'}).json()
        self.assertEqual(dict(zip(payload['labels'], payload['data'])),
                         {'辟展镇': 2, '七克台镇': 1, '未标注乡镇': 1})
        self.assertEqual(sum(payload['data']), payload['total'])
        self.assertEqual(len(payload['labels']), len(set(payload['labels'])))
        self.assertEqual({item['value'] for item in get_heritage_stats_meta()['township_options']},
                         {'辟展镇', '七克台镇'})
        for township, count in [('辟展乡', 2), ('辟展镇', 2), ('七克台镇', 1)]:
            self.assertEqual(self.client.get(self.url, {'township': township}).json()['total'], count)

    def test_registered_township_is_normalized_without_modifying_source(self):
        registration = self.registration('reg', ' 辟展乡 ')
        site = self.site('a', '鄯善县七克台镇甲村', registration)
        self.assertEqual(site_township(site), '辟展镇')
        self.assertEqual(self.client.get(self.url, {'township': '辟展镇'}).json()['total'], 1)
        registration.refresh_from_db()
        self.assertEqual(registration.township, ' 辟展乡 ')

    def test_immovable_source_merges_whitespace_and_aliases(self):
        for code, township in [('a', '辟展乡'), ('b', '辟展镇'), ('c', ' 辟展镇 ')]:
            self.registration(code, township)
        payload = self.client.get(self.url, {'source': 'immovable', 'group_by': 'township'}).json()
        self.assertEqual(payload['labels'], ['辟展镇'])
        self.assertEqual(payload['data'], [3])
        self.assertEqual(self.client.get(self.url, {
            'source': 'immovable', 'township': '辟展乡',
        }).json()['total'], 3)

    def test_nonlocal_names_are_preserved(self):
        self.assertEqual(normalize_township_name(' 东门镇 '), '东门镇')
        self.assertEqual(normalize_township_name('南山街道'), '南山街道')

    def test_kanerjing_distribution_uses_same_location(self):
        self.site('甲坎儿井', '鄯善县辟展乡甲村，七克台镇西南15千米')
        self.site('乙坎儿井', '鄯善县辟展镇乙村')
        payload = self.client.get('/api/kanerjing-stats/').json()
        self.assertEqual(payload['top_addresses'],
                         [{'township': '辟展镇', 'address': '辟展镇', 'count': 2}])
