"""
管理命令：重置超级管理员密码

用法:
    python manage.py reset_super_admin_password --password NewPass123
    python manage.py reset_super_admin_password --username admin --password NewPass123
    python manage.py reset_super_admin_password --username admin --password NewPass123 --create-if-missing

说明:
    - 若未指定 username，且系统仅有一个超级管理员，则自动重置该账号。
    - 若指定用户名但账号不存在，且开启 --create-if-missing，则自动创建超级管理员。
    - 会自动确保该用户属于“超级管理员”用户组，并保持 is_staff / is_superuser / is_active 为 True。
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError


ROLE_SUPER_ADMIN = '超级管理员'
ROLE_ADMIN = '管理员'


class Command(BaseCommand):
    help = '重置或创建超级管理员密码'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='',
            help='要重置的超级管理员用户名；不填则在仅有一个超级管理员时自动选择',
        )
        parser.add_argument(
            '--password',
            required=True,
            help='新的超级管理员密码',
        )
        parser.add_argument(
            '--create-if-missing',
            action='store_true',
            help='账号不存在时自动创建',
        )

    def handle(self, *args, **options):
        password = str(options.get('password') or '').strip()
        username = str(options.get('username') or '').strip()
        create_if_missing = bool(options.get('create_if_missing'))

        if not password:
            raise CommandError('password 不能为空')

        super_group, _ = Group.objects.get_or_create(name=ROLE_SUPER_ADMIN)
        admin_group, _ = Group.objects.get_or_create(name=ROLE_ADMIN)
        super_group.permissions.set(Permission.objects.all())
        admin_group.permissions.set(
            Permission.objects.exclude(content_type__app_label__in=['auth', 'contenttypes', 'sessions', 'admin'])
        )

        User = get_user_model()

        user = None
        if username:
            user = User.objects.filter(username=username).first()
            if user is None and not create_if_missing:
                raise CommandError(f'用户 {username} 不存在，如需自动创建请加 --create-if-missing')
        else:
            super_admins = list(
                User.objects.filter(is_active=True, is_superuser=True).order_by('id')
            )
            if len(super_admins) == 1:
                user = super_admins[0]
                username = user.username
            elif len(super_admins) == 0:
                if not create_if_missing:
                    raise CommandError('系统中没有超级管理员，请指定 --username 并配合 --create-if-missing 创建')
            else:
                raise CommandError('检测到多个超级管理员，请显式指定 --username')

        if user is None:
            user = User.objects.create_user(
                username=username,
                password=password,
                is_staff=True,
                is_superuser=True,
                is_active=True,
                first_name='超级管理员',
            )
            action = 'created'
        else:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if not user.first_name:
                user.first_name = '超级管理员'
            user.save()
            action = 'updated'

        user.groups.add(super_group)

        self.stdout.write(
            self.style.SUCCESS(
                f'超级管理员密码已{ "创建并设置" if action == "created" else "重置" }: {user.username}'
            )
        )
        self.stdout.write(self.style.HTTP_INFO('提示：请妥善保存新密码，离线包可通过该命令随时恢复访问。'))