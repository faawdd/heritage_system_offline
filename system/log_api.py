import json

from django.contrib.admin.models import LogEntry
from django.db.models import Q
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import LandUseProjectApproval, LandUseProjectOperationLog, UserManagementAudit
from system.admin_access import has_system_permission, log_scope
from system.admin_labels import action_name, model_name, module_name
from system.models import LoginLog, OperationLog


LOG_SOURCES = {
    'login': (LoginLog, 'user', 'system.view_loginlog', '登录日志'),
    'operation': (OperationLog, 'operator', 'system.view_operationlog', '系统操作日志'),
    'django': (LogEntry, 'user', 'admin.view_logentry', 'Django后台操作日志'),
    'user': (UserManagementAudit, 'operator', 'core.view_usermanagementaudit', '用户管理审计'),
    'project': (LandUseProjectOperationLog, 'operator', 'core.view_landuseprojectoperationlog', '用地项目流程日志'),
}


class LogQuerySerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=list(LOG_SOURCES), default='login')
    keyword = serializers.CharField(required=False, allow_blank=True, max_length=200)
    success = serializers.ChoiceField(choices=['', 'true', 'false', '1', '0', 'yes', 'no'], default='')
    module = serializers.CharField(required=False, allow_blank=True, max_length=100)
    action = serializers.CharField(required=False, allow_blank=True, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if attrs.get('start') and attrs.get('end') and attrs['start'] > attrs['end']:
            raise serializers.ValidationError('开始时间不能晚于结束时间')
        return attrs


class LogViewPermission(BasePermission):
    message = '没有查看该类日志的权限'

    def has_permission(self, request, view):
        source = view.source or request.query_params.get('source', 'login')
        # Invalid sources are rejected by the query serializer, not interpreted as another source.
        if source not in LOG_SOURCES:
            return request.user.is_authenticated
        return has_system_permission(request.user, LOG_SOURCES[source][2])


def django_detail(entry):
    if not entry.change_message.startswith('['):
        return entry.change_message
    changes = json.loads(entry.change_message)
    labels = []
    model = entry.content_type.model_class() if entry.content_type else None
    for change in changes:
        if 'added' in change:
            labels.append('新增记录')
        if 'deleted' in change:
            labels.append('删除关联记录')
        if 'changed' in change:
            fields = change['changed'].get('fields', [])
            translated = []
            for field in fields:
                matched = next((str(item.verbose_name) for item in model._meta.fields
                                if field in {item.name, str(item.verbose_name)}) , field) if model else field
                translated.append(matched)
            labels.append('修改字段：' + '、'.join(translated))
    return '；'.join(labels)


def serialize_log(source, entry):
    timestamp = entry.action_time if source == 'django' else entry.created_at
    actor = getattr(entry, LOG_SOURCES[source][1])
    row = {
        'id': entry.pk, 'source': source, 'source_name': LOG_SOURCES[source][3],
        'operator_name': actor.username if actor else '已删除用户或匿名请求',
        'created_at': timestamp, 'success': True, 'ip': '', 'request_path': '', 'detail': '',
    }
    if source == 'login':
        row.update(username=entry.username, operator_name=entry.username, success=entry.success,
                   ip=entry.ip, user_agent=entry.user_agent, message=entry.message,
                   module='账户登录', action='登录', detail=entry.message)
    elif source == 'operation':
        row.update(module=module_name(entry.module), action=action_name(entry.action),
                   module_code=entry.module, action_code=entry.action, success=entry.success,
                   ip=entry.ip, request_path=entry.request_path, method=entry.method, detail=entry.detail)
    elif source == 'django':
        content_type = entry.content_type
        row.update(
            module=model_name(content_type.app_label, content_type.model) if content_type else '已删除系统模型',
            action={1: '新增', 2: '修改', 3: '删除'}.get(entry.action_flag, '后台操作'),
            detail=django_detail(entry), target=entry.object_repr, object_id=entry.object_id,
        )
    elif source == 'user':
        row.update(module='用户与用户组管理', action=entry.get_action_display(),
                   detail=entry.details, target=str(entry.target_user or entry.target_group or '已删除对象'))
    else:
        statuses = dict(LandUseProjectApproval.STATUS_CHOICES)
        row.update(module='用地项目管理', action=entry.action_label or action_name(entry.action),
                   detail=f'{statuses.get(entry.status_before, entry.status_before)} → {statuses.get(entry.status_after, entry.status_after)}',
                   target=entry.project.project_name)
    return row


class AuditLogListAPIView(APIView):
    permission_classes = [LogViewPermission]
    source = None

    def get(self, request):
        raw = request.query_params.copy()
        if self.source:
            raw['source'] = self.source
        serializer = LogQuerySerializer(data=raw)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data
        source = query['source']
        model, actor, _permission, _label = LOG_SOURCES[source]
        date_field = 'action_time' if source == 'django' else 'created_at'
        queryset = model.objects.select_related(actor).all()
        users, scope_label = log_scope(request.user)
        if users is not None:
            scope = Q(**{f'{actor}__in': users})
            if source == 'login':
                scope |= Q(user__isnull=True, username__in=users.values('username'))
            queryset = queryset.filter(scope)
        keyword = query.get('keyword', '')
        if keyword:
            fields = {
                'login': ['username', 'ip', 'message'],
                'operation': ['operator__username', 'module', 'action', 'detail', 'request_path'],
                'django': ['user__username', 'object_repr', 'change_message'],
                'user': ['operator__username', 'details', 'target_user__username', 'target_group__name'],
                'project': ['operator__username', 'action_label', 'project__project_name'],
            }[source]
            search = Q()
            for field in fields:
                search |= Q(**{f'{field}__icontains': keyword})
            if source == 'operation':
                from system.admin_labels import ACTION_NAMES, MODULE_NAMES
                search |= Q(action__in=[key for key, label in ACTION_NAMES.items() if keyword in label])
                search |= Q(module__in=[key for key, label in MODULE_NAMES.items() if keyword in label])
            queryset = queryset.filter(search)
        if query['success']:
            success = query['success'] in {'true', '1', 'yes'}
            queryset = queryset.filter(success=success) if source in {'login', 'operation'} else (
                queryset if success else queryset.none()
            )
        for field in ['module', 'action']:
            if query.get(field) and source == 'operation':
                queryset = queryset.filter(**{f'{field}__icontains': query[field]})
        if 'start' in query:
            queryset = queryset.filter(**{f'{date_field}__gte': query['start']})
        if 'end' in query:
            queryset = queryset.filter(**{f'{date_field}__lte': query['end']})
        total = queryset.count()
        offset = (query['page'] - 1) * query['page_size']
        queryset = queryset.order_by(f'-{date_field}', '-pk')
        if source == 'django':
            queryset = queryset.select_related('content_type')
        elif source == 'project':
            queryset = queryset.select_related('project')
        elif source == 'user':
            queryset = queryset.select_related('target_user', 'target_group')
        return Response({
            'success': True, 'rows': [serialize_log(source, entry) for entry in queryset[offset:offset + query['page_size']]],
            'pagination': {'page': query['page'], 'page_size': query['page_size'], 'total': total},
            'scope': scope_label,
            'sources': [{'value': key, 'label': value[3]} for key, value in LOG_SOURCES.items()
                        if has_system_permission(request.user, value[2])],
        })


class LoginLogListAPIView(AuditLogListAPIView):
    source = 'login'


class OperationLogListAPIView(AuditLogListAPIView):
    source = 'operation'
