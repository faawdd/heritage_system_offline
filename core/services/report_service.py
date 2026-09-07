from datetime import date, timedelta

from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import HeritageSite, InspectionRecord, LandUseProjectApproval, ProjectAudit, ReportRecord


PERIOD_LABELS = dict(ReportRecord.PERIOD_CHOICES)

PERIOD_THEMES = {
    ReportRecord.PERIOD_WEEKLY: {
        'ink': '#244b55', 'muted': '#6b7f82', 'accent': '#3e8790',
        'gold': '#c99a52', 'paper': '#f6f8f5', 'line': '#d7e2df',
    },
    ReportRecord.PERIOD_MONTHLY: {
        'ink': '#18332f', 'muted': '#657774', 'accent': '#1b7168',
        'gold': '#c7933f', 'paper': '#f8f5ee', 'line': '#d9e0d9',
    },
    ReportRecord.PERIOD_QUARTERLY: {
        'ink': '#3f344f', 'muted': '#776e80', 'accent': '#7b5d91',
        'gold': '#b98658', 'paper': '#f8f4f0', 'line': '#e1d8df',
    },
    ReportRecord.PERIOD_YEARLY: {
        'ink': '#4a3024', 'muted': '#7e6b60', 'accent': '#a65e3b',
        'gold': '#bd8a3d', 'paper': '#faf5ea', 'line': '#e5d8c3',
    },
}

PERIOD_LITERATURE = {
    ReportRecord.PERIOD_WEEKLY: {
        'line': '慎终如始，则无败事。',
        'source': '《老子》',
        'focus': '本周以一线巡查、异常发现和即时处置为重点，重在见微知著、闭环管理。',
        'action': '建议对异常巡查逐项复核，做到发现一处、核实一处、整改一处。',
    },
    ReportRecord.PERIOD_MONTHLY: {
        'line': '凡益之道，与时偕行。',
        'source': '《周易》',
        'focus': '本月以工作量、问题分布和项目流转为观察主线，兼顾日常巡护与重点事项。',
        'action': '建议按月梳理重点文物点与待办项目，形成问题清单、责任清单和销号记录。',
    },
    ReportRecord.PERIOD_QUARTERLY: {
        'line': '观乎人文，以化成天下。',
        'source': '《周易·贲卦》',
        'focus': '本季度着眼于阶段性变化，关注保护对象、巡查质量与审批业务之间的联动。',
        'action': '建议结合季度趋势调整巡查力量，对反复出现的风险点制定专项保护措施。',
    },
    ReportRecord.PERIOD_YEARLY: {
        'line': '前人栽树，后人乘凉。',
        'source': '中国谚语',
        'focus': '本年度报告用于回望全年保护实践、盘点工作成效，并为下一年度资源配置提供依据。',
        'action': '建议将年度高频风险、重点项目和薄弱环节纳入下一年度保护计划，持续传承、久久为功。',
    },
}


def get_completed_period_bounds(period, reference_date=None):
    """Return the most recent completed calendar period before reference_date."""
    reference_date = reference_date or timezone.localdate()
    if period == ReportRecord.PERIOD_WEEKLY:
        end = reference_date - timedelta(days=reference_date.weekday() + 1)
        return end - timedelta(days=6), end
    if period == ReportRecord.PERIOD_MONTHLY:
        end = reference_date.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == ReportRecord.PERIOD_QUARTERLY:
        quarter = (reference_date.month - 1) // 3
        end = date(reference_date.year, quarter * 3 + 1, 1) - timedelta(days=1)
        return date(end.year, end.month - 2, 1), end
    if period == ReportRecord.PERIOD_YEARLY:
        end = date(reference_date.year, 1, 1) - timedelta(days=1)
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
        'literature': PERIOD_LITERATURE[period],
        'theme': PERIOD_THEMES[period],
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
    report, _ = ReportRecord.objects.update_or_create(
        period=period,
        period_start=period_start,
        period_end=period_end,
        defaults={
            'title': context['report_title'],
            'html_content': html,
            'generated_by': generated_by,
        },
    )
    return report
