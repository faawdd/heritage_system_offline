from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from .models import HeritageSite, LandUseProjectApproval


class HeritageDashboardKanerjingFilterTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.user = user_model.objects.create_user(
			username='staff_user',
			password='test-pass-123',
			is_staff=True,
		)
		self.client.force_login(self.user)
		self.url = reverse('heritage_classification_stats_api')

		HeritageSite.objects.create(
			name='吐峪沟石窟',
			sip_code='S001',
			category='SKT',
			level='GB',
			address='鄯善县吐峪沟乡示例地址',
			longitude=90.0,
			latitude=42.0,
			description='示例',
			manager='管理员',
		)
		HeritageSite.objects.create(
			name='鲁克沁东坎儿井',
			sip_code='S002',
			category='QT',
			level='SB',
			address='鄯善县鲁克沁镇示例地址',
			longitude=91.0,
			latitude=42.1,
			description='示例',
			manager='管理员',
		)
		HeritageSite.objects.create(
			name='迪坎古井群',
			sip_code='S003',
			category='KRJ',
			level='XB',
			address='鄯善县迪坎镇示例地址',
			longitude=91.1,
			latitude=42.2,
			description='示例',
			manager='管理员',
		)

	def test_default_scope_includes_kanerjing(self):
		response = self.client.get(self.url, {'group_by': 'category'}, secure=True)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['total'], 3)
		self.assertEqual(payload['kanerjing_scope'], 'all')

	def test_only_scope_returns_only_kanerjing_records(self):
		response = self.client.get(self.url, {'group_by': 'category', 'kanerjing_scope': 'only'}, secure=True)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['total'], 2)
		self.assertCountEqual(payload['labels'], ['其他', '坎儿井'])
		self.assertCountEqual(payload['data'], [1, 1])

	def test_exclude_scope_removes_kanerjing_records(self):
		response = self.client.get(self.url, {'group_by': 'category', 'kanerjing_scope': 'exclude'}, secure=True)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['total'], 1)
		self.assertEqual(payload['labels'], ['石窟寺及石刻'])
		self.assertEqual(payload['data'], [1])


class ProjectCreateApiAuthenticationTests(TestCase):
	url = '/api/v1/projects/create/'
	payload = {
		'project_name': '离线项目创建测试',
		'company_name': '测试建设单位',
		'incoming_doc_date': '2026-10-08',
	}

	def setUp(self):
		user_model = get_user_model()
		self.admin = user_model.objects.create_superuser(username='project_admin', password='test-pass-123')
		self.normal_user = user_model.objects.create_user(username='project_user', password='test-pass-123')

	def _post_with_token(self, user):
		token = str(AccessToken.for_user(user))
		return self.client.post(self.url, self.payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')

	def _get_with_token(self, url, user):
		token = str(AccessToken.for_user(user))
		return self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {token}')

	def test_anonymous_request_receives_json_unauthorized_response(self):
		response = self.client.post(self.url, self.payload, content_type='application/json')

		self.assertEqual(response.status_code, 401)
		self.assertEqual(response['Content-Type'], 'application/json')

	def test_authenticated_non_admin_receives_forbidden_response(self):
		response = self._post_with_token(self.normal_user)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json()['message'], '需要管理权限')

	def test_management_admin_can_create_project_with_jwt(self):
		response = self._post_with_token(self.admin)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertTrue(
			LandUseProjectApproval.objects.filter(
				project_name=self.payload['project_name'],
				company_name=self.payload['company_name'],
			).exists()
		)

	def test_management_admin_can_list_projects_with_jwt(self):
		self._post_with_token(self.admin)

		response = self._get_with_token('/api/v1/projects/', self.admin)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertEqual(len(response.json()['rows']), 1)

	def test_management_admin_can_read_project_detail_with_jwt(self):
		created = self._post_with_token(self.admin)
		project_id = created.json()['project_id']

		response = self._get_with_token(f'/api/v1/projects/{project_id}/', self.admin)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertEqual(response.json()['data']['id'], project_id)


class HeritagePreviewRenderTests(TestCase):
	def test_preview_uses_configured_region_and_record_fields(self):
		from django.test import override_settings
		from .models import ImmovableHeritage

		user = get_user_model().objects.create_superuser(username="preview_admin", password="test-pass-123")
		self.client.force_login(user)
		heritage = ImmovableHeritage.objects.create(
			name="测试遗址", era="清代", category="GJZ", protection_level="XB",
			province="测试省", city="测试市", county="测试县", address="测试路1号",
			longitude=90.1, latitude=42.1, management_unit="测试管理所",
		)

		with override_settings(SYSTEM_REGION="测试县"):
			response = self.client.get(f"/mobile/collect/{heritage.pk}/preview/", secure=True)

		self.assertEqual(response.status_code, 200)
		html = response.content.decode()
		self.assertIn("测试县不可移动文物采集", html)
		self.assertIn("测试管理所", html)
		self.assertNotIn("鄯善县", html)
		self.assertNotIn("文化体育广播电视和旅游局", html)
