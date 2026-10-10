from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import LandUseProjectApproval, LandUseProjectOperationLog, UserManagementAudit
from core.role_templates import ensure_builtin_groups
from system.admin_labels import permission_name
from system.admin_sync import sync_admin_permissions
from system.models import LoginLog, OperationLog


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=False)
class AdminManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_builtin_groups()
        Group.objects.get_or_create(name='超级管理员')
        cls.superuser = User.objects.create_superuser('audit_super', password='x')
        cls.admin = User.objects.create_user('audit_admin', password='x')
        cls.other_admin = User.objects.create_user('audit_other_admin', password='x')
        cls.limited = User.objects.create_user('audit_limited', password='x')
        cls.inspector = User.objects.create_user('audit_inspector', password='x')
        cls.other_inspector = User.objects.create_user('audit_other_inspector', password='x')
        cls.plain = User.objects.create_user('audit_plain', password='x')
        for user, group in [
            (cls.admin, '管理员'), (cls.other_admin, '管理员'), (cls.limited, '管理员用户组'),
            (cls.inspector, '文物看护员'), (cls.other_inspector, '文物看护员'),
        ]:
            user.groups.add(Group.objects.get(name=group))
        cls.project = LandUseProjectApproval.objects.create(project_name='测试项目')
        for user in [cls.superuser, cls.admin, cls.other_admin, cls.limited, cls.inspector, cls.other_inspector]:
            LoginLog.objects.create(user=user, username=user.username, success=True)
            LoginLog.objects.create(username=user.username, success=False)
            OperationLog.objects.create(operator=user, module='system_role', action='create_role', success=True)
            UserManagementAudit.objects.create(operator=user, action='add_user', target_user=cls.plain)
            LandUseProjectOperationLog.objects.create(project=cls.project, operator=user, action='submit', action_label='提交审批')
            LogEntry.objects.create(
                user=user, content_type=ContentType.objects.get_for_model(User), object_id=str(cls.plain.pk),
                object_repr=cls.plain.username, action_flag=ADDITION, change_message='[{"added": {}}]',
            )
        LoginLog.objects.create(username='unrelated', success=False)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_all_log_sources_enforce_scope(self):
        expectations = [
            (self.superuser, {self.superuser.username, self.admin.username, self.other_admin.username,
                              self.limited.username, self.inspector.username, self.other_inspector.username}),
            (self.admin, {self.admin.username, self.inspector.username, self.other_inspector.username}),
            (self.limited, {self.limited.username, self.inspector.username, self.other_inspector.username}),
            (self.inspector, {self.inspector.username}),
        ]
        for source in ['login', 'operation', 'django', 'user', 'project']:
            for user, names in expectations:
                with self.subTest(source=source, user=user.username):
                    response = self.client_for(user).get('/api/v1/system/audit-log/', {'source': source, 'page_size': 100})
                    self.assertEqual(response.status_code, 200)
                    expected = names | {'unrelated'} if source == 'login' and user == self.superuser else names
                    self.assertEqual({row['operator_name'] for row in response.data['rows']}, expected)
                    self.assertEqual(response.data['pagination']['total'], len(expected) + len(names) if source == 'login' else len(names))

    def test_multi_group_inspectors_do_not_leak_admin_logs(self):
        self.other_admin.groups.add(Group.objects.get(name='文物看护员'))
        response = self.client_for(self.admin).get('/api/v1/system/audit-log/', {'source': 'operation'})
        self.assertNotIn(self.other_admin.username, {row['operator_name'] for row in response.data['rows']})

    def test_legacy_log_routes_also_enforce_scope(self):
        for path in ['login-log/', 'operation-log/']:
            response = self.client_for(self.inspector).get('/api/v1/system/' + path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual({row['operator_name'] for row in response.data['rows']}, {self.inspector.username})

    def test_log_permissions_and_anonymous_rejected(self):
        self.assertEqual(APIClient().get('/api/v1/system/audit-log/').status_code, 401)
        self.assertEqual(self.client_for(self.plain).get('/api/v1/system/audit-log/').status_code, 403)
        permission = Permission.objects.get(content_type__app_label='system', codename='view_operationlog')
        self.plain.user_permissions.add(permission)
        self.assertEqual(self.client_for(User.objects.get(pk=self.plain.pk)).get('/api/v1/system/audit-log/', {'source': 'operation'}).status_code, 200)
        self.assertEqual(self.client_for(self.plain).get('/api/v1/system/audit-log/', {'source': 'django'}).status_code, 403)
        self.assertEqual(self.client_for(self.superuser).delete('/api/v1/system/audit-log/').status_code, 405)

    def test_invalid_queries_and_keyword_cannot_expand_scope(self):
        client = self.client_for(self.inspector)
        for query in [{'page': 'wrong'}, {'page': 0}, {'page_size': 101}, {'source': 'unknown'}, {'start': 'bad'}]:
            self.assertEqual(client.get('/api/v1/system/audit-log/', query).status_code, 400)
        response = client.get('/api/v1/system/audit-log/', {'keyword': self.admin.username})
        self.assertEqual(response.data['pagination']['total'], 0)
        response = client.get('/api/v1/system/audit-log/', {'source': 'operation', 'keyword': '新增用户组'})
        self.assertEqual(response.data['pagination']['total'], 1)

    def test_log_labels_are_chinese(self):
        for source, action in [('operation', '新增用户组'), ('django', '新增'), ('user', '创建用户'), ('project', '提交审批')]:
            response = self.client_for(self.inspector).get('/api/v1/system/audit-log/', {'source': source})
            self.assertEqual(response.data['rows'][0]['action'], action)
        response = self.client_for(self.inspector).get('/api/v1/system/audit-log/', {'source': 'django'})
        self.assertEqual(response.data['rows'][0]['detail'], '新增记录')
        self.assertEqual(response.data['rows'][0]['module'], '用户')

    def test_permission_catalog_is_chinese_and_preserves_codes(self):
        response = self.client_for(self.admin).get('/api/v1/system/permissions/')
        self.assertEqual(response.status_code, 200)
        user_add = next(row for row in response.data['rows'] if row['app_label'] == 'auth' and row['codename'] == 'add_user')
        self.assertEqual(user_add['name'], '新增用户')
        self.assertEqual(user_add['model_name'], '用户')
        self.assertTrue(user_add['grantable'])
        permission_add = next(row for row in response.data['rows'] if row['codename'] == 'add_permission')
        self.assertFalse(permission_add['grantable'])
        self.assertEqual(self.client_for(self.inspector).get('/api/v1/system/permissions/').status_code, 403)

    def test_migrate_translation_is_idempotent_and_preserves_custom_names(self):
        permission = Permission.objects.get(codename='add_user', content_type__app_label='auth')
        Permission.objects.filter(pk=permission.pk).update(name='Can add user')
        custom = Permission.objects.create(content_type=permission.content_type, codename='export_accounts', name='导出账户')
        sync_admin_permissions(None, 'default')
        sync_admin_permissions(None, 'default')
        permission.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(permission.name, '新增用户')
        self.assertEqual(custom.name, '导出账户')

    def test_read_only_group_cannot_manage_users_or_roles(self):
        client = self.client_for(self.limited)
        self.assertEqual(client.get('/api/v1/system/roles/').status_code, 200)
        self.assertEqual(client.get('/api/v1/system/users/').status_code, 200)
        self.assertEqual(client.post('/api/v1/system/roles/', {'name': 'forbidden'}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'/api/v1/system/users/{self.inspector.pk}/', {'is_active': False}, format='json').status_code, 403)

    def test_direct_user_permissions_keep_inherited_permissions(self):
        client = self.client_for(self.superuser)
        permission = Permission.objects.get(codename='view_permission', content_type__app_label='auth')
        path = f'/api/v1/system/users/{self.inspector.pk}/permissions/'
        response = client.put(path, {'permission_ids': [permission.pk]}, format='json')
        self.assertEqual(response.status_code, 200)
        response = client.get(path)
        self.assertEqual(response.data['data']['permission_ids'], [permission.pk])
        self.assertIn('system.view_loginlog', response.data['data']['effective_permissions'])
        self.assertEqual(client.put(path, {'permission_ids': [999999]}, format='json').status_code, 400)
        self.assertTrue(OperationLog.objects.filter(action='assign_user_permissions', operator=self.superuser).exists())

    def test_admin_cannot_grant_unowned_permissions_or_modify_superuser(self):
        client = self.client_for(self.admin)
        permission = Permission.objects.get(codename='add_permission', content_type__app_label='auth')
        path = f'/api/v1/system/users/{self.inspector.pk}/permissions/'
        self.assertEqual(client.put(path, {'permission_ids': [permission.pk]}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'/api/v1/system/users/{self.superuser.pk}/', {'is_active': False}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'/api/v1/system/users/{self.inspector.pk}/', {
            'group_ids': [Group.objects.get(name='超级管理员').pk],
        }, format='json').status_code, 403)

    def test_profile_capabilities_match_effective_permissions(self):
        for user, can_manage in [(self.admin, True), (self.limited, False), (self.inspector, False)]:
            response = self.client_for(user).get('/api/v1/system/profile/')
            capabilities = response.data['data']['capabilities']
            self.assertEqual(capabilities['change_groups'], can_manage)
            self.assertTrue(capabilities['view_logs'])
            self.assertEqual(set(capabilities['log_sources']), {'login', 'operation', 'django', 'user', 'project'})

    def test_super_admin_group_template_restoration(self):
        group = Group.objects.get(name='超级管理员')
        path = f'/api/v1/system/roles/{group.pk}/apply-template/'
        self.assertEqual(self.client_for(self.admin).post(path, {}, format='json').status_code, 403)
        self.assertEqual(self.client_for(self.superuser).post(path, {}, format='json').status_code, 200)
        self.assertEqual(group.permissions.count(), Permission.objects.count())

    def test_log_count_and_time_filter_are_scoped(self):
        response = self.client_for(self.inspector).get('/api/v1/system/audit-log/', {
            'source': 'operation', 'start': timezone.now().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['pagination']['total'], 0)

    def test_custom_business_permission_name_is_preserved(self):
        permission = Permission.objects.create(
            content_type=ContentType.objects.get_for_model(User), codename='view_private_users', name='查看特殊用户清单',
        )
        self.assertEqual(permission_name(permission), '查看特殊用户清单')
