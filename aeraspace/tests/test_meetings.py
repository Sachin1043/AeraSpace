from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from aeraspace.api import meeting
from aeraspace.tests.test_chat import make_user

HOST = "mt-host@example.com"
GUEST = "mt-guest@example.com"
GUEST2 = "mt-guest2@example.com"
OUTSIDER = "mt-out@example.com"


def at(minutes: int) -> str:
	return str((now_datetime() + timedelta(minutes=minutes)).replace(microsecond=0))


class TestMeetings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for user in (HOST, GUEST, GUEST2, OUTSIDER):
			make_user(user)

	def setUp(self):
		frappe.db.delete("AS Meeting", {"host": HOST})
		frappe.db.delete("AS Notification", {"user": ("in", (HOST, GUEST, GUEST2))})

	def schedule(self, minutes=60, users=(GUEST, GUEST2), **kwargs):
		with self.set_user(HOST):
			return meeting.schedule("Sprint planning", at(minutes), 30, users=list(users), **kwargs)

	def test_schedule_makes_a_meeting_chat_and_invites(self):
		m = self.schedule()
		self.assertEqual(m["channel_type"], "Group")
		self.assertEqual({i["user"] for i in m["invitees"]}, {GUEST, GUEST2})
		self.assertEqual(
			frappe.db.count("AS Notification", {"user": GUEST, "notification_type": "Meeting"}), 1
		)
		self.assertFalse(frappe.db.exists("AS Notification", {"user": GUEST, "notification_type": "Invite"}))
		messages = frappe.get_all("AS Message", filters={"channel": m["channel"]}, pluck="content")
		self.assertTrue(any("scheduled Sprint planning" in c for c in messages))

		with self.set_user(GUEST):
			self.assertEqual([r["name"] for r in meeting.get_meetings()], [m["name"]])
			self.assertEqual(meeting.respond(m["name"], "Accepted")["my_response"], "Accepted")
		with self.set_user(OUTSIDER):
			self.assertEqual(meeting.get_meetings(), [])
			self.assertRaises(frappe.PermissionError, meeting.respond, m["name"], "Accepted")

	def test_one_person_meets_in_their_direct_chat(self):
		m = self.schedule(users=[GUEST])
		self.assertEqual(m["channel_type"], "Direct")

	def test_only_host_edits_and_moving_resets_answers(self):
		m = self.schedule()
		with self.set_user(GUEST):
			meeting.respond(m["name"], "Accepted")
			self.assertRaises(frappe.PermissionError, meeting.cancel, m["name"])
		with self.set_user(HOST):
			moved = meeting.update(m["name"], "Sprint planning", at(120), 45)
		self.assertEqual(moved["duration"], 45)
		self.assertEqual({i["response"] for i in moved["invitees"]}, {"Pending"})
		with self.set_user(HOST):
			self.assertEqual(meeting.cancel(m["name"])["status"], "Cancelled")
		self.assertTrue(
			frappe.db.exists(
				"AS Notification",
				{"user": GUEST, "notification_type": "Meeting", "preview": ("like", "cancelled%")},
			)
		)

	def test_validation(self):
		with self.set_user(HOST):
			self.assertRaises(frappe.ValidationError, meeting.schedule, "Old", at(-60), 30, users=[GUEST])
			self.assertRaises(frappe.ValidationError, meeting.schedule, "", at(60), 30, users=[GUEST])
			self.assertRaises(frappe.ValidationError, meeting.schedule, "Odd", at(60), 7, users=[GUEST])
			self.assertRaises(frappe.ValidationError, meeting.schedule, "Alone", at(60), 30, users=[])

	def test_reminder_once_and_not_for_people_who_declined(self):
		m = self.schedule(minutes=3)
		with self.set_user(GUEST2):
			meeting.respond(m["name"], "Declined")
		frappe.db.delete("AS Notification", {"user": ("in", (HOST, GUEST, GUEST2))})
		with patch("aeraspace.api.meeting.now_datetime", return_value=now_datetime()):
			meeting.send_reminders()
			meeting.send_reminders()
		reminded = frappe.get_all(
			"AS Notification",
			filters={"notification_type": "Meeting", "preview": ("like", "%starts at%")},
			pluck="user",
		)
		self.assertEqual(sorted(reminded), sorted([HOST, GUEST]))
