import io
import json
import tempfile
import zipfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from core.land_project_services import (
    apply_workflow_action, build_workflow_todos, link_project_kml_record,
    verify_preliminary_spatial_safety, verify_project_spatial_safety,
)
from core.models import KmlUploadRecord, LandUseProjectApproval


KML = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><Point><coordinates>90,42,0</coordinates></Point></Placemark></kml>'


class ProjectKmlLinkTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.media.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.project = LandUseProjectApproval.objects.create(
            project_name='KML link test', preliminary_project_name='Preliminary name',
            company_name='Test company', receive_date=date.today(),
        )
        self.record = self.make_record()

    def make_record(self, kmz=False):
        content = KML
        if kmz:
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('doc.kml', KML)
            content = archive.getvalue()
        record = KmlUploadRecord.objects.create(title='Test selection')
        record.source_file.save('selection.kmz' if kmz else 'selection.kml', ContentFile(content))
        return record

    def test_new_project_link_enables_preliminary_check_and_advances(self):
        for record in (self.record, self.make_record(kmz=True)):
            self.project.status = LandUseProjectApproval.STATUS_RECEIVED
            link_project_kml_record(self.project, record)
            self.project.refresh_from_db()
            self.assertEqual(self.project.preliminary_kml_file_path, record.source_file.name)
            todo = build_workflow_todos(self.project, '')[0]
            self.assertTrue(todo['enabled'], todo['blockers'])
            result = verify_preliminary_spatial_safety(self.project.id)
            self.assertEqual(result['feature_count'], 1)
            self.project.refresh_from_db()
            self.assertEqual(self.project.status, LandUseProjectApproval.STATUS_PRELIM_REVIEWED)

    def test_old_linked_project_can_continue_without_reupload(self):
        self.project.kml_record = self.record
        self.project.kml_file_path = self.record.source_file.name
        self.project.save()
        self.assertTrue(build_workflow_todos(self.project, '')[0]['enabled'])
        user = get_user_model().objects.create_superuser('legacy-admin', password='test-password')
        self.client.force_login(user)
        response = self.client.get(f'/api/v1/projects/{self.project.id}/', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['preliminary_kml_file_path'], self.record.source_file.name)
        self.assertTrue(response.json()['data']['guide']['todos'][0]['enabled'])
        verify_preliminary_spatial_safety(self.project.id)
        self.project.refresh_from_db()
        self.assertEqual(self.project.preliminary_kml_file_path, self.record.source_file.name)

    def test_replacing_unreplied_preliminary_source_invalidates_only_preliminary_results(self):
        self.project.status = LandUseProjectApproval.STATUS_PRELIM_REVIEWED
        self.project.preliminary_kml_file_path = 'old.kml'
        self.project.preliminary_spatial_check_at = timezone.now()
        self.project.preliminary_spatial_feature_count = 9
        self.project.preliminary_is_overlap_artifact = True
        self.project.preliminary_overlapped_relics_info = [{'heritage_id': 1}]
        self.project.save()
        link_project_kml_record(self.project, self.record)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, LandUseProjectApproval.STATUS_RECEIVED)
        self.assertIsNone(self.project.preliminary_spatial_check_at)
        self.assertIsNone(self.project.preliminary_is_overlap_artifact)
        self.assertEqual(self.project.preliminary_overlapped_relics_info, [])
        self.assertEqual(self.project.preliminary_spatial_feature_count, 0)

    def test_formal_link_preserves_completed_preliminary_review(self):
        self.project.status = LandUseProjectApproval.STATUS_PRELIM_SAFE
        self.project.preliminary_kml_file_path = 'preliminary.kml'
        self.project.preliminary_review_date = date.today()
        self.project.preliminary_review_opinion = 'Reference only'
        self.project.preliminary_spatial_check_at = timezone.now()
        self.project.spatial_check_at = timezone.now()
        self.project.spatial_feature_count = 3
        self.project.is_overlap_artifact = True
        self.project.save()
        link_project_kml_record(self.project, self.record)
        self.project.refresh_from_db()
        self.assertEqual(self.project.preliminary_kml_file_path, 'preliminary.kml')
        self.assertEqual(self.project.preliminary_review_opinion, 'Reference only')
        self.assertEqual(self.project.status, LandUseProjectApproval.STATUS_PRELIM_REVIEWED)
        self.assertIsNone(self.project.spatial_check_at)
        self.assertFalse(self.project.is_overlap_artifact)

    def test_same_preliminary_source_does_not_invalidate_successful_check(self):
        link_project_kml_record(self.project, self.record)
        verify_preliminary_spatial_safety(self.project.id)
        self.project.refresh_from_db()
        checked_at = self.project.preliminary_spatial_check_at
        link_project_kml_record(self.project, self.record)
        self.project.refresh_from_db()
        self.assertEqual(self.project.preliminary_spatial_check_at, checked_at)

    def test_formal_link_after_reply_allows_formal_verification(self):
        link_project_kml_record(self.project, self.record)
        verify_preliminary_spatial_safety(self.project.id)
        self.project.refresh_from_db()
        apply_workflow_action(self.project, 'complete_preliminary_review', {
            'preliminary_review_date': date.today(), 'preliminary_review_opinion': 'Reference only',
        })
        other = self.make_record(kmz=True)
        link_project_kml_record(self.project, other)
        self.project.refresh_from_db()
        self.assertEqual(self.project.preliminary_kml_file_path, self.record.source_file.name)
        result = verify_project_spatial_safety(self.project.id)
        self.assertEqual(result['feature_count'], 1)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, LandUseProjectApproval.STATUS_PRELIM_SAFE)

    def test_missing_file_is_rejected_without_changing_project(self):
        self.record.source_file.storage.delete(self.record.source_file.name)
        with self.assertRaisesMessage(ValueError, '文件'):
            link_project_kml_record(self.project, self.record)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.kml_record_id)

    def test_unlinked_formal_file_does_not_satisfy_preliminary_requirement(self):
        self.project.kml_file_path = self.record.source_file.name
        self.project.save()
        self.assertFalse(build_workflow_todos(self.project, '')[0]['enabled'])
        with self.assertRaisesMessage(ValueError, '尚未上传初步选址'):
            verify_preliminary_spatial_safety(self.project.id)

    def test_link_api_then_detail_and_preliminary_verification(self):
        user = get_user_model().objects.create_superuser('project-admin', password='test-password')
        self.client.force_login(user)
        response = self.client.post(
            '/api/v1/projects/create/', json.dumps({
                'project_name': 'API created project', 'company_name': 'Test company',
                'incoming_doc_date': date.today().isoformat(),
            }), content_type='application/json', secure=True,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.project = LandUseProjectApproval.objects.get(id=response.json()['project_id'])
        base = f'/api/v1/projects/{self.project.id}/'
        response = self.client.post(
            base + 'link-kml-record/', json.dumps({'kml_record_id': self.record.id}),
            content_type='application/json', secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.project.refresh_from_db()
        self.assertEqual(self.project.preliminary_kml_file_path, self.record.source_file.name)
        response = self.client.get(base, secure=True)
        self.assertTrue(response.json()['data']['guide']['todos'][0]['enabled'])
        response = self.client.post(
            base + 'verify-spatial-safety/?preliminary=1', '{}',
            content_type='application/json', secure=True,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])
