from decimal import Decimal
from unittest import mock

from django.test import TestCase

from core.models import ImmovableHeritage
from core.services import sipu_import
from core.services.sipu_client import dms_to_decimal, parse_form


class SipuImportTests(TestCase):
    def _payload(self, **extra):
        payload = {
            'row': {'id': 'rid-1', 'code': '650000-0001', 'name': '测试墓', 'latitude': '44-23-27.6', 'longitude': '87-30-00'},
            'cover': {'values': {'code': '650000-0001', 'collectdate': '2026.06.01'}, 'labels': {}, 'unnamed': ['新疆维吾尔自治区', '昌吉州', '阜康市']},
            'basic': {'values': {'name': '测试墓', 'category': ['0200'], 'rank': ['2'], 'ownership': ['01'],
                                 'stateevaluation': ['2'], 'area': '12.5'}, 'labels': {}},
            'warnings': [], 'files': {},
            'points': [{'id': 'p1', 'measurePointType': '2', 'lng': 87.5, 'lat': 44.39, 'altitude': '10'}],
        }
        payload.update(extra)
        return payload

    def _options(self):
        return {'modules': list(sipu_import.ALL_MODULES), 'scope': 'all', 'sync_sites': False}

    def test_dms_and_form_parse(self):
        self.assertAlmostEqual(float(dms_to_decimal('44-23-27.6')), 44 + 23 / 60 + 27.6 / 3600, places=6)
        form = parse_form('<input name="a" value="1"><input type="checkbox" name="b" value="x" checked>')
        self.assertEqual(form['values']['a'], '1')

    def test_apply_payload_is_idempotent(self):
        options = self._options()
        for _ in range(2):
            sipu_import.apply_payload(self._payload(), {'category': {}, 'rank': {}}, options, {})
        self.assertEqual(ImmovableHeritage.objects.count(), 1)
        heritage = ImmovableHeritage.objects.get()
        self.assertEqual(heritage.survey_code, '650000-0001')
        self.assertEqual(heritage.category, 'GMZ')
        self.assertEqual(heritage.protection_level, 'SB')
        self.assertEqual(heritage.county, '阜康市')
        self.assertEqual(heritage.longitude, Decimal('87.50000000'))
        self.assertEqual(len(heritage.coord_list), 1)

    def test_survey_code_conflict_gets_suffix(self):
        ImmovableHeritage.objects.create(survey_code='650000-0001', name='已有', sipu_id='other', longitude=1, latitude=1)
        sipu_import.apply_payload(self._payload(), {}, self._options(), {})
        self.assertEqual(ImmovableHeritage.objects.count(), 2)


class SipuDisplayTests(TestCase):
    def test_display_rows_and_preview(self):
        from core.models import HeritageConstituent, SipuDictItem
        from core.services import sipu_display
        SipuDictItem.objects.create(field='useType', code='01', label='开放')
        h = ImmovableHeritage.objects.create(
            survey_code='X-1', name='预览墓', longitude=1, latitude=1, open_status='01',
            use_purposes=['09'], is_single_area=True, sipu_data={'inferred': ['township']})
        HeritageConstituent.objects.create(heritage=h, name='主体', number='1')
        rows = dict(sipu_display.display_rows(h, sipu_display.load_dict_map()))
        self.assertEqual(rows['开放状况'], '开放')
        self.assertEqual(rows['是否单一范围'], '是')
        self.assertEqual(sipu_display.inferred_labels(h), ['乡镇/街道'])
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('u1', password='p')
        self.client.force_login(user)
        resp = self.client.get(f'/mobile/collect/{h.pk}/preview/')
        self.assertContains(resp, '补充信息（四普系统）')
        self.assertContains(resp, '主体')


class HeritageInferenceTests(TestCase):
    def test_parse_address_strips_repeated_region_prefix(self):
        from core.services.heritage_inference import parse_address
        result = parse_address('某省某市某县某县甲镇乙村3组，在乙村村民委员会东约1千米', ['某省', '某市', '某县'])
        self.assertEqual(result, {'township': '甲镇', 'village': '乙村'})

    def test_infer_text_negation_and_relocation(self):
        from core.services.heritage_inference import infer_from_text
        r = infer_from_text('该墓群未受到盗扰。村民搬迁至他处。曾用名为老城堡。', '新城堡')
        self.assertNotIn('damage_cause', r)
        self.assertNotIn('is_relocated', r)
        self.assertEqual(r.get('former_name'), '老城堡')
