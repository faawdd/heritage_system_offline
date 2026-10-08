import io
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.services import offline_tiles


class OfflineTileImportTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.environment = patch.dict(os.environ, {'HERITAGE_DATA_DIR': str(self.data_dir)})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def test_import_xyz_zip_and_read_tile(self):
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, 'w') as archive:
            archive.writestr('qgis-export/2/2/1.png', b'xyz-tile')

        tile_set = offline_tiles.import_tile_set(
            SimpleUploadedFile('qgis-export.zip', archive_data.getvalue()),
            '本地影像',
        )

        self.assertEqual(tile_set['kind'], 'xyz')
        self.assertEqual(tile_set['tile_count'], 1)
        self.assertEqual(offline_tiles.read_tile(tile_set['id'], 2, 2, 1), (b'xyz-tile', 'png'))

    def test_import_mbtiles_uses_tms_row_scheme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / 'map.mbtiles'
            connection = sqlite3.connect(database_path)
            connection.executescript(
                'CREATE TABLE metadata (name TEXT, value TEXT);'
                'CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);'
            )
            connection.executemany(
                'INSERT INTO metadata (name, value) VALUES (?, ?)',
                [('name', 'Test map'), ('format', 'png'), ('scheme', 'tms')],
            )
            connection.execute(
                'INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (2, 1, 2, ?)',
                (b'mbtiles-tile',),
            )
            connection.commit()
            connection.close()

            tile_set = offline_tiles.import_tile_set(
                SimpleUploadedFile('map.mbtiles', database_path.read_bytes()),
            )

        self.assertEqual(tile_set['kind'], 'mbtiles')
        self.assertEqual(offline_tiles.read_tile(tile_set['id'], 2, 1, 1), (b'mbtiles-tile', 'png'))

    def test_zip_path_traversal_is_rejected(self):
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, 'w') as archive:
            archive.writestr('../2/2/1.png', b'unsafe')

        with self.assertRaises(ValidationError):
            offline_tiles.import_tile_set(SimpleUploadedFile('unsafe.zip', archive_data.getvalue()))

    def test_import_tms_zip_flips_rows_for_xyz_requests(self):
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, 'w') as archive:
            archive.writestr('2/2/2.png', b'tms-tile')

        tile_set = offline_tiles.import_tile_set(
            SimpleUploadedFile('tms-export.zip', archive_data.getvalue()),
            scheme='tms',
        )

        self.assertEqual(tile_set['scheme'], 'tms')
        self.assertEqual(offline_tiles.read_tile(tile_set['id'], 2, 2, 1), (b'tms-tile', 'png'))


class OfflineTileApiTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'HERITAGE_DATA_DIR': self.temp_dir.name})
        self.environment.start()
        self.user = User(username='tile-admin', is_active=True, is_staff=True, is_superuser=True)
        self.user.pk = 1
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def test_authenticated_upload_and_tile_read(self):
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, 'w') as archive:
            archive.writestr('2/2/1.png', b'api-tile')

        response = self.client.post(
            '/api/v1/gis/offline-tiles/',
            {'file': SimpleUploadedFile('qgis-export.zip', archive_data.getvalue())},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)

        tile_set_id = response.data['data']['id']
        access_token = str(AccessToken.for_user(self.user))
        with patch('core.api.views.User.objects.filter') as user_filter:
            user_filter.return_value.first.return_value = self.user
            tile_response = APIClient().get(
                f'/api/v1/gis/offline-tiles/{tile_set_id}/2/2/1/?access_token={access_token}'
            )
        self.assertEqual(tile_response.status_code, 200)
        self.assertEqual(tile_response.content, b'api-tile')

    def test_tile_read_requires_a_valid_access_token(self):
        response = APIClient().get('/api/v1/gis/offline-tiles/missing/2/2/1/')
        self.assertEqual(response.status_code, 404)
