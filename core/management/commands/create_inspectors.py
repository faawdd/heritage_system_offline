"""
管理命令：创建基层文物看护员账号
用法：python manage.py create_inspectors --inspectors-file 名单.json --security-questions-file 安全问题.json
     同一名单配合 --reset-passwords 重置密码，或 --delete 删除名单中的账号
"""
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from core.models import InspectionRecord, UserProfile
from core.services.account_security import hash_security_questions

class Command(BaseCommand):
    help = '从部署方提供的名单创建基层文物看护员账号'
    
    # 默认初始密码
    DEFAULT_PASSWORD = 'Heritage2026!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--inspectors-file',
            required=True,
            help='看护员名单 JSON 文件，格式为 [{"name": "姓名", "username": "登录名"}]',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='经交互确认后删除名单中的看护员账号',
        )
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='重置名单中的看护员密码为初始密码',
        )
        parser.add_argument(
            '--security-questions-file',
            help='逐用户安全问题 JSON 文件，键为用户名，值为 3 组 question_id/answer',
        )

    def handle(self, *args, **options):
        try:
            rows = json.loads(Path(options['inspectors_file']).read_text(encoding='utf-8'))
            if not isinstance(rows, list) or not rows:
                raise ValueError('名单必须为非空数组')
            self.INSPECTORS_DATA = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError('名单条目必须为对象')
                name = row.get('name')
                username = row.get('username')
                if not isinstance(name, str) or not name.strip() or not isinstance(username, str) or not username.strip():
                    raise ValueError('每条名单必须提供姓名与登录名')
                self.INSPECTORS_DATA.append((name.strip(), username.strip()))
            if len({username for _, username in self.INSPECTORS_DATA}) != len(self.INSPECTORS_DATA):
                raise ValueError('名单中登录名不能重复')
        except (OSError, ValueError, TypeError) as exc:
            raise CommandError(f'看护员名单文件无效: {exc}') from exc

        # 创建或获取"文物看护员"用户组
        inspector_group, created = Group.objects.get_or_create(name='文物看护员')
        
        if created:
            self.stdout.write(self.style.SUCCESS('已创建用户组"文物看护员"'))
            # 为用户组添加权限：查看和添加巡查记录
            inspection_content_type = ContentType.objects.get_for_model(InspectionRecord)
            permissions = Permission.objects.filter(
                content_type=inspection_content_type,
                codename__in=['add_inspectionrecord', 'change_inspectionrecord', 'view_inspectionrecord']
            )
            inspector_group.permissions.set(permissions)
        
        if options['delete']:
            self.delete_inspectors()
            return

        questions_file = options.get('security_questions_file')
        if not questions_file:
            raise CommandError('创建或重置看护员密码必须提供 --security-questions-file')
        try:
            raw_questions = json.loads(Path(questions_file).read_text(encoding='utf-8'))
            self.security_questions_by_username = {
                username: hash_security_questions(raw_questions[username])
                for _name, username in self.INSPECTORS_DATA
            }
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise CommandError(f'安全问题文件无效或缺少用户条目: {exc}') from exc
        
        if options['reset_passwords']:
            self.reset_passwords()
            return
        
        self.create_inspectors()

    def create_inspectors(self):
        """创建名单中的看护员账户"""
        created_count = 0
        updated_count = 0
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('开始创建名单中的基层文物看护员账号')
        self.stdout.write('='*80 + '\n')
        
        # 获取用户组
        inspector_group = Group.objects.get(name='文物看护员')
        
        # 显示表头
        self.stdout.write(f"{'操作':<6} | {'姓名':<15} | {'登录名':<13} | {'密码状态':<20}")
        self.stdout.write('-' * 80)
        
        for name, phone in self.INSPECTORS_DATA:
            try:
                user, created = User.objects.get_or_create(
                    username=phone,
                    defaults={
                        'first_name': name,
                        'last_name': '看护员',
                        'is_staff': True,  # 允许访问后台
                        'is_active': True,
                    }
                )
                
                # 设置统一的初始密码
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.security_questions = self.security_questions_by_username[phone]
                profile.has_changed_password = False
                profile.failed_login_attempts = 0
                profile.login_locked_until = None
                profile.login_locked = False
                profile.failed_recovery_attempts = 0
                profile.recovery_locked_until = None
                profile.save(update_fields=[
                    'security_questions', 'has_changed_password', 'failed_login_attempts',
                    'login_locked_until', 'login_locked', 'failed_recovery_attempts',
                    'recovery_locked_until',
                ])
                
                # 将用户加入"文物看护员"组
                user.groups.add(inspector_group)
                
                if created:
                    created_count += 1
                    status = '✓ 新建'
                else:
                    updated_count += 1
                    status = '✓ 更新'
                
                self.stdout.write(
                    f'{status:<6} | {name:<15} | {phone:<13} | 首次登录必须修改'
                )
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ 失败   | {name:<15} | {phone:<13} | 错误: {str(e)}'
                ))
        
        self.stdout.write('-' * 80)
        self.stdout.write(self.style.SUCCESS(
            f'\n创建完成！新建 {created_count} 个账号，更新 {updated_count} 个账号\n'
        ))
        
        self.stdout.write('✓ 所有看护员已添加到"文物看护员"用户组')
        self.stdout.write('✓ 看护员可以查看、添加和修改巡查记录\n')
        
        self.stdout.write(self.style.WARNING('⚠️  已设置初始密码；登录后必须修改并完成安全问题确认。\n'))
        
        self.stdout.write('📝 首次登录建议事项：')
        self.stdout.write('  1. 使用名单中的登录名登录：')
        for name, phone in self.INSPECTORS_DATA[:3]:
            self.stdout.write(f'     {name} → 账号: {phone}')
        if len(self.INSPECTORS_DATA) > 3:
            self.stdout.write(f'     ... 等其他 {len(self.INSPECTORS_DATA)-3} 人')
        self.stdout.write('\n  2. 使用管理员告知的初始密码')
        self.stdout.write('  3. 首次登录后系统会提示修改密码')
        self.stdout.write('  4. 修改为更复杂的密码（8位以上，包含大小写和数字）')
        self.stdout.write('  5. 登录后可在"日常办公 → 巡查记录"中添加巡查数据\n')

    def reset_passwords(self):
        """重置名单中的看护员密码"""
        reset_count = 0
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('重置名单中的看护员密码')
        self.stdout.write('='*80 + '\n')
        
        self.stdout.write(f"{'姓名':<15} | {'登录名':<13} | {'密码状态':<20}")
        self.stdout.write('-' * 80)
        
        for name, phone in self.INSPECTORS_DATA:
            try:
                user = User.objects.get(username=phone)
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.security_questions = self.security_questions_by_username[phone]
                profile.has_changed_password = False
                profile.failed_login_attempts = 0
                profile.login_locked_until = None
                profile.login_locked = False
                profile.failed_recovery_attempts = 0
                profile.recovery_locked_until = None
                profile.save(update_fields=[
                    'security_questions', 'has_changed_password', 'failed_login_attempts',
                    'login_locked_until', 'login_locked', 'failed_recovery_attempts',
                    'recovery_locked_until',
                ])
                reset_count += 1
                
                self.stdout.write(
                    f'{name:<15} | {phone:<13} | 首次登录必须修改'
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'{name:<15} | {phone:<13} | 账户不存在'
                ))
        
        self.stdout.write('-' * 80)
        self.stdout.write(self.style.SUCCESS(f'\n已重置 {reset_count} 个账户密码\n'))
        self.stdout.write('所有重置账户首次登录均需修改密码并完成安全问题确认。\n')

    def delete_inspectors(self):
        """删除名单中的看护员账户"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('确认删除名单中的看护员账户？')
        self.stdout.write('='*80 + '\n')
        
        # 确认删除
        confirm = input('请输入 yes 确认删除（输入其他值取消）: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('已取消删除操作\n'))
            return
        
        delete_count = 0
        
        self.stdout.write(f"{'状态':<6} | {'姓名':<15} | {'登录名':<13}\n")
        self.stdout.write('-' * 60)
        
        for name, phone in self.INSPECTORS_DATA:
            try:
                user = User.objects.get(username=phone)
                user.delete()
                delete_count += 1
                self.stdout.write(f'✓ 删除  | {name:<15} | {phone:<13}')
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'✗ 不存在 | {name:<15} | {phone:<13}'
                ))
        
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.SUCCESS(f'\n已删除 {delete_count} 个看护员账户\n'))
