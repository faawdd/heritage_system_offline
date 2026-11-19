import io
import json
import tempfile
import zipfile
from unittest import mock
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from core.services.ai_service import AIConfig, chat_completion, get_ai_config, list_models
from core.services.project_import_service import analyze_project_files, collect_import_files, create_project_from_files
from core.services import smart_import_jobs
from system.models import SystemConfig


class AIServiceTests(TestCase):
    def test_legacy_deepseek_config_is_read_by_unified_service(self):
        SystemConfig.objects.create(key='deepseek.api_key', value='legacy-key')
        SystemConfig.objects.create(key='deepseek.base_url', value='https://legacy.example/v1')
        SystemConfig.objects.create(key='deepseek.model', value='legacy-model')

        config = get_ai_config()

        self.assertEqual(config.provider, 'deepseek')
        self.assertEqual(config.api_key, 'legacy-key')
        self.assertEqual(config.base_url, 'https://legacy.example/v1')
        self.assertEqual(config.model, 'legacy-model')

    def test_non_deepseek_provider_does_not_inherit_deepseek_credentials(self):
        SystemConfig.objects.create(key='ai.provider', value='openai')
        SystemConfig.objects.create(key='deepseek.api_key', value='legacy-key')
        SystemConfig.objects.create(key='deepseek.base_url', value='https://legacy.example/v1')

        config = get_ai_config()

        self.assertEqual(config.provider, 'openai')
        self.assertEqual(config.api_key, '')
        self.assertEqual(config.base_url, 'https://api.openai.com/v1')

    @patch('core.services.ai_service.requests.get')
    def test_ollama_model_detection_uses_local_tags_api(self, request_get):
        request_get.return_value.raise_for_status.return_value = None
        request_get.return_value.json.return_value = {
            'models': [{'name': 'qwen2.5:7b'}, {'model': 'gemma3:4b'}]
        }
        config = AIConfig(
            provider='ollama',
            api_key='',
            base_url='http://127.0.0.1:11434',
            model='qwen2.5:7b',
        )

        self.assertEqual(list_models(config), ['gemma3:4b', 'qwen2.5:7b'])
        request_get.assert_called_once()
        self.assertTrue(request_get.call_args.args[0].endswith('/api/tags'))

    @patch('core.services.ai_service.requests.post')
    def test_ollama_chat_completion_caps_prediction_tokens(self, request_post):
        request_post.return_value.raise_for_status.return_value = None
        request_post.return_value.json.return_value = {
            'message': {'content': '{"ok": true}'}
        }
        config = AIConfig(
            provider='ollama',
            api_key='',
            base_url='http://127.0.0.1:11434',
            model='qwen2.5:7b',
            max_tokens=500,
        )

        result = chat_completion([{'role': 'user', 'content': 'hello'}], config=config)

        self.assertEqual(result, '{"ok": true}')
        payload = request_post.call_args.kwargs['json']
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options']['num_predict'], 500)


class ProjectSmartImportTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.media.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)

    def make_zip_upload(self):
        pdf = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(pdf)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('资料/项目说明.pdf', pdf.getvalue())
            zipped.writestr('矢量/选址.kml', '<kml><Placemark><name>选址</name></Placemark></kml>')
            zipped.writestr('照片/现场.jpg', b'not-a-real-image')
        return SimpleUploadedFile('项目资料.zip', archive.getvalue(), content_type='application/zip')

    def test_zip_files_are_safely_flattened_for_analysis_and_import(self):
        files = collect_import_files([self.make_zip_upload()])
        self.assertEqual(len(files), 3)
        self.assertTrue(all(item.name.startswith('项目资料/') for item in files))

    @patch('core.services.project_import_service.chat_completion')
    def test_analysis_sends_compact_manifest_and_returns_editable_preview(self, completion):
        completion.return_value = json.dumps({
            'project_name': '示例道路项目',
            'company_name': '示例公司',
            'incoming_doc_date': '2026-01-02',
            'attachments': [
                {'name': '项目资料/资料/项目说明.pdf', 'file_type': 'official_doc', 'category': 'incoming_request', 'reason': '查询函'},
                {'name': '项目资料/矢量/选址.kml', 'file_type': 'preliminary_kml', 'category': 'other', 'reason': '矢量'},
                {'name': '项目资料/照片/现场.jpg', 'file_type': 'field_photo', 'category': 'other', 'reason': '照片'},
            ],
        }, ensure_ascii=False)
        files = collect_import_files([self.make_zip_upload()])

        preview = analyze_project_files(files)

        self.assertEqual(preview['project_name'], '示例道路项目')
        self.assertEqual(preview['file_count'], 3)
        self.assertIn('12000', preview['token_strategy'])
        prompt = completion.call_args.args[0][1]['content']
        self.assertIn('manifest', prompt)
        self.assertNotIn('not-a-real-image', prompt)

    def test_confirmed_import_creates_project_and_classifies_attachments(self):
        files = collect_import_files([self.make_zip_upload()])
        metadata = {
            'project_name': '示例道路项目',
            'company_name': '示例公司',
            'incoming_doc_date': '2026-01-02',
            'attachments': [
                {'name': '项目资料/资料/项目说明.pdf', 'file_type': 'official_doc', 'category': 'incoming_request'},
                {'name': '项目资料/矢量/选址.kml', 'file_type': 'preliminary_kml', 'category': 'other'},
                {'name': '项目资料/照片/现场.jpg', 'file_type': 'field_photo', 'category': 'other'},
            ],
        }

        project = create_project_from_files(files, metadata, user=None)

        self.assertEqual(project.project_name, '示例道路项目')
        self.assertTrue(project.preliminary_kml_file_path)
        self.assertEqual(project.documents.count(), 1)
        self.assertEqual(project.field_photos.count(), 1)

    def test_analysis_api_returns_job_immediately_and_exposes_result(self):
        user = get_user_model().objects.create_superuser('ai-import-admin', password='test-password')
        self.client.force_login(user)

        class InlineThread:
            def __init__(self, target, args, **kwargs):
                self.target = target
                self.args = args

            def start(self):
                self.target(*self.args)

        expected = {
            'project_name': '异步项目',
            'company_name': '异步单位',
            'incoming_doc_date': '',
            'attachments': [],
            'warnings': [],
        }
        with mock.patch.object(smart_import_jobs.threading, 'Thread', InlineThread), \
                mock.patch.object(smart_import_jobs, 'analyze_project_files', return_value=expected):
            started = self.client.post(
                '/api/v1/projects/smart-import/analyze/',
                {'files': SimpleUploadedFile('说明.txt', b'project text')},
                secure=True,
            )
            self.assertEqual(started.status_code, 202)
            job_id = started.json()['data']['job_id']
            status_response = self.client.get(
                f'/api/v1/projects/smart-import/jobs/{job_id}/',
                secure=True,
            )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()['data']['status'], 'succeeded')
        self.assertEqual(status_response.json()['data']['result'], expected)
