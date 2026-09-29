import frappe
from frappe.tests import IntegrationTestCase

from aeraspace.api import channel as channel_api
from aeraspace.api import chat, presence
from aeraspace.api.directory import get_people

USERS = ("as-alice@example.com", "as-bob@example.com", "as-carol@example.com")


def make_user(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": "AeraSpace User"}],
			}
		).insert(ignore_permissions=True)
	return email


class TestChat(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.alice, cls.bob, cls.carol = (make_user(u) for u in USERS)

	def unread(self, user, channel):
		with self.set_user(user):
			row = next(c for c in chat.get_sidebar() if c.name == channel)
		return row.unread

	def test_new_user_gets_profile(self):
		self.assertTrue(frappe.db.exists("AS Employee Profile", self.alice))
		with self.set_user(self.alice):
			self.assertIn(self.bob, [p.user for p in get_people()])

	def test_direct_message_is_reused(self):
		with self.set_user(self.alice):
			first = chat.get_or_create_dm(self.bob)
		with self.set_user(self.bob):
			second = chat.get_or_create_dm(self.alice)
		self.assertEqual(first, second)

	def test_private_channel_hidden_from_non_members(self):
		with self.set_user(self.alice):
			name = channel_api.create_channel("Secret Plans", "Private", members=[self.bob])

		with self.set_user(self.bob):
			chat.get_messages(name)

		with self.set_user(self.carol):
			self.assertRaises(frappe.PermissionError, chat.get_messages, name)
			self.assertRaises(frappe.PermissionError, chat.send_message, name, "hi")
			self.assertRaises(frappe.PermissionError, channel_api.join_channel, name)
			self.assertNotIn(name, [c.name for c in channel_api.browse_channels()])

	def test_public_channel_join_before_posting(self):
		with self.set_user(self.alice):
			name = channel_api.create_channel("General Chat", "Public")

		with self.set_user(self.carol):
			chat.get_messages(name)  # readable without joining
			self.assertRaises(frappe.PermissionError, chat.send_message, name, "hello")
			channel_api.join_channel(name)
			chat.send_message(name, "hello")

		with self.set_user(self.alice):
			contents = [m.content for m in chat.get_messages(name)["messages"]]
		self.assertIn("hello", contents)

	def test_unread_counts_and_mark_read(self):
		with self.set_user(self.alice):
			dm = chat.get_or_create_dm(self.carol)
		with self.set_user(self.carol):
			chat.send_message(dm, "one")
			chat.send_message(dm, "two")

		self.assertEqual(self.unread(self.alice, dm), 2)
		self.assertEqual(self.unread(self.carol, dm), 0)  # own messages never count

		with self.set_user(self.alice):
			chat.mark_read(dm)
		self.assertEqual(self.unread(self.alice, dm), 0)

	def test_channel_name_normalized_and_unique(self):
		with self.set_user(self.alice):
			name = channel_api.create_channel("  #Shopify Integration!! ", "Public")
			self.assertEqual(frappe.db.get_value("AS Channel", name, "channel_name"), "shopify-integration")
			self.assertRaises(
				frappe.ValidationError, channel_api.create_channel, "shopify integration", "Private"
			)

	def test_group_with_one_person_becomes_dm(self):
		with self.set_user(self.alice):
			channel = chat.create_group([self.bob])
		self.assertEqual(frappe.db.get_value("AS Channel", channel, "channel_type"), "Direct")

	def test_message_pagination(self):
		with self.set_user(self.alice):
			name = channel_api.create_channel("paging-test", "Public")
			for i in range(5):
				chat.send_message(name, f"m{i}")
			page = chat.get_messages(name, limit=3)
			self.assertTrue(page["has_more"])
			self.assertEqual([m.content for m in page["messages"]], ["m2", "m3", "m4"])
			older = chat.get_messages(name, before=page["messages"][0].creation, limit=10)
			self.assertEqual([m.content for m in older["messages"]][-2:], ["m0", "m1"])

	def test_empty_message_rejected(self):
		with self.set_user(self.alice):
			dm = chat.get_or_create_dm(self.bob)
			self.assertRaises(frappe.ValidationError, chat.send_message, dm, "   ")

	def test_presence_round_trip(self):
		with self.set_user(self.alice):
			presence.heartbeat("online")
		with self.set_user(self.bob):
			presence.heartbeat("away")
			states = presence.get_presence()
		self.assertEqual(states.get(self.alice), "online")
		self.assertEqual(states.get(self.bob), "away")
		frappe.parse_json(frappe.as_json(states))  # must be JSON serializable

		with self.set_user(self.alice):
			presence.go_offline()
			self.assertNotIn(self.alice, presence.get_presence())

	def test_profile_photo_upload_and_remove(self):
		from io import BytesIO
		from unittest.mock import patch

		from werkzeug.datastructures import FileStorage

		from aeraspace.api import directory

		png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
		png += bytes.fromhex("1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
		fake_request = type("R", (), {"files": {"file": FileStorage(BytesIO(png), filename="me.png")}})()
		with self.set_user(self.alice), patch.object(frappe, "request", fake_request, create=True):
			url = directory.upload_profile_photo()
		self.assertTrue(url.startswith("/files/"))
		self.assertEqual(frappe.db.get_value("User", self.alice, "user_image"), url)
		with self.set_user(self.bob):
			alice = next(p for p in get_people() if p.user == self.alice)
		self.assertEqual(alice.user_image, url)

		bad = type("R", (), {"files": {"file": FileStorage(BytesIO(b"x"), filename="virus.exe")}})()
		with self.set_user(self.alice), patch.object(frappe, "request", bad, create=True):
			self.assertRaises(frappe.ValidationError, directory.upload_profile_photo)

		with self.set_user(self.alice):
			directory.remove_profile_photo()
		self.assertIsNone(frappe.db.get_value("User", self.alice, "user_image"))

	def test_invisible_looks_offline_to_others(self):
		from aeraspace.api.directory import update_my_profile

		with self.set_user(self.alice):
			presence.heartbeat("online")
			update_my_profile(availability="Invisible")
			self.assertEqual(presence.get_presence().get(self.alice), "online")  # you still see yourself
			me = next(p for p in get_people() if p.user == self.alice)
			self.assertEqual(me.availability, "Invisible")
		with self.set_user(self.bob):
			self.assertEqual(presence.get_presence().get(self.alice), "offline")
			alice = next(p for p in get_people() if p.user == self.alice)
			self.assertEqual(alice.availability, "Auto")  # the invisible setting itself is never revealed
		with self.set_user(self.alice):
			update_my_profile(availability="Busy")
		with self.set_user(self.bob):
			self.assertEqual(presence.get_presence().get(self.alice), "online")
			self.assertEqual(next(p for p in get_people() if p.user == self.alice).availability, "Busy")
		with self.set_user(self.alice):
			self.assertRaises(frappe.ValidationError, update_my_profile, availability="Sleeping")
			update_my_profile(availability="Auto")
