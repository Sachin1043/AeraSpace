import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from aeraspace import hr, hr_rules
from aeraspace.api import attendance
from aeraspace.api import hr_requests as requests_api
from aeraspace.tests.test_chat import make_user

EMPLOYEE = "rq-employee@example.com"
MANAGER = "rq-manager@example.com"
OUTSIDER = "rq-outsider@example.com"


def weekday(offset_weeks: int, day: int = 0):
	"""A Monday (day=0) .. Saturday some weeks from now, never a Sunday."""
	monday = add_days(today(), -getdate(today()).weekday() + 7 * offset_weeks)
	return str(getdate(add_days(monday, day)))


class TestHrRequests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for user in (EMPLOYEE, MANAGER, OUTSIDER):
			make_user(user)
		hr.ensure_hr_setup()
		frappe.db.set_value("AS Employee Profile", EMPLOYEE, "manager", MANAGER)
		cls.employee = hr.employee_for(EMPLOYEE)
		frappe.db.set_value("Employee", cls.employee, "date_of_joining", add_days(today(), -400))
		# a fresh, full year of leave for the test employee
		for doctype in ("Leave Ledger Entry", "Leave Allocation", "Leave Policy Assignment"):
			frappe.db.delete(doctype, {"employee": cls.employee})
		hr_rules.assign_leave_policy(cls.employee)

	def setUp(self):
		for doctype in ("Leave Application", "Attendance Request", "Attendance"):
			for name in frappe.get_all(doctype, filters={"employee": self.employee}, pluck="name"):
				frappe.db.delete(doctype, {"name": name})
		frappe.db.delete(
			"Leave Ledger Entry", {"employee": self.employee, "transaction_type": "Leave Application"}
		)
		frappe.db.delete("AS Notification", {"user": ("in", (EMPLOYEE, MANAGER))})

	def apply(self, kind, start, end=None, **kwargs):
		with self.set_user(EMPLOYEE):
			return requests_api.apply(kind, start, end or start, reason="Family function", **kwargs)

	def decide(self, row, approve, user=MANAGER, note=None):
		with self.set_user(user):
			return requests_api.decide(row["kind"], row["name"], approve, note)

	def statuses(self, start, end):
		with self.set_user(EMPLOYEE):
			return {d["date"]: d["status"] for d in attendance.get_history(start, end)["days"]}

	def test_leave_goes_to_manager_and_shows_on_calendar(self):
		start, end = weekday(2, 1), weekday(2, 2)
		row = self.apply("leave", start, end, leave_type="Casual Leave")
		self.assertEqual((row["status"], row["approver"], row["days"]), ("Pending", MANAGER, 2))
		self.assertTrue(
			frappe.db.exists("AS Notification", {"user": MANAGER, "notification_type": "Request"})
		)
		with self.set_user(MANAGER):
			self.assertEqual([r["name"] for r in requests_api.get_approvals()["pending"]], [row["name"]])

		self.assertRaises(frappe.PermissionError, self.decide, row, 1, OUTSIDER)
		self.assertRaises(frappe.PermissionError, self.decide, row, 1, EMPLOYEE)  # not their own

		approved = self.decide(row, 1)
		self.assertEqual(approved["status"], "Approved")
		self.assertEqual(frappe.db.get_value("Leave Application", row["name"], "docstatus"), 1)
		self.assertEqual(set(self.statuses(start, end).values()), {"On Leave"})
		self.assertTrue(
			frappe.db.exists("AS Notification", {"user": EMPLOYEE, "notification_type": "Request"})
		)

		with self.set_user(EMPLOYEE):  # still in the future, so it can be cancelled
			self.assertEqual(requests_api.cancel("leave", row["name"])["status"], "Cancelled")
		self.assertNotIn("On Leave", self.statuses(start, end).values())

	def test_rejected_leave_keeps_the_note_and_frees_the_dates(self):
		day = weekday(3, 2)
		row = self.apply("leave", day, leave_type="Sick Leave")
		rejected = self.decide(row, 0, note="Release week")
		self.assertEqual((rejected["status"], rejected["note"]), ("Rejected", "Release week"))
		again = self.apply("leave", day, leave_type="Sick Leave")
		self.assertEqual(again["status"], "Pending")

	def test_past_wfh_marks_attendance_and_future_waits(self):
		past = weekday(-2, 1)
		row = self.decide(self.apply("wfh", past), 1)
		self.assertEqual(row["status"], "Approved")
		self.assertEqual(frappe.db.get_value("Attendance Request", row["name"], "docstatus"), 1)
		self.assertEqual(
			frappe.db.get_value("Attendance", {"employee": self.employee, "attendance_date": past}, "status"),
			"Work From Home",
		)
		self.assertEqual(self.statuses(past, past)[str(past)], "Work From Home")

		future = weekday(2, 3)
		later = self.decide(self.apply("wfh", future), 1)
		self.assertEqual(later["status"], "Approved")
		self.assertEqual(frappe.db.get_value("Attendance Request", later["name"], "docstatus"), 0)
		requests_api.submit_due_attendance_requests()  # its day hasn't come
		self.assertEqual(frappe.db.get_value("Attendance Request", later["name"], "docstatus"), 0)
		self.assertEqual(self.statuses(future, future)[str(future)], "Work From Home")

	def test_correction_fixes_a_missed_day(self):
		self.assertRaises(frappe.ValidationError, self.apply, "correction", str(add_days(today(), 1)))
		day = weekday(-1, 2)
		self.assertEqual(self.statuses(day, day)[str(day)], "Absent")
		row = self.decide(self.apply("correction", day), 1)
		self.assertEqual(row["status"], "Approved")
		self.assertEqual(self.statuses(day, day)[str(day)], "Present")

	def test_rejected_request_does_not_block_a_new_one(self):
		day = weekday(-1, 4)
		rejected = self.decide(self.apply("wfh", day), 0, note="Was in office")
		self.assertEqual(rejected["status"], "Rejected")
		self.assertEqual(frappe.db.get_value("Attendance Request", rejected["name"], "docstatus"), 2)
		self.assertEqual(self.apply("wfh", day)["status"], "Pending")
		with self.set_user(EMPLOYEE):
			mine = requests_api.get_my_requests()
		self.assertEqual([r["status"] for r in mine], ["Pending", "Rejected"])
		self.assertEqual(mine[1]["note"], "Was in office")
		self.assertTrue(mine[0]["can_cancel"])
