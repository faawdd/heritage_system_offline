"""进程内报告调度器，避免部署时必须额外维护 cron。"""

import logging
import os
import sys
import threading
import time

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from core.models import ReportRecord, ReportSchedule
from core.services.report_service import create_report, get_completed_period_bounds

logger = logging.getLogger(__name__)
_scheduler_started = False


def _enabled_periods():
    schedules = list(ReportSchedule.objects.filter(enabled=True).values_list('period', flat=True))
    if schedules:
        return schedules
    return [period for period, _ in ReportRecord.PERIOD_CHOICES]


def generate_due_reports():
    """为每个已完成且尚未归档的周期生成一份报告。"""
    close_old_connections()
    generated = []
    try:
        for period in _enabled_periods():
            period_start, period_end = get_completed_period_bounds(period)
            if ReportRecord.objects.filter(
                period=period, period_start=period_start, period_end=period_end
            ).exists():
                continue
            report = create_report(period)
            ReportSchedule.objects.filter(period=period).update(last_generated_at=timezone.now())
            generated.append(report)
    except Exception:
        logger.exception('内置报告调度器生成报告失败')
    finally:
        close_old_connections()
    return generated


def _scheduler_loop():
    interval = max(int(getattr(settings, 'REPORT_AUTO_GENERATOR_INTERVAL', 3600)), 60)
    # 等待 Django 完成应用初始化，再访问数据库。
    time.sleep(2)
    while True:
        generate_due_reports()
        time.sleep(interval)


def start_report_scheduler():
    global _scheduler_started
    if _scheduler_started or not getattr(settings, 'REPORT_AUTO_GENERATOR_ENABLED', True):
        return
    if any(command in sys.argv for command in ('migrate', 'makemigrations', 'test', 'shell')):
        return
    # runserver 父进程只负责拉起子进程，避免重复启动一个调度线程。
    if os.environ.get('RUN_MAIN') == 'false':
        return
    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, name='report-scheduler', daemon=True)
    thread.start()
    logger.info('内置报告调度器已启动，检查间隔 %s 秒', getattr(settings, 'REPORT_AUTO_GENERATOR_INTERVAL', 3600))