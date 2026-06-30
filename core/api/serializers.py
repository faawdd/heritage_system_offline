from rest_framework import serializers

from core.models import LandUseProjectApproval


class LandProjectListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LandUseProjectApproval
        fields = [
            'id',
            'project_name',
            'company_name',
            'incoming_doc_date',
            'receive_date',
            'is_overlap_artifact',
            'status',
            'status_display',
            'created_at',
            'updated_at',
        ]


class LandProjectDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LandUseProjectApproval
        fields = [
            'id',
            'project_name',
            'company_name',
            'incoming_doc_date',
            'receive_date',
            'kml_file_path',
            'misc_zip_path',
            'is_overlap_artifact',
            'overlapped_relics_info',
            'status',
            'status_display',
            'field_check_date',
            'shanshan_request_num',
            'city_reply_num',
            'archaeology_request_num',
            'archaeology_report_path',
            'region_approval_num',
            'city_final_reply_num',
            'final_reply_to_company',
            'created_at',
            'updated_at',
        ]
