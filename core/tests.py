from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import HeritageSite


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
