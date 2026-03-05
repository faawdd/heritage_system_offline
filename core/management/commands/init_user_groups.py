"""
管理命令：初始化用户组和权限
用法: python manage.py init_user_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.models import InspectionRecord, HeritageSite, ProjectAudit


class Command(BaseCommand):
    help = '初始化用户组和权限配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='重置所有用户组（谨慎使用）',
        )

    def handle(self, *args, **options):
        """执行初始化"""
        if options['reset']:
            self.stdout.write(self.style.WARNING('⚠️  开始重置用户组...'))
            Group.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ 用户组已清空'))

        self.stdout.write('=' * 60)
        self.stdout.write('正在初始化用户组和权限配置...\n')

        # 创建三个用户组
        groups_config = {
            '超级管理员': {
                'description': '系统最高权限，具有所有功能访问权限',
                'permissions': 'all',  # 特殊标记：所有权限
            },
            '管理员': {
                'description': '系统管理员，拥有大部分管理权限，不能删除超级管理员',
                'permissions': [
                    'add_heritagesite', 'change_heritagesite', 'view_heritagesite',
                    'add_inspectionrecord', 'change_inspectionrecord', 'view_inspectionrecord', 'delete_inspectionrecord',
                    'add_projectaudit', 'change_projectaudit', 'view_projectaudit', 'delete_projectaudit',
                    'add_coordinate', 'change_coordinate', 'view_coordinate', 'delete_coordinate',
                    'add_user', 'change_user', 'view_user',
                    'add_group', 'change_group', 'view_group',
                    'add_userprofile', 'change_userprofile', 'view_userprofile',
                ],
            },
            '文物看护员': {
                'description': '巡查人员，只能访问文物点巡查上报功能',
                'permissions': [
                    'view_heritagesite',
                    'add_inspectionrecord', 'change_inspectionrecord', 'view_inspectionrecord',
                    'change_userprofile', 'view_userprofile',
                ],
            },
        }

        for group_name, config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            
            # 设置权限
            if config['permissions'] == 'all':
                # 超级管理员：授予所有权限
                all_permissions = Permission.objects.all()
                group.permissions.set(all_permissions)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 创建用户组: {group_name}')
                    + f'\n  描述: {config["description"]}'
                    + f'\n  权限: 所有权限 ({all_permissions.count()} 个)\n'
                )
            else:
                # 其他用户组：按指定权限列表授予
                permissions = []
                for perm_codename in config['permissions']:
                    try:
                        perm = Permission.objects.get(codename=perm_codename)
                        permissions.append(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  权限未找到: {perm_codename}')
                        )
                
                group.permissions.set(permissions)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 创建用户组: {group_name}')
                    + f'\n  描述: {config["description"]}'
                    + f'\n  权限: {len(permissions)} 个\n'
                )

        # 配置 wenwu1 为超级管理员
        self.stdout.write(self.style.WARNING('\n配置特殊用户...'))
        try:
            user = User.objects.get(username='wenwu1')
            super_admin_group = Group.objects.get(name='超级管理员')
            
            # 从其他组中移除
            user.groups.exclude(name='超级管理员').delete()
            user.groups.add(super_admin_group)
            
            # 设置为Django超级用户和员工
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS('✓ 用户 wenwu1 已设置为超级管理员')
                + '\n  权限: 最高级别\n'
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('✗ 用户 wenwu1 不存在，请先创建该用户')
            )

        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS('✓ 用户组和权限初始化完成！\n')
        )
        self.print_summary()

    def print_summary(self):
        """打印总结信息"""
        self.stdout.write(self.style.HTTP_INFO('\n📊 系统用户组配置总结:\n'))
        
        groups = Group.objects.all().order_by('name')
        for group in groups:
            perm_count = group.permissions.count()
            users_count = group.user_set.count()
            self.stdout.write(
                f'  • {group.name}'
                f'\n    └─ 权限数: {perm_count} | 用户数: {users_count}'
            )
        
        # 显示超级管理员信息
        super_admin_group = Group.objects.filter(name='超级管理员').first()
        if super_admin_group:
            super_admins = super_admin_group.user_set.all()
            self.stdout.write(f'\n  超级管理员 ({super_admins.count()} 人):')
            for user in super_admins:
                self.stdout.write(f'    - {user.username} ({user.first_name or "无"})')
