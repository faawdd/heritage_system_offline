import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from fastapi.testclient import TestClient
from rest_framework.test import APIClient

from core.models import HeritageSite, InspectionRecord
from core.services import data_sync


@override_settings(SECURE_SSL_REDIRECT=False)
class InspectionDistanceTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('admin', password='test')
        self.site = HeritageSite.objects.create(
            name='测试文物', sip_code='test-1', category='GJZ', level='XB',
            latitude=42, longitude=90, address='测试地址',
        )

    def test_distance_survives_online_style_package_round_trip(self):
        record = InspectionRecord.objects.create(site=self.site, inspector=self.user, distance_meters=123.456)
        _, package = data_sync.build_export_package(['inspection'], include_media=False)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            serialized = json.loads(archive.read('data/core.inspectionrecord.json'))
        self.assertEqual(serialized[0]['fields']['distance_meters'], 123.456)
        serialized[0]['fields']['client_id'] = 'online-only-id'
        imported, skipped, errors = data_sync._load_model_objects(
            json.dumps(serialized).encode(), 'core.InspectionRecord',
        )
        self.assertEqual((imported, skipped, errors), (1, 0, []))
        record.refresh_from_db()
        self.assertEqual(record.distance_meters, 123.456)
        record.delete()
        report = data_sync.apply_import_package(io.BytesIO(package), ['inspection'], import_media=False)
        self.assertEqual(report['skipped_count'], 0)
        self.assertEqual(InspectionRecord.objects.get().distance_meters, 123.456)

    def test_legacy_package_without_distance_imports_as_unknown(self):
        record = InspectionRecord.objects.create(site=self.site, inspector=self.user)
        _, package = data_sync.build_export_package(['inspection'], include_media=False)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            serialized = json.loads(archive.read('data/core.inspectionrecord.json'))
        del serialized[0]['fields']['distance_meters']
        record.delete()
        imported, skipped, errors = data_sync._load_model_objects(
            json.dumps(serialized).encode(), 'core.InspectionRecord',
        )
        self.assertEqual((imported, skipped, errors), (1, 0, []))
        self.assertIsNone(InspectionRecord.objects.get().distance_meters)

    def test_management_list_returns_distance_and_null_for_legacy_records(self):
        InspectionRecord.objects.create(site=self.site, inspector=self.user, distance_meters=0)
        InspectionRecord.objects.create(site=self.site, inspector=self.user)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/v1/inspections/')
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([row['distance_meters'] for row in response.json()['rows']], [0, None])

    def test_legacy_mobile_upload_accepts_distance_and_rejects_invalid_values(self):
        from fastapi_server import main
        main.app.dependency_overrides[main.get_current_user] = lambda: self.user
        try:
            with tempfile.TemporaryDirectory() as media, mock.patch.object(main, 'MEDIA_ROOT', Path(media)), TestClient(main.app) as api:
                data = {'site_id': str(self.site.pk), 'latitude': '42', 'longitude': '90'}
                for value in ['-1', 'NaN', 'Infinity', '20015100']:
                    response = api.post('/api/inspections/upload', data={**data, 'distance_meters': value}, files={'photo': ('test.jpg', b'photo', 'image/jpeg')})
                    self.assertEqual(response.status_code, 400, response.text)
                response = api.post('/api/inspections/upload', data={**data, 'distance_meters': '123.456'}, files={'photo': ('test.jpg', b'photo', 'image/jpeg')})
                self.assertEqual(response.status_code, 201, response.text)
                result = api.get('/api/inspections/mine')
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['items'][0]['distance_meters'], 123.456)
                response = api.post('/api/inspections/upload', data=data, files={'photo': ('test.jpg', b'photo', 'image/jpeg')})
                self.assertEqual(response.status_code, 201, response.text)
                self.assertIsNone(InspectionRecord.objects.order_by('-id').first().distance_meters)
        finally:
            main.app.dependency_overrides.pop(main.get_current_user, None)
