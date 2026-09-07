from datetime import date, datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import ReportRecord, ReportSchedule
from core.report_scheduler import _is_due, _schedules
from core.services.report_service import get_completed_period_bounds


class ReportSchedulerTimingTests(SimpleTestCase):
    def test_weekly_report_is_not_due_before_configured_hour(self):
        reference = timezone.make_aware(datetime(2026, 8, 10, 7, 59))

        self.assertFalse(_is_due(ReportRecord.PERIOD_WEEKLY, 8, reference))

    def test_weekly_report_is_due_at_configured_hour(self):
        reference = timezone.make_aware(datetime(2026, 8, 10, 8, 0))

        self.assertTrue(_is_due(ReportRecord.PERIOD_WEEKLY, 8, reference))

    def test_missed_schedule_is_due_later_the_same_day(self):
        reference = timezone.make_aware(datetime(2026, 8, 10, 18, 0))

        self.assertTrue(_is_due(ReportRecord.PERIOD_WEEKLY, 8, reference))

    def test_monthly_period_completes_on_the_first_day_of_next_month(self):
        self.assertEqual(
            get_completed_period_bounds(ReportRecord.PERIOD_MONTHLY, date(2026, 9, 1)),
            (date(2026, 8, 1), date(2026, 8, 31)),
        )

    def test_quarterly_and_yearly_periods_complete_on_boundary_day(self):
        self.assertEqual(
            get_completed_period_bounds(ReportRecord.PERIOD_QUARTERLY, date(2026, 7, 1)),
            (date(2026, 4, 1), date(2026, 6, 30)),
        )
        self.assertEqual(
            get_completed_period_bounds(ReportRecord.PERIOD_YEARLY, date(2026, 1, 1)),
            (date(2025, 1, 1), date(2025, 12, 31)),
        )


class ReportScheduleSelectionTests(TestCase):
    def test_all_disabled_schedules_do_not_fall_back_to_defaults(self):
        ReportSchedule.objects.create(period=ReportRecord.PERIOD_WEEKLY, enabled=False)

        self.assertEqual(_schedules(), [])