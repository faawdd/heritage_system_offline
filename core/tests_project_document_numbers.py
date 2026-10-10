from datetime import date

from django.test import TestCase

from core.models import LandUseProjectApproval, LandUseProjectDocument
from core.land_project_services import apply_workflow_action


class ProjectDocumentNumberTests(TestCase):
    def make_project(self):
        project = LandUseProjectApproval.objects.create(
            project_name='通用文号测试', company_name='测试单位', receive_date=date.today(),
            status=LandUseProjectApproval.STATUS_FIELD_DONE,
        )
        LandUseProjectDocument.objects.create(
            project=project, category=LandUseProjectDocument.CATEGORY_COUNTY_REQUEST,
            file_path='documents/request.pdf',
        )
        return project

    def test_county_document_numbers_accept_local_conventions(self):
        for number in ('某县文旅〔2026〕12号', '文物函[2026]A-15', '2026/审批/008'):
            with self.subTest(number=number):
                project = self.make_project()
                apply_workflow_action(project, 'submit_city_request', {'shanshan_request_num': number})
                project.refresh_from_db()
                self.assertEqual(project.shanshan_request_num, number)
                self.assertEqual(project.status, LandUseProjectApproval.STATUS_CITY_REVIEWING)
                field = project._meta.get_field('shanshan_request_num')
                self.assertEqual(field.clean(number, project), number)

    def test_empty_number_still_requires_input(self):
        with self.assertRaisesMessage(ValueError, '县局请示文号不能为空'):
            apply_workflow_action(self.make_project(), 'submit_city_request', {'shanshan_request_num': '  '})

    def test_overlong_number_is_a_validation_error(self):
        with self.assertRaisesMessage(ValueError, '不能超过100个字符'):
            apply_workflow_action(self.make_project(), 'submit_city_request', {'shanshan_request_num': 'X' * 101})
