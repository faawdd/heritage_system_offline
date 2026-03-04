"""
管理命令：检查和处理坎儿井数据
用法：python manage.py check_kanerjing --auto-tag
"""
from django.core.management.base import BaseCommand
from core.models import HeritageSite

class Command(BaseCommand):
    help = '检查数据库中的坎儿井数据，名称包含"坎儿井"的会被识别'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-tag',
            action='store_true',
            help='为坎儿井添加特殊的"坎儿井"标签到备注字段',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='生成坎儿井数据报告',
        )

    def handle(self, *args, **options):
        # 查找所有名称包含"坎儿井"的文物
        kanerjing_sites = HeritageSite.objects.filter(name__contains='坎儿井')
        count = kanerjing_sites.count()
        
        self.stdout.write(self.style.SUCCESS(f'\n找到 {count} 处坎儿井'))
        self.stdout.write('=' * 60)
        
        # 生成报告
        if options['report'] or True:  # 默认显示报告
            self.stdout.write('\n坎儿井清单：')
            for i, site in enumerate(kanerjing_sites, 1):
                self.stdout.write(f'{i}. {site.sip_code} - {site.name}')
                self.stdout.write(f'   地址：{site.address}')
                self.stdout.write(f'   等级：{site.get_level_display()}')
                self.stdout.write(f'   分类：{site.get_category_display()}')
                self.stdout.write('')
        
        # 等级统计
        self.stdout.write('\n等级分布统计：')
        for level_code, level_name in HeritageSite.LEVEL_CHOICES:
            count = kanerjing_sites.filter(level=level_code).count()
            if count > 0:
                self.stdout.write(f'  {level_name}: {count} 处')
        
        # 分类统计
        self.stdout.write('\n分类分布统计：')
        category_stats = kanerjing_sites.values('category').annotate(
            django_db_models_functions_count='count'
        ).annotate(count=models.Count('id'))
        
        from django.db.models import Count
        category_stats = kanerjing_sites.values('category').annotate(count=Count('id'))
        for stat in category_stats:
            cat_code = stat['category']
            cat_name = dict(HeritageSite.CATEGORY_CHOICES).get(cat_code, cat_code)
            self.stdout.write(f'  {cat_name}: {stat["count"]} 处')
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('检查完成！'))
