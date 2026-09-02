"""
管理命令：导入四普系统"文物矢量图"边界坐标，替换KML叠加检查使用的单点坐标。

数据来源：通过内置浏览器登录四普系统后，按本地文物名称逐条调用
    POST /immovableListController.do?queryRelicList  （按名称查找 culRid）
    POST /api/mapdata/list  (id=<culRid>&table=5&)    （取本体范围/保护范围/建控地带矢量）
抓取结果导出为 NDJSON，每行一个 JSON 对象：
    {"id": <HeritageSite.id>, "culrid": "...", "matchedName": "...",
     "body": [[[lon,lat],...],...], "protection": [...], "control": [...]}
    或 {"id": ..., "unmatched": true, ...} / {"id": ..., "noGeometry": true, ...}

用法：
    python manage.py import_sipu_boundary /path/to/heritage_body_boundary_clean.ndjson
    python manage.py import_sipu_boundary /path/to/xxx.ndjson --dry-run
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import HeritageSite


class Command(BaseCommand):
    help = '导入四普系统文物矢量图（本体范围/保护范围/建控地带）到 HeritageSite'

    def add_arguments(self, parser):
        parser.add_argument('ndjson_path', help='抓取结果 NDJSON 文件路径')
        parser.add_argument('--dry-run', action='store_true', help='仅打印统计，不写入数据库')

    def handle(self, *args, **options):
        path = options['ndjson_path']
        dry_run = options['dry_run']

        try:
            records = self._load_records(path)
        except OSError as exc:
            raise CommandError(f'无法读取文件：{exc}')

        updated = 0
        unmatched = []
        no_geometry = []
        missing_local = []

        with transaction.atomic():
            for record in records:
                site_id = record.get('id')
                site = HeritageSite.objects.filter(id=site_id).first()
                if not site:
                    missing_local.append(site_id)
                    continue

                if record.get('unmatched'):
                    unmatched.append({'id': site_id, 'name': site.name, 'candidates': record.get('candidateNames') or []})
                    continue

                body_rings = record.get('body') or []
                protection_rings = record.get('protection') or []
                control_rings = record.get('control') or []

                if not (body_rings or protection_rings or control_rings):
                    no_geometry.append({'id': site_id, 'name': site.name})
                    continue

                update_fields = []
                if body_rings:
                    site.body_boundary = json.dumps(body_rings, ensure_ascii=False)
                    update_fields.append('body_boundary')
                if protection_rings:
                    site.protection_zone = json.dumps(protection_rings, ensure_ascii=False)
                    update_fields.append('protection_zone')
                if control_rings:
                    site.control_zone = json.dumps(control_rings, ensure_ascii=False)
                    update_fields.append('control_zone')

                if update_fields:
                    site.save(update_fields=update_fields)
                    updated += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry_run else ""}已{"预演" if dry_run else "更新"} {updated} 条文物点的边界坐标'
        ))
        if missing_local:
            self.stdout.write(self.style.WARNING(f'本地未找到的记录ID（{len(missing_local)}）：{missing_local}'))
        if unmatched:
            self.stdout.write(self.style.WARNING(f'四普系统未匹配到的文物点（{len(unmatched)}）：'))
            for item in unmatched:
                self.stdout.write(f"  - [{item['id']}] {item['name']}  候选：{item['candidates']}")
        if no_geometry:
            self.stdout.write(self.style.WARNING(f'匹配成功但四普未登记矢量图的文物点（{len(no_geometry)}）：'))
            for item in no_geometry:
                self.stdout.write(f"  - [{item['id']}] {item['name']}")

    @staticmethod
    def _load_records(path):
        records = []
        with open(path, encoding='utf-8') as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
