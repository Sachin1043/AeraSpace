from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from aeraspace.api import call as call_api
from aeraspace.api import chat as chat_api
from aeraspace.tests.test_chat import make_user

USERS = ("call-a@example.com", "call-b@example.com", "call-c@example.com")


class TestCalls(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.a, cls.b, cls.c = (make_user(u) for u in USERS)

	def setUp(self):
		with self.set_user(self.a):
			self.dm = chat_api.get_or_create_dm(self.b)
		for name in frappe.get_all("AS Call", filters={"channel": self.dm}, pluck="name"):
			frappe.cache.delete_value(call_api._key(name))
		frappe.db.delete("AS Call", {"channel": self.dm})

	def system_messages(self):
		return frappe.get_all(
			"AS Message",
			filters={"channel": self.dm, "message_type": "System"},
			order_by="creation desc",
			pluck="content",
		)

	def test_call_flow_join_leave_and_history(self):
		with self.set_user(self.a):
			started = call_api.start_call(self.dm, "Video")
		self.assertEqual(started["participants"], [self.a])
		self.assertIn("started a video call", self.system_messages()[0])

		with self.set_user(self.b):
			# starting again in the same conversation joins the running call
			joined = call_api.start_call(self.dm, "Audio")
			self.assertEqual(joined["name"], started["name"])
			self.assertEqual(joined["participants"], sorted([self.a, self.b]))
			self.assertEqual(call_api.get_active_call(self.dm)["name"], started["name"])

		with self.set_user(self.a):
			call_api.leave_call(started["name"])
		self.assertEqual(frappe.db.get_value("AS Call", started["name"], "status"), "Active")
		with self.set_user(self.b):
			call_api.leave_call(started["name"])

		doc = frappe.get_doc("AS Call", started["name"])
		self.assertEqual(doc.status, "Ended")
		self.assertEqual(doc.participants.splitlines(), [self.a, self.b])
		self.assertIn("Video call ended", self.system_messages()[0])
		with self.set_user(self.a):
			self.assertIsNone(call_api.get_active_call(self.dm))

	def test_unanswered_call_is_missed(self):
		with self.set_user(self.a):
			started = call_api.start_call(self.dm, "Audio")
			call_api.leave_call(started["name"])
		self.assertEqual(frappe.db.get_value("AS Call", started["name"], "status"), "Missed")
		self.assertIn("Missed audio call", self.system_messages()[0])

	def test_only_members_and_participants(self):
		with self.set_user(self.a):
			started = call_api.start_call(self.dm)
		with self.set_user(self.c):  # not in the conversation
			self.assertRaises(frappe.PermissionError, call_api.start_call, self.dm)
			self.assertRaises(frappe.PermissionError, call_api.join_call, started["name"])
		with self.set_user(self.a):  # b hasn't joined, so nothing can be sent to b
			self.assertRaises(frappe.ValidationError, call_api.signal, started["name"], self.b, "{}")

	def test_signal_relayed_to_the_other_participant(self):
		with self.set_user(self.a):
			started = call_api.start_call(self.dm)
		with self.set_user(self.b):
			call_api.join_call(started["name"])
		with patch("frappe.publish_realtime") as publish, self.set_user(self.a):
			call_api.signal(started["name"], self.b, '{"type": "offer", "sdp": "x"}')
		publish.assert_called_once_with(
			"as_call_signal",
			{"call": started["name"], "from": self.a, "data": {"type": "offer", "sdp": "x"}},
			user=self.b,
		)

	def test_stale_participants_drop_out_and_call_ends(self):
		with self.set_user(self.a):
			started = call_api.start_call(self.dm)
		frappe.cache.hset(call_api._key(started["name"]), self.a, 0)  # a's browser stopped pinging
		with self.set_user(self.b):
			fresh = call_api.start_call(self.dm)  # the old call is ended and a new one starts
		self.assertNotEqual(fresh["name"], started["name"])
		self.assertEqual(frappe.db.get_value("AS Call", started["name"], "status"), "Missed")
