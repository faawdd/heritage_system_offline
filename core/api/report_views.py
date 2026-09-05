from django.http import HttpResponse
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ReportRecord
from core.services.report_service import create_report, get_completed_period_bounds, render_report_html


class ReportListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = ReportRecord.objects.values(
            'id', 'period', 'title', 'period_start', 'period_end', 'generated_at'
        )[:30]
        return Response({'success': True, 'data': list(rows)})


class ReportGenerateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        period = str(request.data.get('period', ReportRecord.PERIOD_MONTHLY))
        valid_periods = {key for key, _ in ReportRecord.PERIOD_CHOICES}
        if period not in valid_periods:
            return Response({'success': False, 'message': '报告周期不正确'}, status=400)
        report = create_report(period, generated_by=request.user)
        return Response({
            'success': True,
            'data': {
                'id': report.id,
                'period': report.period,
                'title': report.title,
                'period_start': report.period_start,
                'period_end': report.period_end,
            },
        })


class ReportDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, report_id):
        try:
            report = ReportRecord.objects.get(id=report_id)
        except ReportRecord.DoesNotExist:
            return Response({'success': False, 'message': '报告不存在'}, status=404)
        return Response({'success': True, 'data': {
            'id': report.id,
            'period': report.period,
            'title': report.title,
            'period_start': report.period_start,
            'period_end': report.period_end,
            'html_url': f'/api/v1/reports/{report.id}/html/',
            'generated_at': report.generated_at,
        }})


class ReportHTMLAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, report_id):
        try:
            report = ReportRecord.objects.get(id=report_id)
        except ReportRecord.DoesNotExist:
            return HttpResponse('报告不存在', status=404, content_type='text/plain; charset=utf-8')
        response = HttpResponse(report.html_content, content_type='text/html; charset=utf-8')
        if request.GET.get('download') == '1':
            response['Content-Disposition'] = f'attachment; filename="report-{report.period}-{report.period_end}.html"'
        return response


class ReportPreviewAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        period = request.GET.get('period', ReportRecord.PERIOD_MONTHLY)
        try:
            period_start, period_end = get_completed_period_bounds(period)
            html, _ = render_report_html(period, period_start, period_end)
        except ValueError:
            return HttpResponse('报告周期不正确', status=400, content_type='text/plain; charset=utf-8')
        return HttpResponse(html, content_type='text/html; charset=utf-8')
