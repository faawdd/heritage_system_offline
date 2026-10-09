from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.role_templates import ROLE_TEMPLATES


class RoleManagementAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('init_user_groups', verbosity=0)
        cls.admin = User.objects.create_user('role_admin', password='x')
        cls.admin.groups.add(Group.objects.get(name='管理员'))
        cls.limited = User.objects.create_user('role_limited', password='x')
        cls.limited.groups.add(Group.objects.get(name='管理员用户组'))
        cls.superuser = User.objects.create_superuser('role_super', password='x')

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_templates_are_listed_with_permissions(self):
        response = self.client_for(self.admin).get('/api/v1/system/role-templates/')
        self.assertEqual(response.status_code, 200)
        keys = {row['key'] for row in response.json()['rows']}
        self.assertEqual(keys, set(ROLE_TEMPLATES))

    def test_inspector_template_permissions(self):
        group = Group.objects.get(name='文物看护员')
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertIn('add_inspectionrecord', codenames)
        self.assertNotIn('delete_heritagesite', codenames)
        self.assertNotIn('add_user', codenames)

    def test_create_role_from_template_and_manual(self):
        client = self.client_for(self.superuser)
        response = client.post('/api/v1/system/roles/', {'name': '巡查组A', 'template': '文物看护员'}, format='json')
        self.assertEqual(response.status_code, 201)
        role = Group.objects.get(name='巡查组A')
        self.assertEqual(
            set(role.permissions.values_list('id', flat=True)),
            set(Group.objects.get(name='文物看护员').permissions.values_list('id', flat=True)),
        )
        perm = Permission.objects.filter(codename='view_heritagesite').first()
        response = client.post('/api/v1/system/roles/', {'name': '自定义B', 'permission_ids': [perm.id]}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Group.objects.get(name='自定义B').permissions.count(), 1)

    def test_duplicate_and_builtin_names_rejected(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.post('/api/v1/system/roles/', {'name': '文物看护员'}, format='json').status_code, 400)
        self.assertEqual(client.post('/api/v1/system/roles/', {'name': '  '}, format='json').status_code, 400)

    def test_limited_admin_cannot_write(self):
        response = self.client_for(self.limited).post('/api/v1/system/roles/', {'name': 'X'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Group.objects.filter(name='X').exists())

    def test_builtin_group_is_protected(self):
        client = self.client_for(self.admin)
        inspector = Group.objects.get(name='文物看护员')
        self.assertEqual(client.patch(f'/api/v1/system/roles/{inspector.id}/', {'name': '改名'}, format='json').status_code, 400)
        self.assertEqual(client.delete(f'/api/v1/system/roles/{inspector.id}/').status_code, 400)
        self.assertEqual(
            client.put(f'/api/v1/system/roles/{inspector.id}/permissions/', {'permission_ids': []}, format='json').status_code,
            400,
        )

    def test_apply_template_restores_builtin_permissions(self):
        inspector = Group.objects.get(name='文物看护员')
        expected = inspector.permissions.count()
        inspector.permissions.clear()
        response = self.client_for(self.admin).post(f'/api/v1/system/roles/{inspector.id}/apply-template/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(inspector.permissions.count(), expected)

    def test_rename_and_delete_custom_role(self):
        client = self.client_for(self.admin)
        role = Group.objects.create(name='临时角色')
        self.assertEqual(client.patch(f'/api/v1/system/roles/{role.id}/', {'name': '临时角色2'}, format='json').status_code, 200)
        role.refresh_from_db()
        self.assertEqual(role.name, '临时角色2')

        member = User.objects.create_user('member', password='x')
        member.groups.add(role)
        self.assertEqual(client.delete(f'/api/v1/system/roles/{role.id}/').status_code, 400)
        member.groups.remove(role)
        self.assertEqual(client.delete(f'/api/v1/system/roles/{role.id}/').status_code, 200)
        self.assertFalse(Group.objects.filter(id=role.id).exists())

    def test_cannot_grant_permissions_not_held(self):
        client = self.client_for(self.admin)
        role = Group.objects.create(name='提权测试')
        perm = Permission.objects.get(codename='add_permission')
        self.assertFalse(self.admin.has_perm('auth.add_permission'))
        response = client.put(f'/api/v1/system/roles/{role.id}/permissions/', {'permission_ids': [perm.id]}, format='json')
        self.assertEqual(response.status_code, 403)
