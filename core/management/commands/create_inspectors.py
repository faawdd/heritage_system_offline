"""
管理命令：创建基层文物看护员账号
用法：python manage.py create_inspectors
     python manage.py create_inspectors --reset-passwords  (重置密码)
     python manage.py create_inspectors --delete  (删除所有账号)
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from core.models import InspectionRecord

class Command(BaseCommand):
    help = '创建18名基层文物看护员账号'

    # 看护员信息数据（姓名、手机号）
    INSPECTORS_DATA = [
        ('阿力木·艾尼', '13565713009'),
        ('吴蕊', '13999048119'),
        ('阿力木·牙库甫', '17794888003'),
        ('玉素甫·木合买提', '13999694846'),
        ('刘生', '13565588002'),
        ('佐日古丽·艾比布力', '13239957706'),
        ('亚库甫·司马义', '18999465525'),
        ('武娜', '15160841026'),
        ('吾甫尔·哈山', '15022877179'),
        ('艾孜海尔·阿布都热合曼', '18699531152'),
        ('玉素甫·依明', '18399483332'),
        ('白克力·艾海提', '13999471400'),
        ('依卖尔江·乌斯曼', '15309951715'),
        ('沙塔尔·热西提', '13109037072'),
        ('卡哈尔·努尤木', '13899311791'),
        ('买买提·沙塔尔', '13999698842'),
        ('赵强', '13899319788'),
        ('卞和好', '18196081222'),
    ]
    
    # 默认初始密码
    DEFAULT_PASSWORD = 'Heritage2026!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='删除已创建的看护员账号（用于重置）',
        )
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='重置所有看护员密码为初始密码',
        )

    def handle(self, *args, **options):
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
        
        if options['reset_passwords']:
            self.reset_passwords()
            return
        
        self.create_inspectors()

    def create_inspectors(self):
        """创建18名看护员账户"""
        created_count = 0
        updated_count = 0
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('开始创建基层文物看护员账号（使用手机号作为登录账户）')
        self.stdout.write('='*80 + '\n')
        
        # 获取用户组
        inspector_group = Group.objects.get(name='文物看护员')
        
        # 显示表头
        self.stdout.write(f"{'操作':<6} | {'姓名':<15} | {'手机号（账号）':<13} | {'初始密码':<20}")
        self.stdout.write('-' * 80)
        
        for name, phone in self.INSPECTORS_DATA:
            try:
                user, created = User.objects.get_or_create(
                    username=phone,  # 使用手机号作为username
                    defaults={
                        'email': phone,  # 邮箱也存储手机号
                        'first_name': name,
                        'last_name': '看护员',
                        'is_staff': True,  # 允许访问后台
                        'is_active': True,
                    }
                )
                
                # 设置统一的初始密码
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()
                
                # 将用户加入"文物看护员"组
                user.groups.add(inspector_group)
                
                if created:
                    created_count += 1
                    status = '✓ 新建'
                else:
                    updated_count += 1
                    status = '✓ 更新'
                
                self.stdout.write(
                    f'{status:<6} | {name:<15} | {phone:<13} | {self.DEFAULT_PASSWORD:<20}'
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
        
        self.stdout.write(self.style.WARNING('⚠️  初始密码信息：'))
        self.stdout.write(f"   所有账户默认密码: {self.DEFAULT_PASSWORD}\n")
        
        self.stdout.write('📝 首次登录建议事项：')
        self.stdout.write('  1. 使用手机号登录：')
        for name, phone in self.INSPECTORS_DATA[:3]:
            self.stdout.write(f'     {name} → 账号: {phone}')
        self.stdout.write(f'     ... 等其他 {len(self.INSPECTORS_DATA)-3} 人')
        self.stdout.write(f'\n  2. 密码: {self.DEFAULT_PASSWORD}')
        self.stdout.write('  3. 首次登录后系统会提示修改密码')
        self.stdout.write('  4. 修改为更复杂的密码（8位以上，包含大小写和数字）')
        self.stdout.write('  5. 登录后可在"日常办公 → 巡查记录"中添加巡查数据\n')

    def reset_passwords(self):
        """重置所有看护员密码"""
        reset_count = 0
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('重置所有看护员密码')
        self.stdout.write('='*80 + '\n')
        
        self.stdout.write(f"{'姓名':<15} | {'手机号':<13} | {'新密码':<20}")
        self.stdout.write('-' * 80)
        
        for name, phone in self.INSPECTORS_DATA:
            try:
                user = User.objects.get(username=phone)
                user.set_password(self.DEFAULT_PASSWORD)
                user.save()
                reset_count += 1
                
                self.stdout.write(
                    f'{name:<15} | {phone:<13} | {self.DEFAULT_PASSWORD:<20}'
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'{name:<15} | {phone:<13} | 账户不存在'
                ))
        
        self.stdout.write('-' * 80)
        self.stdout.write(self.style.SUCCESS(f'\n已重置 {reset_count} 个账户密码\n'))
        self.stdout.write(f'所有账户密码已重置为: {self.DEFAULT_PASSWORD}\n')

    def delete_inspectors(self):
        """删除所有看护员账户"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('确认删除所有看护员账户？')
        self.stdout.write('='*80 + '\n')
        
        # 确认删除
        confirm = input('请输入 yes 确认删除（输入其他值取消）: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('已取消删除操作\n'))
            return
        
        delete_count = 0
        
        self.stdout.write(f"{'状态':<6} | {'姓名':<15} | {'手机号':<13}\n")
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
