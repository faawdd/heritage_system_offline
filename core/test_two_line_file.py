import io
import json
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import HeritageSite, HeritageTwoLineFile
from core.services.two_line_file import parse_two_line_file


KML_BOTH_ZONES = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Folder><name>保护范围</name><Placemark><name>保护范围边界</name><Polygon><outerBoundaryIs><LinearRing><coordinates>89.0,42.0,0 89.1,42.0,0 89.1,42.1,0 89.0,42.0,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Folder>
    <Placemark><name>保护范围_DIMENSION_0</name><LineString><coordinates>89.0,42.0,0 89.05,42.02,0 89.1,42.0,0</coordinates></LineString></Placemark>
  <Folder><name>建控地带</name><Placemark><name>控制线</name><LineString><coordinates>89.2,42.0,0 89.3,42.0,0 89.3,42.1,0 89.2,42.0,0</coordinates></LineString></Placemark></Folder>
</Document></kml>'''.encode('utf-8')


class TwoLineParserTests(TestCase):
    def test_ovkml_auto_classifies_both_zone_types(self):
        zones, counts = parse_two_line_file(KML_BOTH_ZONES, 'boundary.ovkml')

        self.assertEqual(counts, {'protection': 1, 'control': 1})
        self.assertEqual(len(zones['protection']), 1)
        self.assertEqual(len(zones['control']), 1)
        self.assertEqual(zones['protection'][0][0], [89.0, 42.0])

    def test_kmz_extracts_kml_and_uses_selected_type_for_unmarked_features(self):
        generic_kml = KML_BOTH_ZONES.decode('utf-8').replace('保护范围', '区域').replace(
            '建控地带', '区域2'
        ).encode('utf-8')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('doc.kml', generic_kml)

        zones, counts = parse_two_line_file(buffer.getvalue(), 'zones.kmz', zone_type='control')

        self.assertEqual(counts, {'protection': 0, 'control': 2})
        self.assertEqual(len(zones['protection']), 0)
        self.assertEqual(len(zones['control']), 2)

    def test_unmarked_file_requires_zone_type(self):
        generic_kml = KML_BOTH_ZONES.decode('utf-8').replace('保护范围', '区域').replace(
            '建控地带', '区域2'
        ).encode('utf-8')

        with self.assertRaisesMessage(ValueError, '未标注的 KML'):
            parse_two_line_file(generic_kml, 'zones.kml')


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class TwoLineFileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser('two-line-admin', 'admin@example.test', 'pass')
        self.client.force_authenticate(self.user)
        self.site = HeritageSite.objects.create(
            name='测试文物',
            sip_code='TEST-TWO-LINE-001',
            category='GMZ',
            level='GB',
            address='测试地址',
            longitude=89.0,
            latitude=42.0,
            description='',
            manager='',
        )
        self.url = f'/api/v1/heritage/sites/{self.site.id}/two-line-file/'

    def upload(self, content=KML_BOTH_ZONES, name='test.ovkml', zone_type='auto'):
        return self.client.post(
            self.url,
            {'file': SimpleUploadedFile(name, content), 'zone_type': zone_type},
            format='multipart',
        )

    def test_upload_replaces_file_and_delete_clears_zones(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.data['data']['protection_count'], 1)
        self.assertEqual(uploaded.data['data']['control_count'], 1)
        self.assertTrue(HeritageTwoLineFile.objects.filter(site=self.site).exists())

        replacement = self.upload(name='replacement.kml')
        self.assertEqual(replacement.status_code, 200)
        self.assertEqual(HeritageTwoLineFile.objects.get(site=self.site).original_name, 'replacement.kml')

        deleted = self.client.delete(self.url)
        self.assertEqual(deleted.status_code, 200)
        self.site.refresh_from_db()
        self.assertFalse(self.site.protection_zone)
        self.assertFalse(self.site.control_zone)
        self.assertFalse(HeritageTwoLineFile.objects.filter(site=self.site).exists())

    def test_invalid_replacement_keeps_existing_file_and_zones(self):
        self.assertEqual(self.upload().status_code, 200)

        invalid = self.upload(content=b'not kml', name='bad.kml')

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(HeritageTwoLineFile.objects.get(site=self.site).original_name, 'test.ovkml')
        self.site.refresh_from_db()
        self.assertTrue(json.loads(self.site.protection_zone))
        self.assertTrue(json.loads(self.site.control_zone))