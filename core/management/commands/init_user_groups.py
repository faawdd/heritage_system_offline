"""
管理命令：初始化用户组和权限
用法: 
    python manage.py init_user_groups          # 初始化用户组（不删除现有数据）
    python manage.py init_user_groups --reset  # 完全重置用户组和权限

权限体系说明：
    看护员    → 仅巡查上报功能 (最小化权限)
    管理员    → 大部分管理功能 (不影响底层数据安全)
    超级管理员 → 完全访问权限
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.models import InspectionRecord, HeritageSite, ProjectAudit, UserProfile


class Command(BaseCommand):
    help = '初始化用户组和权限配置 - 三层权限体系'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='重置所有用户组和权限（谨慎使用！）',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='仅检查权限配置，不进行修改',
        )

    def handle(self, *args, **options):
        """执行初始化"""
        # 检查模式
        if options.get('check_only'):
            self.stdout.write(self.style.HTTP_INFO('🔍 检查权限配置...\n'))
            self.check_permission_config()
            return

        # 重置模式
        if options['reset']:
            confirm = input(
                self.style.WARNING('⚠️  警告：这将删除所有用户组及其权限配置！\n')
                + '      是否继续？(yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('操作已取消'))
                return
            
            self.stdout.write(self.style.WARNING('⚠️  开始重置用户组...'))
            Group.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ 用户组已清空\n'))

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('📋 初始化用户组和权限配置\n'))

        # ============================================================================
        # 权限配置定义：三层权限体系
        # ============================================================================
        groups_config = {
            # 🔵 第一层：文物看护员（巡查人员）
            '文物看护员': {
                'description': '巡查人员，仅能使用文物点巡查上报功能',
                'permissions': [
                    # 文物档案：仅查看权限
                    'view_heritagesite',
                    # 巡查记录：完整权限（但视图层会限制为自己的记录）
                    'add_inspectionrecord',
                    'change_inspectionrecord',
                    'view_inspectionrecord',
                    # 个人资料：修改自己的信息
                    'change_userprofile',
                    'view_userprofile',
                ],
            },
            # 🟡 第二层：管理员（文保科工作人员）
            '管理员': {
                'description': '文保科工作人员和领导，拥有大部分管理权限（不影响底层数据安全）',
                'permissions': [
                    # 不可移动文物档案：增删改查
                    'add_heritagesite',
                    'change_heritagesite',
                    'view_heritagesite',
                    # 巡查记录：完整权限（包括删除）
                    'add_inspectionrecord',
                    'change_inspectionrecord',
                    'view_inspectionrecord',
                    'delete_inspectionrecord',
                    # 项目建设审批：完整权限
                    'add_projectaudit',
                    'change_projectaudit',
                    'view_projectaudit',
                    'delete_projectaudit',
                    # 坐标数据：完整权限
                    'add_coordinate',
                    'change_coordinate',
                    'view_coordinate',
                    'delete_coordinate',
                    # 用户管理：创建和修改（不能删除）
                    'add_user',
                    'change_user',
                    'view_user',
                    # 用户组：查看和编辑（不能删除）
                    'add_group',
                    'change_group',
                    'view_group',
                    # 用户资料：完整权限
                    'add_userprofile',
                    'change_userprofile',
                    'view_userprofile',
                ],
            },
            # 🔴 第三层：超级管理员（系统最高权限）
            '超级管理员': {
                'description': '系统最高权限，具有所有功能访问权限',
                'permissions': 'all',  # 特殊标记：授予所有权限
            },
        }

        # 创建或更新用户组
        for group_name, config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            verb = '创建' if created else '更新'
            
            # 设置权限
            if config['permissions'] == 'all':
                # 超级管理员：授予所有权限
                all_permissions = Permission.objects.all()
                group.permissions.set(all_permissions)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {verb}用户组: {group_name}')
                    + f'\n  📝 描述: {config["description"]}'
                    + f'\n  🔐 权限: 所有权限 ({all_permissions.count()} 个)'
                    + f'\n'
                )
            else:
                # 其他用户组：按指定权限列表授予
                permissions = []
                missing_perms = []
                
                for perm_codename in config['permissions']:
                    try:
                        perm = Permission.objects.get(codename=perm_codename)
                        permissions.append(perm)
                    except Permission.DoesNotExist:
                        missing_perms.append(perm_codename)
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  权限未找到: {perm_codename}')
                        )
                
                group.permissions.set(permissions)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {verb}用户组: {group_name}')
                    + f'\n  📝 描述: {config["description"]}'
                    + f'\n  🔐 权限: {len(permissions)} 个'
                    + (f'\n  ⚠️  缺失权限: {len(missing_perms)} 个' if missing_perms else '')
                    + f'\n'
                )

        # 配置超级管理员用户
        self._setup_superuser()

        # 权限审计
        self._audit_permissions()
        
        self.stdout.write('=' * 70)
        self.stdout.write(
            self.style.SUCCESS('✅ 用户组和权限初始化完成！\n')
        )
        self.print_summary()

    def _setup_superuser(self):
        """配置超级管理员用户"""
        self.stdout.write(self.style.WARNING('\n🔧 配置特殊用户...\n'))
        
        try:
            user = User.objects.get(username='wenwu1')
            super_admin_group = Group.objects.get(name='超级管理员')
            
            # 清除其他组并添加到超级管理员组
            user.groups.clear()
            user.groups.add(super_admin_group)
            
            # 设置为Django超级用户和员工
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS('✓ 用户 wenwu1 已配置为超级管理员')
                + '\n  🔐 权限级别: 最高'
                + '\n'
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('✗ 用户 wenwu1 不存在，请先创建该用户')
                + '\n  💡 运行命令: python manage.py createsuperuser'
                + '\n'
            )

    def _audit_permissions(self):
        """审计权限配置"""
        self.stdout.write(self.style.HTTP_INFO('\n🔍 权限配置审计\n'))
        
        # 检查权限记录
        all_perms = Permission.objects.all().count()
        admin_group = Group.objects.filter(name='管理员').first()
        inspector_group = Group.objects.filter(name='文物看护员').first()
        
        if admin_group and inspector_group:
            admin_perms = admin_group.permissions.count()
            inspector_perms = inspector_group.permissions.count()
            
            self.stdout.write(
                f'  系统总权限数: {all_perms}\n'
                f'  管理员权限数: {admin_perms}\n'
                f'  看护员权限数: {inspector_perms}\n'
            )

    def check_permission_config(self):
        """检查权限配置（不修改）"""
        self.stdout.write(self.style.HTTP_INFO('🔍 正在检查权限配置...\n'))
        
        groups = Group.objects.all().order_by('name')
        for group in groups:
            perm_count = group.permissions.count()
            users_count = group.user_set.count()
            self.stdout.write(
                f'  • {group.name}'
                f'\n    权限: {perm_count} | 用户: {users_count}'
            )
        
        # 检查超级管理员
        super_admin_group = Group.objects.filter(name='超级管理员').first()
        if super_admin_group:
            super_admins = super_admin_group.user_set.all()
            self.stdout.write(f'\n  超级管理员 ({super_admins.count()}):\n')
            for user in super_admins:
                status = '✅' if user.is_superuser else '❌'
                self.stdout.write(f'    {status} {user.username} ({user.first_name or "无"})')


    def print_summary(self):
        """打印配置总结信息"""
        self.stdout.write(self.style.HTTP_INFO('📊 系统用户组配置总结\n'))
        
        groups = Group.objects.all().order_by('name')
        if not groups.exists():
            self.stdout.write(self.style.WARNING('  [暂无用户组]'))
            return
        
        # 构建总结表
        for group in groups:
            perm_count = group.permissions.count()
            users_count = group.user_set.count()
            
            # 显示用户组信息
            group_icon = '🟡' if group.name == '管理员' else ('🔵' if group.name == '文物看护员' else '🔴')
            self.stdout.write(
                f'  {group_icon} {group.name}'
                f'\n     · 权限数: {perm_count}'
                f'\n     · 用户数: {users_count}'
            )
            
            # 显示该组下的用户
            users = group.user_set.all()
            if users.exists():
                for user in users:
                    superuser_mark = '👑' if user.is_superuser else '  '
                    self.stdout.write(
                        f'     {superuser_mark} {user.username} ({user.first_name or "无"})'
                    )
            self.stdout.write('')
        
        # 显示权限占比
        all_perms = Permission.objects.all().count()
        admin_group = Group.objects.filter(name='管理员').first()
        if admin_group:
            admin_perm_ratio = (admin_group.permissions.count() / all_perms * 100) if all_perms > 0 else 0
            self.stdout.write(
                self.style.HTTP_INFO(f'\n📈 权限占比\n')
                + f'  · 系统总权限: {all_perms}\n'
                + f'  · 管理员占比: {admin_perm_ratio:.1f}%\n'
            )

