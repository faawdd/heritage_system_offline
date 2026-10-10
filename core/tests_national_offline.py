import io
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.api.views import _build_inspection_photo_url
from core.land_project_services import (
    PATH_ARCHAEOLOGY, apply_workflow_action, get_status_controls, resolve_workflow_path,
)
from core.models import HeritageSite, ImmovableHeritage, LandUseProjectApproval, LandUseProjectDocument, ReportRecord
from core.ovkml_converter import CoordinateTransformer
from core.services.heritage_service import get_heritage_stats_meta, site_township
from core.services.report_service import render_report_html
from core.services.system_service import collection_region_defaults
from core.views import _build_project_feasibility_context


class NationalRegionTests(TestCase):
    def make_registration(self, code, **fields):
        return ImmovableHeritage.objects.create(name='测试文物', sipu_id=code, longitude=110, latitude=40, **fields)

    def test_empty_and_unique_imported_region(self):
        empty = {'province': '', 'city': '', 'county': ''}
        self.assertEqual(collection_region_defaults(), empty)
        region = {'province': '浙江省', 'city': '杭州市', 'county': '余杭区'}
        self.make_registration('one', **region)
        self.make_registration('two', **region)
        self.assertEqual(collection_region_defaults(), region)
        self.make_registration('three', province='四川省', city='成都市', county='郫都区')
        self.assertEqual(collection_region_defaults(), empty)

    def test_incomplete_region_is_not_guessed(self):
        self.make_registration('one', province='浙江省')
        self.assertEqual(collection_region_defaults(), {'province': '', 'city': '', 'county': ''})
        self.make_registration('two', province='浙江省', city='杭州市', county='余杭区')
        self.make_registration('three')
        self.assertEqual(collection_region_defaults(), {'province': '', 'city': '', 'county': ''})

    def test_manual_records_do_not_supply_import_defaults(self):
        ImmovableHeritage.objects.create(name='手工文物', province='四川省', city='成都市', county='郫都区', longitude=110, latitude=40)
        self.assertEqual(collection_region_defaults(), {'province': '', 'city': '', 'county': ''})

    def test_townships_across_regions_and_registration_override(self):
        cases = [
            ('浙江省杭州市余杭区良渚街道玉鸟社区', '良渚街道'),
            ('四川省成都市郫都区安德镇泉水村', '安德镇'),
            ('内蒙古自治区呼和浩特市土默特左旗白庙子镇新营子村', '白庙子镇'),
            ('内蒙古自治区锡林郭勒盟正蓝旗桑根达来苏木某嘎查', '桑根达来苏木'),
        ]
        for index, (address, township) in enumerate(cases):
            site = HeritageSite.objects.create(
                name='测试点', sip_code=f'site-{index}', category='GJZ', level='DS',
                address=address, longitude=110, latitude=40,
            )
            self.assertEqual(site_township(site), township)
        self.assertEqual(
            {row['value'] for row in get_heritage_stats_meta()['township_options']},
            {township for _, township in cases},
        )
        site.registration = self.make_registration('registered', township='档案登记乡')
        site.save()
        self.assertEqual(site_township(site), '档案登记乡')
        self.client.force_login(get_user_model().objects.create_superuser('stats_admin', password='test-pass'))
        url = reverse('heritage_classification_stats_api')
        grouped = self.client.get(url, {'source': 'legacy', 'group_by': 'township'}, secure=True)
        self.assertEqual(grouped.status_code, 200)
        self.assertIn('档案登记乡', grouped.json()['labels'])
        filtered = self.client.get(url, {'source': 'legacy', 'township': '良渚街道'}, secure=True)
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()['total'], 1)

    def test_new_collection_codes_and_historical_numbers(self):
        year = timezone.now().year
        historic = ImmovableHeritage.objects.create(name='历史', survey_code=f'SS-CJ-{year}-0001', longitude=110, latitude=40)
        first = ImmovableHeritage.objects.create(name='新采集', longitude=110, latitude=40)
        self.assertEqual(first.survey_code, f'CJ-{year}-0001')
        ImmovableHeritage.objects.create(name='序号上限', survey_code=f'CJ-{year}-9999', longitude=110, latitude=40)
        self.assertEqual(ImmovableHeritage.objects.create(name='下一条', longitude=110, latitude=40).survey_code, f'CJ-{year}-10000')
        self.assertEqual(ImmovableHeritage.objects.create(name='再一条', longitude=110, latitude=40).survey_code, f'CJ-{year}-10001')
        historic.refresh_from_db()
        self.assertEqual(historic.survey_code, f'SS-CJ-{year}-0001')

    def test_report_region_is_configured_not_fixed(self):
        for region in ('', '某市'):
            with override_settings(SYSTEM_REGION=region):
                html, context = render_report_html(ReportRecord.PERIOD_MONTHLY, date(2026, 1, 1), date(2026, 1, 31))
                self.assertTrue(context['report_title'].startswith(f'{region}文物保护'))
                self.assertNotIn('鄯善', html)


class NationalProjectWorkflowTests(TestCase):
    def make_project(self, level):
        return LandUseProjectApproval.objects.create(
            project_name='风险提示测试', company_name='测试单位',
            status=LandUseProjectApproval.STATUS_CHECK_OVERLAP,
            is_overlap_artifact=True, spatial_check_at=timezone.now(),
            overlapped_relics_info=[{'site_level': level, 'heritage_name': '测试文物'}],
        )

    def test_high_levels_warn_but_do_not_block_submission(self):
        for level in ('GB', 'SB'):
            with self.subTest(level=level):
                project = self.make_project(level)
                self.assertEqual(resolve_workflow_path(project)[0], PATH_ARCHAEOLOGY)
                self.assertTrue(get_status_controls(project.status, project)['submit_archaeology'])
                context = _build_project_feasibility_context(project)
                self.assertTrue(context['hasHighLevelOverlap'])
                self.assertTrue(context['isFeasibleByLevel'])
                self.assertIn('不代替审批', context['replyConclusion'])
                self.assertNotIn('不予同意', context['replyConclusion'])
                LandUseProjectDocument.objects.create(
                    project=project, category=LandUseProjectDocument.CATEGORY_COUNTY_REQUEST,
                    file_path='documents/request.pdf',
                )
                apply_workflow_action(project, 'submit_city_request', {'shanshan_request_num': '任意地区/2026/01'})
                LandUseProjectDocument.objects.create(
                    project=project, category=LandUseProjectDocument.CATEGORY_ARCHAEOLOGY_REQUEST,
                    file_path='documents/archaeology.pdf',
                )
                apply_workflow_action(project, 'submit_archaeology_request', {'archaeology_request_num': '考古函/01'})
                project.refresh_from_db()
                self.assertEqual(project.status, LandUseProjectApproval.STATUS_ARCHAEOLOGY)

    def test_required_documents_and_manual_approval_are_preserved(self):
        project = self.make_project('GB')
        with self.assertRaises(ValueError):
            apply_workflow_action(project, 'submit_archaeology_request', {'archaeology_request_num': '函/01'})
        LandUseProjectDocument.objects.create(
            project=project, category=LandUseProjectDocument.CATEGORY_ARCHAEOLOGY_REQUEST,
            file_path='documents/archaeology.pdf',
        )
        with self.assertRaisesMessage(ValueError, '考古请示文号不能为空'):
            apply_workflow_action(project, 'submit_archaeology_request', {})
        with self.assertRaises(ValueError):
            apply_workflow_action(project, 'record_city_reply', {'final_reply_to_company': '直接复函'})
        self.assertEqual(project.status, LandUseProjectApproval.STATUS_CHECK_OVERLAP)

    def test_list_detail_and_workflow_filter_keep_high_level_risk(self):
        project = self.make_project('GB')
        self.client.force_login(get_user_model().objects.create_superuser('project_admin', password='test-pass'))
        response = self.client.get('/api/v1/projects/', {'workflow_path': PATH_ARCHAEOLOGY}, secure=True)
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.json()['rows'] if item['id'] == str(project.pk))
        self.assertTrue(row['has_high_level_overlap'])
        self.assertTrue(row['is_feasible_by_level'])
        detail = self.client.get(f'/api/v1/projects/{project.pk}/', secure=True)
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()['data']['has_high_level_overlap'])
        self.assertTrue(detail.json()['data']['controls']['submit_archaeology'])


class NationalInspectorRosterTests(TestCase):
    def test_delete_targets_only_provided_roster(self):
        users = get_user_model()
        selected = users.objects.create_user('selected_user')
        retained = users.objects.create_user('retained_user')
        with TemporaryDirectory() as directory:
            roster = Path(directory) / 'inspectors.json'
            roster.write_text(json.dumps([{'name': '测试', 'username': selected.username}]), encoding='utf-8')
            with mock.patch('builtins.input', return_value='yes'):
                call_command('create_inspectors', inspectors_file=str(roster), delete=True, stdout=io.StringIO())
        self.assertFalse(users.objects.filter(pk=selected.pk).exists())
        self.assertTrue(users.objects.filter(pk=retained.pk).exists())


class NationalCoordinateTests(SimpleTestCase):
    def test_projection_requires_explicit_valid_meridian(self):
        for value in (None, '', 'invalid', float('nan'), float('inf'), 72, 136):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CoordinateTransformer('cgcs2000_proj', 'wgs84', value)

    def test_multiple_meridians_and_projected_output(self):
        for meridian in (90, 111, 120, 129):
            transformer = CoordinateTransformer('cgcs2000_proj', 'wgs84', meridian)
            longitude, latitude = transformer.transform_lonlat(500000, 4700000)
            self.assertAlmostEqual(longitude, meridian, places=5)
            self.assertAlmostEqual(latitude, 42.4354, places=3)
        x, y = CoordinateTransformer('wgs84', 'cgcs2000_proj').to_projected_xy(120, 30)
        self.assertAlmostEqual(x, 500000, places=3)
        self.assertGreater(y, 3000000)

    def test_missing_projection_library_cannot_fake_success(self):
        with mock.patch('core.ovkml_converter.Transformer', None):
            with self.assertRaises(RuntimeError):
                CoordinateTransformer('cgcs2000_proj', 'wgs84', 120).transform_lonlat(500000, 4700000)
            with self.assertRaises(RuntimeError):
                CoordinateTransformer('wgs84', 'cgcs2000').transform_lonlat(120, 30)
            self.assertEqual(CoordinateTransformer('wgs84', 'wgs84').transform_lonlat(120, 30), (120, 30))

    def test_photo_urls_use_current_deployment(self):
        request = RequestFactory().get('/', secure=True)
        self.assertEqual(_build_inspection_photo_url('/media/photo.jpg', request), 'https://testserver/media/photo.jpg')

    def test_inspection_template_has_no_fixed_region(self):
        with ZipFile(Path(settings.BASE_DIR) / 'template.docx') as archive:
            xml = archive.read('word/document.xml').decode()
        self.assertNotIn('鄯善', xml)
        for field in ('name', 'inspector', 'time', 'status', 'details', 'photo'):
            self.assertIn(field, xml)

    def test_inspector_initialization_requires_deployment_roster(self):
        with TemporaryDirectory() as directory:
            roster = Path(directory) / 'inspectors.json'
            roster.write_text('[]', encoding='utf-8')
            with self.assertRaisesMessage(CommandError, '名单必须为非空数组'):
                call_command('create_inspectors', inspectors_file=str(roster))
