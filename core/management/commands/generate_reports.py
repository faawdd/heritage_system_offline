from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import ReportRecord, ReportSchedule
from core.services.report_service import create_report


class Command(BaseCommand):
    help = '生成周报、月报、季度报或年报；可由 cron/systemd timer 周期调用。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period', choices=[key for key, _ in ReportRecord.PERIOD_CHOICES],
            help='只生成指定周期；不传则按启用的报告计划生成',
        )
        parser.add_argument('--force', action='store_true', help='忽略本次是否已生成的判断')

    def handle(self, *args, **options):
        target_period = options.get('period')
        periods = [target_period] if target_period else list(
            ReportSchedule.objects.filter(enabled=True).values_list('period', flat=True)
        )
        if not periods:
            periods = [key for key, _ in ReportRecord.PERIOD_CHOICES]

        created = 0
        today = timezone.localdate()
        for period in periods:
            if not options['force'] and ReportRecord.objects.filter(
                period=period, period_end__lt=today
            ).filter(generated_at__date=today).exists():
                self.stdout.write(f'跳过 {period}：今天已生成')
                continue
            report = create_report(period)
            ReportSchedule.objects.filter(period=period).update(last_generated_at=timezone.now())
            created += 1
            self.stdout.write(self.style.SUCCESS(f'已生成 {report.title}（{report.period_start} 至 {report.period_end}）'))
        self.stdout.write(f'本次生成 {created} 份报告')
