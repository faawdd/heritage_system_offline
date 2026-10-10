from decimal import Decimal
from unittest import mock

from django.test import TestCase

from core.models import HeritageSite, ImmovableHeritage
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
        self.assertEqual(HeritageSite.objects.count(), 1)
        self.assertEqual(HeritageSite.objects.get().registration_id, heritage.pk)

    def test_import_is_visible_to_management_map_and_kml(self):
        from django.contrib.auth import get_user_model
        from core.services.heritage_service import get_heritage_map_points
        from core.views import _analyze_conflicts
        rings = [[[87.4, 44.3], [87.6, 44.3], [87.6, 44.5], [87.4, 44.3]]]
        sipu_import.apply_payload(
            self._payload(rings={'body': rings}), {}, self._options(), {})
        site = HeritageSite.objects.get()
        self.assertEqual(site._load_polygon_rings(site.body_boundary), [
            [(87.4, 44.3), (87.6, 44.3), (87.6, 44.5), (87.4, 44.3)]])
        self.assertEqual(get_heritage_map_points()[0]['id'], site.pk)
        conflicts = _analyze_conflicts(
            [{'geometry_type': 'Point', 'coordinates': [87.55, 44.35]}], 10)
        self.assertEqual(conflicts[0]['site_id'], site.pk)
        self.client.force_login(get_user_model().objects.create_superuser('admin', password='test-pass'))
        resp = self.client.get('/api/v1/heritage/sites/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['pagination']['total'], 1)
        self.assertEqual(resp.json()['rows'][0]['registration_id'], site.registration_id)
        resp = self.client.get('/api/v1/heritage/immovable/', {'record_id': site.registration_id})
        self.assertEqual(resp.json()['pagination']['total'], 1)
        self.assertIn('sipu_choices', resp.json()['meta'])
        resp = self.client.patch(
            f'/api/v1/heritage/immovable/{site.registration_id}/',
            {'name': '更新墓'}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        site.refresh_from_db()
        self.assertEqual(site.name, '更新墓')
        resp = self.client.patch(
            f'/api/v1/heritage/sites/{site.pk}/',
            {'name': '管理页更新墓'}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        site.registration.refresh_from_db()
        self.assertEqual(site.registration.name, '管理页更新墓')

    def test_same_name_is_not_identity_and_existing_code_is_reused(self):
        existing = HeritageSite.objects.create(
            sip_code='650000-0001', name='旧名称', category='GYZ', level='DS',
            longitude=1, latitude=1)
        sipu_import.apply_payload(self._payload(), {}, self._options(), {})
        existing.refresh_from_db()
        self.assertIsNotNone(existing.registration_id)
        payload = self._payload()
        payload['row']['id'] = 'rid-2'
        payload['row']['code'] = payload['cover']['values']['code'] = '650000-0002'
        payload['basic']['values']['category'] = ['0100']
        sipu_import.apply_payload(payload, {}, self._options(), {})
        self.assertEqual(HeritageSite.objects.count(), 2)
        self.assertEqual(HeritageSite.objects.get(sip_code='650000-0002').category, 'GYZ')

    def test_data_sync_preserves_registry_link(self):
        import io
        from core.services import data_sync
        sipu_import.apply_payload(self._payload(), {}, self._options(), {})
        site = HeritageSite.objects.get()
        _filename, package = data_sync.build_export_package(['heritage'], include_media=False)
        HeritageSite.objects.all().delete()
        ImmovableHeritage.objects.all().delete()
        report = data_sync.apply_import_package(
            io.BytesIO(package), ['heritage'], mode='replace', import_media=False)
        self.assertEqual(report['skipped_count'], 0)
        restored = HeritageSite.objects.get(pk=site.pk)
        self.assertEqual(restored.registration_id, site.registration_id)

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


class RegistryBackfillTests(TestCase):
    def test_backfill_3386_existing_imports_is_idempotent(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        migration = import_module('core.migrations.0038_heritagesite_registration')
        apps = MigrationExecutor(connection).loader.project_state(
            ('core', '0038_heritagesite_registration')).apps
        ImmovableHeritage.objects.bulk_create([
            ImmovableHeritage(
                survey_code=f'REPAIR-{i}', sipu_id=f'remote-{i}', name='同名文物',
                longitude=87.5, latitude=44.3, category='GWZ', protection_level='DS')
            for i in range(3386)
        ])
        existing = HeritageSite.objects.create(
            sip_code='REPAIR-0', name='已有文物', category='GYZ', level='DS',
            longitude=1, latitude=1, body_boundary='[[[1,1],[2,1],[2,2],[1,1]]]')
        manual = ImmovableHeritage.objects.create(
            survey_code='MANUAL', name='未导入四普的采集记录', longitude=1, latitude=1)
        editor = SimpleNamespace(connection=connection)
        for _ in range(2):
            migration.backfill_registry(apps, editor)
        self.assertEqual(HeritageSite.objects.count(), 3386)
        self.assertEqual(HeritageSite.objects.exclude(registration=None).count(), 3386)
        existing.refresh_from_db()
        self.assertEqual(existing.body_boundary, '[[[1,1],[2,1],[2,2],[1,1]]]')
        self.assertFalse(HeritageSite.objects.filter(registration=manual).exists())


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
