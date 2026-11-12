from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from aeraspace import hr, hr_rules
from aeraspace.api import attendance
from aeraspace.api import hr_requests as requests_api
from aeraspace.tests.test_chat import make_user

USER = "rules-user@example.com"


def at(day, hhmm):
	hours, minutes = map(int, hhmm.split(":"))
	return datetime.combine(getdate(day), datetime.min.time()) + timedelta(hours=hours, minutes=minutes)


@contextmanager
def clock(when):
	with patch("aeraspace.api.attendance.now_datetime", return_value=when):
		yield


def weekdays_back(count, start_weeks=6):
	"""`count` Monday-Friday dates in one month, a few weeks back."""
	day = getdate(add_days(today(), -7 * start_weeks)).replace(day=1)
	days = []
	while len(days) < count:
		if day.weekday() < 5:
			days.append(day)
		day = add_days(day, 1)
	return days


class TestHrRules(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(USER)
		hr.ensure_hr_setup()
		cls.employee = hr.employee_for(USER)
		frappe.db.set_value("Employee", cls.employee, "date_of_joining", add_days(today(), -400))

	def setUp(self):
		for doctype in ("Employee Checkin", "Attendance", "Leave Application"):
			frappe.db.delete(doctype, {"employee": self.employee})

	def step(self, action, when):
		with self.set_user(USER), clock(when):
			return getattr(attendance, action)()

	def test_saturday_and_sunday_are_weekly_offs(self):
		saturday = add_days(today(), 5 - getdate(today()).weekday() - 7)
		with self.set_user(USER):
			days = attendance.get_history(str(saturday), str(add_days(saturday, 1)))["days"]
		self.assertEqual([d["status"] for d in days], ["Weekly Off", "Weekly Off"])

	def test_every_third_late_day_is_a_half_day(self):
		days = weekdays_back(4)
		for day in days[:3]:
			self.step("check_in", at(day, "09:40"))
			self.step("check_out", at(day, "18:30"))
		self.step("check_in", at(days[3], "09:00"))  # on time
		self.step("check_out", at(days[3], "18:00"))

		hr_rules.apply_late_penalties(self.employee, until=days[3])
		hr_rules.apply_late_penalties(self.employee, until=days[3])  # runs daily; only once per day
		penalties = frappe.get_all(
			"Attendance",
			filters={"employee": self.employee, "as_late_penalty": 1, "docstatus": 1},
			fields=["attendance_date", "status"],
		)
		self.assertEqual([(p.attendance_date, p.status) for p in penalties], [(days[2], "Half Day")])
		with self.set_user(USER):
			history = {d["date"]: d for d in attendance.get_history(str(days[0]), str(days[3]))["days"]}
		self.assertEqual(history[str(days[2])]["status"], "Half Day")
		self.assertTrue(history[str(days[2])]["late_penalty"])
		self.assertEqual(history[str(days[0])]["status"], "Present")

	def test_forgotten_check_out_closes_at_shift_end(self):
		day = weekdays_back(1, start_weeks=1)[0]
		self.step("check_in", at(day, "09:00"))
		state = self.step("check_in", at(add_days(day, 1), "09:05"))  # next morning
		self.assertEqual(state["state"], "working")
		auto = frappe.get_all(
			"Employee Checkin",
			filters={"employee": self.employee, "as_source": "Auto"},
			fields=["log_type", "time"],
		)
		self.assertEqual([(a.log_type, a.time) for a in auto], [("OUT", at(day, "18:00"))])
		summary = attendance.summarize(self.employee, day)
		self.assertEqual(summary["worked_seconds"], 9 * 3600)
		self.assertTrue(summary["auto_checkout"])
		self.assertEqual(state["missed_checkout"], str(day))

	def test_overtime_beyond_nine_hours(self):
		day = weekdays_back(1, start_weeks=2)[0]
		self.step("check_in", at(day, "09:00"))
		self.step("check_out", at(day, "19:30"))
		self.assertEqual(attendance.summarize(self.employee, day)["overtime_seconds"], 90 * 60)

	def test_leave_notice_and_balance(self):
		with self.set_user(USER):
			self.assertRaisesRegex(
				frappe.ValidationError,
				"notice",
				requests_api.apply,
				"leave",
				today(),
				today(),
				"Errand",
				"Casual Leave",
			)
			balance = int(requests_api.get_options()["balances"]["Sick Leave"])
			self.assertGreater(balance, 0)
			monday = add_days(today(), 7 - getdate(today()).weekday())
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Leave Without Pay",
				requests_api.apply,
				"leave",
				str(monday),
				str(add_days(monday, 13)),  # 10 working days, more than the balance
				"Surgery",
				"Sick Leave",
			)
			# Friday to Monday: the weekend isn't counted
			friday = add_days(monday, 4)
			ok = requests_api.apply("leave", str(friday), str(add_days(friday, 3)), "Fever", "Sick Leave")
		self.assertEqual(ok["days"], 2)
