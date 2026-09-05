from calendar import monthrange
from datetime import date, timedelta

from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import HeritageSite, InspectionRecord, LandUseProjectApproval, ProjectAudit, ReportRecord


PERIOD_LABELS = dict(ReportRecord.PERIOD_CHOICES)


def get_completed_period_bounds(period, reference_date=None):
    """Return the most recent completed calendar period before reference_date."""
    reference_date = reference_date or timezone.localdate()
    anchor = reference_date - timedelta(days=1)
    if period == ReportRecord.PERIOD_WEEKLY:
        end = anchor - timedelta(days=anchor.weekday() + 1)
        return end - timedelta(days=6), end
    if period == ReportRecord.PERIOD_MONTHLY:
        end = anchor.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == ReportRecord.PERIOD_QUARTERLY:
        quarter = (anchor.month - 1) // 3
        end = date(anchor.year, quarter * 3 + 1, 1) - timedelta(days=1)
        return date(end.year, end.month - 2, 1), end
    if period == ReportRecord.PERIOD_YEARLY:
        end = date(anchor.year, 1, 1) - timedelta(days=1)
        return date(end.year, 1, 1), end
    raise ValueError(f'不支持的报告周期：{period}')


def _build_daily_rows(period_start, period_end):
    total_map = {
        row['inspect_time__date']: row['count']
        for row in InspectionRecord.objects.filter(
            inspect_time__date__range=(period_start, period_end)
        ).values('inspect_time__date').annotate(count=Count('id'))
    }
    abnormal_map = {
        row['inspect_time__date']: row['count']
        for row in InspectionRecord.objects.filter(
            inspect_time__date__range=(period_start, period_end), is_normal=False
        ).values('inspect_time__date').annotate(count=Count('id'))
    }
    days = (period_end - period_start).days + 1
    # 长周期报告按月聚合，避免年报生成过大的明细表。
    if days > 62:
        rows = []
        cursor = period_start.replace(day=1)
        while cursor <= period_end:
            next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_end = min(period_end, next_month - timedelta(days=1))
            rows.append({
                'label': cursor.strftime('%Y-%m'),
                'total': sum(value for key, value in total_map.items() if cursor <= key <= month_end),
                'abnormal': sum(value for key, value in abnormal_map.items() if cursor <= key <= month_end),
            })
            cursor = next_month
        return rows
    return [
        {
            'label': (period_start + timedelta(days=offset)).strftime('%m-%d'),
            'total': total_map.get(period_start + timedelta(days=offset), 0),
            'abnormal': abnormal_map.get(period_start + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]


def build_report_context(period, period_start, period_end):
    inspection_qs = InspectionRecord.objects.filter(inspect_time__date__range=(period_start, period_end))
    abnormal_qs = inspection_qs.filter(is_normal=False)
    project_qs = LandUseProjectApproval.objects.filter(receive_date__range=(period_start, period_end))
    legacy_project_qs = ProjectAudit.objects.filter(received_date__date__range=(period_start, period_end))
    total_inspections = inspection_qs.count()
    abnormal_count = abnormal_qs.count()
    category_rows = list(
        HeritageSite.objects.values('category').annotate(count=Count('id')).order_by('-count')[:6]
    )
    category_labels = dict(HeritageSite.CATEGORY_CHOICES)
    category_rows = [
        {'label': category_labels.get(row['category'], row['category']), 'count': row['count']}
        for row in category_rows
    ]
    status_labels = dict(LandUseProjectApproval.STATUS_CHOICES)
    status_rows = [
        {'label': status_labels.get(status, status), 'count': project_qs.filter(status=status).count()}
        for status, _ in LandUseProjectApproval.STATUS_CHOICES
    ]
    return {
        'period': period,
        'period_label': PERIOD_LABELS[period],
        'period_start': period_start,
        'period_end': period_end,
        'generated_at': timezone.localtime(),
        'summary': {
            'heritage_total': HeritageSite.objects.count(),
            'inspection_total': total_inspections,
            'abnormal_total': abnormal_count,
            'inspection_rate': round(abnormal_count / total_inspections * 100, 1) if total_inspections else 0,
            'project_total': project_qs.count() + legacy_project_qs.count(),
            'project_archived': project_qs.filter(status=LandUseProjectApproval.STATUS_ARCHIVED).count(),
            'project_risk': project_qs.filter(is_overlap_artifact=True).count(),
        },
        'daily_rows': _build_daily_rows(period_start, period_end),
        'category_rows': category_rows,
        'status_rows': status_rows,
        'abnormal_items': list(
            abnormal_qs.select_related('site', 'inspector').order_by('-inspect_time')[:8].values(
                'site__name', 'issue_details', 'inspect_time', 'inspector__username'
            )
        ),
    }


def render_report_html(period, period_start, period_end):
    context = build_report_context(period, period_start, period_end)
    context['report_title'] = f"鄯善县文物保护工作{PERIOD_LABELS[period]}"
    html = render_to_string('reports/report_detail.html', context)
    return html, context


def create_report(period, generated_by=None, reference_date=None):
    period_start, period_end = get_completed_period_bounds(period, reference_date)
    html, context = render_report_html(period, period_start, period_end)
    report = ReportRecord.objects.create(
        period=period,
        period_start=period_start,
        period_end=period_end,
        title=context['report_title'],
        html_content=html,
        generated_by=generated_by,
    )
    return report
