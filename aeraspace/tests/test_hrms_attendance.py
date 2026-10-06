from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from aeraspace import hr
from aeraspace.api import admin_users, attendance
from aeraspace.api.directory import update_my_profile
from aeraspace.tests.test_chat import make_user

MANAGER = "hr-manager@example.com"
MEMBER = "hr-member@example.com"
OUTSIDER = "hr-outsider@example.com"
CLOCK = "hr-clock@example.com"


def at(day, hhmm):
	hours, minutes = map(int, hhmm.split(":"))
	return datetime.combine(getdate(day), datetime.min.time()) + timedelta(hours=hours, minutes=minutes)


@contextmanager
def clock(when):
	with patch("aeraspace.api.attendance.now_datetime", return_value=when):
		yield


class TestHrmsFoundation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(MANAGER)
		make_user(MEMBER)

	def test_default_shift_and_holiday_list(self):
		hr.ensure_hr_setup()
		shift = frappe.get_doc("Shift Type", hr.DEFAULT_SHIFT)
		self.assertEqual(str(shift.start_time), "9:00:00")
		self.assertEqual(shift.working_hours_calculation_based_on, "Every Valid Check-in and Check-out")
		self.assertTrue(shift.enable_auto_attendance)
		holiday_list = frappe.db.get_value("Company", hr.default_company(), "default_holiday_list")
		self.assertEqual(shift.holiday_list, holiday_list)
		self.assertTrue(frappe.db.count("Holiday", {"parent": holiday_list, "weekly_off": 1}))

	def test_new_member_gets_employee(self):
		employee = frappe.get_doc("Employee", hr.employee_for(MEMBER))
		self.assertEqual(employee.company, hr.default_company())
		self.assertEqual(employee.default_shift, hr.DEFAULT_SHIFT)
		self.assertTrue(frappe.db.exists("Has Role", {"parent": MEMBER, "role": hr.EMPLOYEE_ROLE}))

	def test_non_members_are_left_alone(self):
		if not frappe.db.exists("User", OUTSIDER):
			frappe.get_doc(
				{"doctype": "User", "email": OUTSIDER, "first_name": "Out", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		self.assertIsNone(hr.ensure_employee(OUTSIDER))
		self.assertFalse(frappe.db.exists("Employee", {"user_id": OUTSIDER}))

	def test_profile_details_flow_to_employee(self):
		with self.set_user(MEMBER):
			update_my_profile(designation="QA Engineer", department="Quality", manager=MANAGER)
		employee = frappe.get_doc("Employee", hr.employee_for(MEMBER))
		self.assertEqual(employee.designation, "QA Engineer")
		self.assertEqual(frappe.db.get_value("Department", employee.department, "department_name"), "Quality")
		self.assertEqual(employee.reports_to, hr.employee_for(MANAGER))

	def test_admin_created_user_gets_employee(self):
		email = "hr-new@example.com"
		admin_users.create_user("Nila", email, designation="Designer")
		self.assertEqual(frappe.db.get_value("Employee", {"user_id": email}, "designation"), "Designer")

	def test_link_all_users_is_idempotent(self):
		hr.link_all_users()
		count = frappe.db.count("Employee")
		self.assertEqual(hr.link_all_users(), [])
		self.assertEqual(frappe.db.count("Employee"), count)


class TestAttendance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(CLOCK)
		cls.employee = hr.employee_for(CLOCK)
		# joined a while ago, so HRMS may mark attendance for past days
		frappe.db.set_value("Employee", cls.employee, "date_of_joining", add_days(today(), -60))

	def setUp(self):
		frappe.db.delete("Attendance", {"employee": self.employee})
		frappe.db.delete("Employee Checkin", {"employee": self.employee})

	def step(self, action, hhmm, day=None):
		with self.set_user(CLOCK), clock(at(day or today(), hhmm)):
			return getattr(attendance, action)()

	def events(self):
		return frappe.get_all(
			"Employee Checkin",
			filters={"employee": self.employee},
			fields=["log_type", "as_reason", "as_source", "shift"],
			order_by="time asc",
		)

	def test_full_day_creates_checkins(self):
		self.assertEqual(self.step("get_state", "08:55")["state"], "out")
		self.assertEqual(self.step("check_in", "09:00")["state"], "working")
		self.assertEqual(self.step("start_break", "13:00")["state"], "break")
		self.assertEqual(self.step("end_break", "13:45")["state"], "working")
		state = self.step("check_out", "18:00")
		self.assertEqual(state["state"], "out")
		self.assertEqual(
			[(e.log_type, e.as_reason) for e in self.events()],
			[("IN", "Work"), ("OUT", "Break"), ("IN", "Break"), ("OUT", "Work")],
		)
		self.assertTrue(all(e.as_source == "Web" and e.shift == hr.DEFAULT_SHIFT for e in self.events()))

		summary = state["today"]
		self.assertEqual(summary["worked_seconds"], (4 * 60 + 4 * 60 + 15) * 60)
		self.assertEqual(summary["break_seconds"], 45 * 60)
		self.assertEqual(summary["late_seconds"], 0)
		self.assertEqual(summary["first_in"], str(at(today(), "09:00")))
		self.assertEqual(summary["last_out"], str(at(today(), "18:00")))

	def test_repeated_clicks_are_ignored(self):
		self.step("check_in", "09:00")
		self.step("check_in", "09:00")
		self.step("start_break", "11:00")
		self.step("start_break", "11:00")
		self.assertEqual(len(self.events()), 2)

	def test_invalid_steps_are_rejected(self):
		self.assertRaises(frappe.ValidationError, self.step, "start_break", "09:00")
		self.assertRaises(frappe.ValidationError, self.step, "end_break", "09:00")
		self.assertRaises(frappe.ValidationError, self.step, "check_out", "09:00")
		self.step("check_in", "09:00")
		self.step("start_break", "11:00")
		self.assertRaises(frappe.ValidationError, self.step, "check_in", "11:10")
		self.assertEqual(self.step("check_out", "11:20")["state"], "out")  # can leave from a break

	def test_late_only_beyond_grace(self):
		self.step("check_in", "09:10")
		self.assertEqual(self.step("get_state", "09:20")["today"]["late_seconds"], 0)
		frappe.db.delete("Employee Checkin", {"employee": self.employee})
		self.step("check_in", "09:30")
		self.assertEqual(self.step("get_state", "09:40")["today"]["late_seconds"], 30 * 60)
		frappe.db.delete("Employee Checkin", {"employee": self.employee})
		self.step("check_in", "20:00")  # after the shift: not late
		self.assertEqual(self.step("get_state", "20:10")["today"]["late_seconds"], 0)

	def test_running_time_is_left_to_the_browser(self):
		self.step("check_in", "09:00")
		state = self.step("get_state", "10:00")
		self.assertEqual(state["since"], str(at(today(), "09:00")))
		self.assertEqual(state["today"]["worked_seconds"], 0)

	def test_open_session_from_yesterday_does_not_carry_over(self):
		yesterday = add_days(today(), -1)
		self.step("check_in", "09:00", day=yesterday)
		state = self.step("get_state", "09:00")
		self.assertEqual(state["state"], "out")
		self.assertEqual(state["missed_checkout"], str(getdate(yesterday)))
		self.assertEqual(self.step("check_in", "09:05")["state"], "working")

	def test_checkins_are_insert_only(self):
		self.step("check_in", "09:00")
		name = frappe.get_all("Employee Checkin", {"employee": self.employee}, pluck="name")[0]
		with self.set_user(CLOCK):
			doc = frappe.get_doc("Employee Checkin", name)
			doc.time = at(today(), "08:00")
			self.assertRaises(frappe.PermissionError, doc.save, ignore_permissions=True)
			self.assertRaises(
				frappe.PermissionError,
				frappe.delete_doc,
				"Employee Checkin",
				name,
				ignore_permissions=True,
			)
		self.assertTrue(frappe.db.exists("Employee Checkin", name))

	def test_records_request_details(self):
		with patch.object(frappe.local, "request_ip", "10.1.2.3", create=True):
			self.step("check_in", "09:00")
		self.assertEqual(
			frappe.db.get_value("Employee Checkin", {"employee": self.employee}, "as_ip_address"), "10.1.2.3"
		)

	def test_hrms_marks_attendance_from_our_checkins(self):
		day = getdate(add_days(today(), -1))
		while day.weekday() == 6:  # Sunday is the weekly off
			day = add_days(day, -1)
		self.step("check_in", "09:00", day=day)
		self.step("start_break", "13:00", day=day)
		self.step("end_break", "14:00", day=day)
		self.step("check_out", "18:00", day=day)

		shift = frappe.get_doc("Shift Type", hr.DEFAULT_SHIFT)
		shift.process_attendance_after = add_days(day, -1)
		shift.last_sync_of_checkin = at(day, "23:00")
		shift.process_auto_attendance()

		record = frappe.db.get_value(
			"Attendance",
			{"employee": self.employee, "attendance_date": day, "docstatus": 1},
			["status", "working_hours", "late_entry"],
			as_dict=True,
		)
		self.assertEqual(record.status, "Present")
		self.assertEqual(record.working_hours, 8)
		self.assertFalse(record.late_entry)
