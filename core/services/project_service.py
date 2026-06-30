from django.db.models import Q

from core.models import LandUseProjectApproval


def list_land_projects(*, status=None, keyword=None):
    queryset = LandUseProjectApproval.objects.all().order_by('-receive_date', '-created_at')

    if status:
        queryset = queryset.filter(status=status)

    if keyword:
        queryset = queryset.filter(
            Q(project_name__icontains=keyword) | Q(company_name__icontains=keyword)
        )

    return queryset
