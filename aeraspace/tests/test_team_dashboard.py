from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from aeraspace import hr
from aeraspace.api import attendance, team_dashboard
from aeraspace.tests.test_chat import make_user

BOSS = "td-boss@example.com"
WORKER = "td-worker@example.com"
RESTER = "td-rester@example.com"
ABSENT = "td-absent@example.com"
OTHER = "td-other@example.com"


class TestTeamDashboard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for user in (BOSS, WORKER, RESTER, ABSENT, OTHER):
			make_user(user)
		for user in (WORKER, RESTER, ABSENT):
			frappe.db.set_value("AS Employee Profile", user, "manager", BOSS)

	def setUp(self):
		employees = [hr.employee_for(u) for u in (WORKER, RESTER, ABSENT)]
		frappe.db.delete("Employee Checkin", {"employee": ("in", employees)})

	def step(self, user, action, when):
		with self.set_user(user), patch("aeraspace.api.attendance.now_datetime", return_value=when):
			getattr(attendance, action)()

	def test_manager_sees_each_reportee_live(self):
		now = datetime.combine(getdate(), datetime.min.time()) + timedelta(hours=11)
		self.step(WORKER, "check_in", now - timedelta(hours=2))
		self.step(RESTER, "check_in", now - timedelta(hours=2))
		self.step(RESTER, "start_break", now - timedelta(minutes=10))

		with self.set_user(BOSS), patch("aeraspace.api.team_dashboard.now_datetime", return_value=now):
			data = team_dashboard.get_today()
		rows = {r["user"]: r for r in data["rows"]}
		self.assertEqual(set(rows), {WORKER, RESTER, ABSENT})  # not the manager themselves
		self.assertEqual(rows[WORKER]["status"], "working")
		self.assertEqual(rows[RESTER]["status"], "break")
		self.assertEqual(rows[RESTER]["today"]["state"], "break")
		self.assertEqual(rows[RESTER]["today"]["worked_seconds"], (110) * 60)
		self.assertEqual(rows[ABSENT]["status"], "not_in")
		self.assertEqual(data["counts"]["working"], 1)
		self.assertEqual([r["user"] for r in data["rows"]][-1], ABSENT)  # missing people last

		with self.set_user(OTHER):  # no reportees: nothing to show
			self.assertFalse(team_dashboard.get_today()["allowed"])

	def test_watchers_get_live_updates(self):
		with patch("frappe.publish_realtime") as publish:
			self.step(
				WORKER, "check_in", datetime.combine(getdate(), datetime.min.time()) + timedelta(hours=9)
			)
		team_events = [c for c in publish.call_args_list if c.args[0] == "as_team_attendance"]
		self.assertIn(BOSS, {c.kwargs["user"] for c in team_events})
		self.assertIn("Administrator", {c.kwargs["user"] for c in team_events})
