import frappe
from frappe.tests import IntegrationTestCase

from aeraspace.api import channel as channel_api
from aeraspace.api import chat
from aeraspace.api import files as files_api
from aeraspace.tests.test_chat import make_user

USERS = ("rc-alice@example.com", "rc-bob@example.com", "rc-carol@example.com")


class TestRichChat(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.alice, cls.bob, cls.carol = (make_user(u) for u in USERS)

	def new_channel(self, name="rich", channel_type="Public", members=None):
		with self.set_user(self.alice):
			return channel_api.create_channel(
				f"{name}-{frappe.generate_hash(length=6)}", channel_type, members=members or [self.bob]
			)

	def test_edit_only_own_message(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			msg = chat.send_message(channel, "helo")["name"]
			updated = chat.edit_message(msg, "hello")
		self.assertEqual(updated["content"], "hello")
		self.assertTrue(updated["is_edited"])
		with self.set_user(self.bob):
			self.assertRaises(frappe.PermissionError, chat.edit_message, msg, "hacked")

	def test_delete_by_owner_or_admin_only(self):
		channel = self.new_channel()
		with self.set_user(self.bob):
			bob_msg = chat.send_message(channel, "bob here")["name"]
			alice_msg = None
		with self.set_user(self.alice):
			alice_msg = chat.send_message(channel, "alice here")["name"]
		with self.set_user(self.bob):
			self.assertRaises(frappe.PermissionError, chat.delete_message, alice_msg)
		with self.set_user(self.alice):  # alice created the channel, so she is admin
			deleted = chat.delete_message(bob_msg)
		self.assertTrue(deleted["is_deleted"])
		self.assertEqual(deleted["content"], "")

	def test_reactions_toggle(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			msg = chat.send_message(channel, "ship it")["name"]
			chat.toggle_reaction(msg, "👍")
		with self.set_user(self.bob):
			payload = chat.toggle_reaction(msg, "👍")
		self.assertEqual(sorted(payload["reactions"]["👍"]), sorted([self.alice, self.bob]))
		with self.set_user(self.bob):
			payload = chat.toggle_reaction(msg, "👍")
		self.assertEqual(payload["reactions"]["👍"], [self.alice])

	def test_threads(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			root = chat.send_message(channel, "Shopify inventory sync is failing.")["name"]
		with self.set_user(self.bob):
			chat.send_message(channel, "Can you check the scheduler?", thread_root=root)
		with self.set_user(self.alice):
			reply = chat.send_message(channel, "Yes, I'll check it.", thread_root=root)
			thread = chat.get_thread(root)
			top_level = [m["name"] for m in chat.get_messages(channel)["messages"]]

		self.assertEqual(thread["root"]["reply_count"], 2)
		self.assertEqual(len(thread["replies"]), 2)
		self.assertTrue(thread["is_following"])
		self.assertIn(root, top_level)
		self.assertNotIn(reply["name"], top_level)  # replies stay out of the channel view

		with self.set_user(self.bob):  # replier auto-follows, and can unfollow
			self.assertFalse(chat.toggle_follow(root))

	def test_thread_replies_do_not_count_as_unread(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			root = chat.send_message(channel, "root")["name"]
		with self.set_user(self.bob):
			chat.mark_read(channel)
		with self.set_user(self.alice):
			chat.send_message(channel, "in thread", thread_root=root)
		with self.set_user(self.bob):
			row = next(c for c in chat.get_sidebar() if c.name == channel)
		self.assertEqual(row.unread, 0)

	def test_reply_to_quotes_original(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			original = chat.send_message(channel, "Please create an issue.")["name"]
		with self.set_user(self.bob):
			reply = chat.send_message(channel, "Done", reply_to=original)
		self.assertEqual(reply["reply_to"]["name"], original)
		self.assertEqual(reply["reply_to"]["content"], "Please create an issue.")

	def test_pin_and_bookmark(self):
		channel = self.new_channel()
		with self.set_user(self.alice):
			msg = chat.send_message(channel, "Deployment instructions")["name"]
			chat.toggle_pin(msg)
			self.assertEqual([m["name"] for m in chat.get_pinned(channel)], [msg])
			self.assertTrue(chat.toggle_bookmark(msg))
			self.assertEqual([b["name"] for b in chat.get_bookmarks()], [msg])
		with self.set_user(self.bob):
			self.assertEqual(chat.get_bookmarks(), [])  # bookmarks are personal

	def test_announcement_only_admins_post(self):
		channel = self.new_channel("announce", "Announcement")
		with self.set_user(self.alice):
			root = chat.send_message(channel, "Office closed Friday")["name"]
		with self.set_user(self.bob):
			self.assertRaises(frappe.PermissionError, chat.send_message, channel, "me too")
			chat.send_message(channel, "Thanks!", thread_root=root)  # thread replies are allowed
		with self.set_user(self.carol):  # open channel: readable and joinable
			chat.get_messages(channel)
			channel_api.join_channel(channel)

	def test_file_must_belong_to_channel_and_sender(self):
		channel = self.new_channel()
		other = self.new_channel("other")
		with self.set_user(self.alice):
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "notes.txt",
					"content": b"hello",
					"is_private": 1,
					"attached_to_doctype": "AS Channel",
					"attached_to_name": channel,
				}
			).insert(ignore_permissions=True)
			sent = chat.send_message(channel, "", files=[file.name])
			self.assertEqual(sent["files"][0]["file_name"], "notes.txt")
			self.assertEqual(files_api.get_channel_files(channel)[0]["name"], file.name)
			self.assertRaises(frappe.ValidationError, chat.send_message, other, "", files=[file.name])
		with self.set_user(self.bob):
			self.assertRaises(frappe.ValidationError, chat.send_message, channel, "mine", files=[file.name])

	def test_private_file_access_follows_channel(self):
		channel = self.new_channel("secret", "Private", members=[self.bob])
		with self.set_user(self.alice):
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "secret.txt",
					"content": b"top secret",
					"is_private": 1,
					"attached_to_doctype": "AS Channel",
					"attached_to_name": channel,
				}
			).insert(ignore_permissions=True)
		self.assertTrue(frappe.has_permission("File", "read", doc=file, user=self.bob))
		self.assertFalse(frappe.has_permission("File", "read", doc=file, user=self.carol))

	def test_channel_not_writable_via_rest(self):
		channel = self.new_channel()
		doc = frappe.get_doc("AS Channel", channel)
		self.assertTrue(frappe.has_permission("AS Channel", "read", doc=doc, user=self.bob))
		self.assertFalse(frappe.has_permission("AS Channel", "write", doc=doc, user=self.bob))

	def test_member_role_management(self):
		channel = self.new_channel()
		with self.set_user(self.bob):
			self.assertRaises(frappe.PermissionError, channel_api.set_member_role, channel, self.bob, "Admin")
		with self.set_user(self.alice):
			self.assertRaises(
				frappe.ValidationError, channel_api.set_member_role, channel, self.alice, "Member"
			)
			channel_api.set_member_role(channel, self.bob, "Admin")
		self.assertEqual(
			frappe.db.get_value("AS Channel Member", {"channel": channel, "user": self.bob}, "role"), "Admin"
		)
