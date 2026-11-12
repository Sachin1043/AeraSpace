from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_datetime, today

from aeraspace import tasks
from aeraspace.api import eod, timesheet
from aeraspace.api import project as project_api
from aeraspace.api import task as task_api
from aeraspace.tests.test_chat import make_user

USERS = ("et-manager@example.com", "et-dev@example.com", "et-other@example.com")


class TestEodAndTimesheets(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.manager, cls.dev, cls.other = (make_user(u) for u in USERS)
		frappe.db.set_value("AS Employee Profile", cls.dev, "manager", cls.manager)

	def setUp(self):
		frappe.db.delete("AS Daily Update", {"user": ("in", USERS)})
		frappe.db.delete("AS Notification", {"user": ("in", USERS)})
		sheets = frappe.get_all("Timesheet", filters={"user": ("in", USERS)}, pluck="name")
		frappe.db.delete("Timesheet Detail", {"parent": ("in", sheets or [""])})
		frappe.db.delete("Timesheet", {"name": ("in", sheets or [""])})

	def project(self):
		suffix = frappe.generate_hash(length=4).upper()
		with self.set_user(self.manager):
			return project_api.create_project(
				f"ET {suffix}", f"E{suffix}", members=[self.dev], client="Acme Ltd"
			)

	# ---- EOD ------------------------------------------------------------

	def test_one_update_per_day_and_edit(self):
		with self.set_user(self.dev):
			first = eod.save_update(completed="Fixed sync", post_to_channel=0)
			second = eod.save_update(
				completed="Fixed sync\nAdded tests", blockers="Waiting for API keys", post_to_channel=0
			)
		self.assertEqual(first["name"], second["name"])
		self.assertEqual(frappe.db.count("AS Daily Update", {"user": self.dev, "update_date": today()}), 1)
		self.assertEqual(second["blockers"], "Waiting for API keys")

	def test_empty_and_future_updates_rejected(self):
		with self.set_user(self.dev):
			self.assertRaises(frappe.ValidationError, eod.save_update, completed="  ", post_to_channel=0)
			self.assertRaises(
				frappe.ValidationError,
				eod.save_update,
				date=add_days(today(), 1),
				completed="x",
				post_to_channel=0,
			)

	def test_suggestions_from_tasks(self):
		name = self.project()
		with self.set_user(self.manager):
			done = task_api.create_task(name, "Ship invoice fix", assignee=self.dev)
			busy = task_api.create_task(name, "Refactor sync", assignee=self.dev)
		with self.set_user(self.dev):
			task_api.update_task(done.name, status="Done")
			task_api.update_task(busy.name, status="In Progress")
			data = eod.get_my_update()
		self.assertIn(done.name, [t.name for t in data["suggestions"]["completed"]])
		self.assertIn(busy.name, [t.name for t in data["suggestions"]["in_progress"]])

	def test_team_report_visibility_and_states(self):
		with self.set_user(self.dev):
			eod.save_update(completed="Done things", post_to_channel=0)
		with self.set_user(self.manager):
			report = eod.get_team_report()
			rows = {r["user"]: r for r in report["rows"]}
			self.assertEqual(rows[self.dev]["state"], "submitted")
			self.assertIn(self.manager, rows)
			self.assertNotIn(self.other, rows)  # not a reportee
			self.assertEqual(len(eod.get_history(self.dev)), 1)
		with self.set_user(self.other):
			self.assertRaises(frappe.PermissionError, eod.get_history, self.dev)

	def test_update_posted_to_eod_channel_and_refreshed(self):
		with self.set_user(self.manager):
			from aeraspace.api import channel as channel_api

			channel = channel_api.create_channel(f"eod-{frappe.generate_hash(length=5)}", "Public")
		settings = frappe.get_doc("AS Settings")
		settings.eod_channel = channel
		settings.save()
		try:
			with self.set_user(self.dev):
				first = eod.save_update(completed="Fixed sync")
				second = eod.save_update(completed="Fixed sync and tests")
			self.assertEqual(first["posted_message"], second["posted_message"])
			content = frappe.db.get_value("AS Message", second["posted_message"], "content")
			self.assertIn("Fixed sync and tests", content)
			self.assertTrue(frappe.db.exists("AS Channel Member", {"channel": channel, "user": self.dev}))
		finally:
			settings.eod_channel = None
			settings.save()

	def test_reminder_once_for_missing_updates(self):
		with self.set_user(self.dev):
			eod.save_update(completed="Done", post_to_channel=0)
		frappe.cache.hdel(tasks.REMINDED_KEY, str(today()))
		late = get_datetime(f"{today()} 23:59:00")
		with (
			patch("aeraspace.tasks.now_datetime", return_value=late),
			patch("aeraspace.tasks.is_working_day", return_value=True),
		):
			tasks.eod_reminders()
			tasks.eod_reminders()  # second run the same day does nothing
		self.assertEqual(
			frappe.db.count("AS Notification", {"user": self.other, "notification_type": "Reminder"}), 1
		)
		self.assertEqual(
			frappe.db.count("AS Notification", {"user": self.dev, "notification_type": "Reminder"}), 0
		)

	# ---- timesheets -----------------------------------------------------

	def test_log_time_rules(self):
		name = self.project()
		with self.set_user(self.dev):
			entry = timesheet.log_time(name, 200, description="Debugged scheduler")
			self.assertEqual(entry["minutes"], 200)
			self.assertRaises(frappe.ValidationError, timesheet.log_time, name, 0)
			self.assertRaises(
				frappe.ValidationError, timesheet.log_time, name, 60, log_date=add_days(today(), 1)
			)
		with self.set_user(self.other):  # not a project member
			self.assertRaises(frappe.PermissionError, timesheet.log_time, name, 60)
			self.assertRaises(frappe.PermissionError, timesheet.delete_log, entry["name"])

	def test_task_must_match_project_and_totals_on_task(self):
		one, two = self.project(), self.project()
		with self.set_user(self.manager):
			task = task_api.create_task(one, "Sync job")
		with self.set_user(self.dev):
			self.assertRaises(frappe.ValidationError, timesheet.log_time, two, 30, task=task.name)
			timesheet.log_time(one, 90, task=task.name)
			timesheet.log_time(one, 30, task=task.name)
			self.assertEqual(task_api.get_task(task.name).logged_minutes, 120)

	def test_report_grouping_and_visibility(self):
		name = self.project()
		with self.set_user(self.dev):
			timesheet.log_time(name, 120)
		with self.set_user(self.manager):
			timesheet.log_time(name, 60)
			by_employee = timesheet.get_report(today(), today(), "employee", project=name)
			by_client = timesheet.get_report(today(), today(), "client", project=name)
		self.assertEqual(by_employee["total_minutes"], 180)
		self.assertEqual({g["key"] for g in by_employee["groups"]}, {self.dev, self.manager})
		self.assertEqual(by_client["groups"][0]["label"], "Acme Ltd")
		with self.set_user(self.other):  # sees nothing of this project
			self.assertEqual(timesheet.get_report(today(), today(), project=name)["total_minutes"], 0)
		with self.set_user(self.dev):  # sees only their own
			self.assertEqual(timesheet.get_report(today(), today(), project=name)["total_minutes"], 120)

	# ---- stored as ERPNext Timesheets -------------------------------------

	def sheets(self, user):
		return frappe.get_all(
			"Timesheet",
			filters={"user": user, "docstatus": ("<", 2)},
			fields=["name", "docstatus", "start_date", "total_hours"],
			order_by="creation",
		)

	def test_entries_are_rows_of_one_daily_timesheet(self):
		name = self.project()
		with self.set_user(self.manager):
			task = task_api.create_task(name, "Sync job")
		with self.set_user(self.dev):
			first = timesheet.log_time(name, 90, task=task.name, description="Fix")
			second = timesheet.log_time(name, 30)
		sheets = self.sheets(self.dev)
		self.assertEqual(len(sheets), 1)
		self.assertEqual(sheets[0].total_hours, 2)
		rows = frappe.get_doc("Timesheet", sheets[0].name).time_logs
		self.assertEqual([r.name for r in rows], [first["name"], second["name"]])
		self.assertEqual(get_datetime(rows[0].from_time).strftime("%H:%M"), "09:00")
		self.assertEqual(rows[1].from_time, rows[0].to_time)  # laid out back to back
		self.assertEqual(first["minutes"], 90)
		self.assertEqual(frappe.db.get_value("Task", task.name, "as_status"), "Todo")  # board untouched

	def test_edit_move_and_delete_entries(self):
		name = self.project()
		yesterday = add_days(today(), -1)
		with self.set_user(self.dev):
			first = timesheet.log_time(name, 60)
			second = timesheet.log_time(name, 30)
			edited = timesheet.update_log(first["name"], minutes=120, description="Longer")
			self.assertEqual((edited["minutes"], edited["description"]), (120, "Longer"))
			row = frappe.db.get_value("Timesheet Detail", second["name"], ["from_time"], as_dict=True)
			self.assertEqual(get_datetime(row.from_time).strftime("%H:%M"), "11:00")  # re-laid after edit

			moved = timesheet.update_log(second["name"], log_date=yesterday)
			self.assertEqual(moved["log_date"], str(yesterday))
			self.assertEqual(len(self.sheets(self.dev)), 2)

			timesheet.delete_log(moved["name"])  # last entry of yesterday: its sheet goes too
			self.assertEqual([s.start_date for s in self.sheets(self.dev)], [frappe.utils.getdate(today())])
			self.assertEqual(len(timesheet.get_my_logs(yesterday, today())), 1)
		with self.set_user(self.manager):
			self.assertRaises(frappe.PermissionError, timesheet.update_log, first["name"], minutes=10)

	def test_day_limit_and_submitted_sheets(self):
		name = self.project()
		with self.set_user(self.dev):
			entry = timesheet.log_time(name, 23 * 60)
			self.assertRaises(frappe.ValidationError, timesheet.log_time, name, 61)

		sheet = frappe.get_doc("Timesheet", self.sheets(self.dev)[0].name)
		sheet.time_logs[0].activity_type = "Execution"
		sheet.flags.ignore_permissions = True
		sheet.submit()

		with self.set_user(self.dev):
			self.assertRaises(frappe.ValidationError, timesheet.update_log, entry["name"], minutes=60)
			later = timesheet.log_time(name, 30)  # goes to a new draft, after the submitted time
		row = frappe.db.get_value("Timesheet Detail", later["name"], ["parent", "from_time"], as_dict=True)
		self.assertNotEqual(row.parent, sheet.name)
		self.assertEqual(get_datetime(row.from_time), get_datetime(sheet.time_logs[0].to_time))
