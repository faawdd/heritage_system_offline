import io
import json
import zipfile

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import HeritageSite, ImmovableHeritage
from core.services.two_line_file import normalize_boundary_rings, parse_body_boundary_file

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>本体范围</name><Polygon><outerBoundaryIs><LinearRing>
<coordinates>90.0,42.0,0 90.1,42.0,0 90.1,42.1,0 90.0,42.1,0 90.0,42.0,0</coordinates>
</LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>保护范围</name><Polygon><outerBoundaryIs><LinearRing>
<coordinates>89.0,41.0,0 89.5,41.0,0 89.5,41.5,0 89.0,41.0,0</coordinates>
</LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>"""


class BodyBoundaryParseTests(TestCase):
    def test_parse_skips_two_line_features(self):
        rings = parse_body_boundary_file(KML.encode('utf-8'), 'x.kml')
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0][0], rings[0][-1])

    def test_parse_kmz(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('doc.kml', KML)
        self.assertEqual(len(parse_body_boundary_file(buf.getvalue(), 'x.kmz')), 1)

    def test_normalize_validates(self):
        self.assertEqual(normalize_boundary_rings(''), [])
        with self.assertRaises(ValueError):
            normalize_boundary_rings('[[[1,2],[3,4]]]')
        with self.assertRaises(ValueError):
            normalize_boundary_rings('[[[200,2],[3,4],[5,6]]]')
        ring = normalize_boundary_rings([[[1, 2], [3, 4], [5, 6]]])[0]
        self.assertEqual(ring[0], ring[-1])


class BodyBoundaryAPITests(TestCase):
    def setUp(self):
        call_group = Group.objects.get_or_create(name='管理员')[0]
        self.admin = User.objects.create_user('bb_admin', password='x')
        self.admin.groups.add(call_group)
        self.viewer = User.objects.create_user('bb_viewer', password='x')
        self.viewer.groups.add(Group.objects.get_or_create(name='管理员用户组')[0])
        self.site = HeritageSite.objects.create(
            name='测试点', sip_code='S-BB-1', category='SKT', level='GB',
            address='a', longitude=90.0, latitude=42.0, description='', manager='m',
        )
        self.url = f'/api/v1/heritage/sites/{self.site.id}/body-boundary/'

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_upload_and_clear(self):
        client = self.client_for(self.admin)
        upload = SimpleUploadedFile('b.kml', KML.encode('utf-8'))
        response = client.post(self.url, {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.site.refresh_from_db()
        self.assertEqual(len(json.loads(self.site.body_boundary)), 1)
        self.assertEqual(len(client.get(self.url).json()['data']['body_boundary']), 1)
        self.assertEqual(client.delete(self.url).status_code, 200)
        self.site.refresh_from_db()
        self.assertEqual(self.site.body_boundary, '')

    def test_json_submit_and_invalid(self):
        client = self.client_for(self.admin)
        ok = client.post(self.url, {'body_boundary': [[[90, 42], [90.1, 42], [90.1, 42.1]]]}, format='json')
        self.assertEqual(ok.status_code, 200)
        bad = client.post(self.url, {'body_boundary': [[[90, 42]]]}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_readonly_role_forbidden(self):
        client = self.client_for(self.viewer)
        response = client.post(self.url, {'body_boundary': []}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_patch_body_boundary(self):
        client = self.client_for(self.admin)
        response = client.patch(
            f'/api/v1/heritage/sites/{self.site.id}/',
            {'body_boundary': '[[[90,42],[90.1,42],[90.1,42.1]]]'}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.site.refresh_from_db()
        self.assertTrue(self.site.body_boundary)


class RegistrationPreviewBoundaryTests(TestCase):
    def test_preview_shows_body_boundary_linked_by_sip_code(self):
        user = User.objects.create_user('pv', password='x')
        self.client.force_login(user)
        HeritageSite.objects.create(
            name='联动点', sip_code='S-PV-1', category='SKT', level='GB', address='a',
            longitude=90.0, latitude=42.0, description='', manager='m',
            body_boundary=json.dumps([[[90.0, 42.0], [90.1, 42.0], [90.1, 42.1], [90.0, 42.0]]]),
        )
        heritage = ImmovableHeritage.objects.create(
            survey_code='S-PV-1', name='联动点', longitude=90.0, latitude=42.0,
        )
        response = self.client.get(f'/mobile/collect/{heritage.pk}/preview/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('本体保护', content)
        self.assertIn('90.10000000', content)
        self.assertNotIn('暂无本体保护范围坐标数据', content)
