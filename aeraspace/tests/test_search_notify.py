import frappe
from frappe.tests import IntegrationTestCase

from aeraspace.api import channel as channel_api
from aeraspace.api import chat
from aeraspace.api import notifications as notify_api
from aeraspace.api.search import parse_query, search
from aeraspace.tests.test_chat import make_user

USERS = ("sn-alice@example.com", "sn-bob@example.com", "sn-carol@example.com")


def notifications_for(user, **filters):
	return frappe.get_all(
		"AS Notification",
		filters={"user": user, **filters},
		fields=["notification_type", "message", "preview"],
	)


class TestSearchAndNotifications(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.alice, cls.bob, cls.carol = (make_user(u) for u in USERS)

	def setUp(self):
		frappe.db.delete("AS Notification", {"user": ("in", USERS)})

	def channel(self, channel_type="Public", members=None):
		with self.set_user(self.alice):
			return channel_api.create_channel(
				f"sn-{frappe.generate_hash(length=6)}", channel_type, members=members or []
			)

	# ---- search --------------------------------------------------------

	def test_parse_query(self):
		terms, filters = parse_query('shopify "inventory sync" from:sachin in:#eng type:pdf')
		self.assertEqual(terms, ["shopify", "inventory sync"])
		self.assertEqual(filters, {"from": ["sachin"], "in": ["#eng"], "type": ["pdf"]})

	def test_search_messages_with_filters(self):
		channel = self.channel(members=[self.bob])
		with self.set_user(self.alice):
			chat.send_message(channel, "Shopify inventory sync is failing")
		with self.set_user(self.bob):
			chat.send_message(channel, "Shopify orders look fine")

		with self.set_user(self.carol):
			both = [m.content for m in search("shopify")["messages"]]
			self.assertIn("Shopify inventory sync is failing", both)
			self.assertIn("Shopify orders look fine", both)
			only_alice = [m.content for m in search(f"shopify from:{self.alice}")["messages"]]
			self.assertEqual(only_alice, ["Shopify inventory sync is failing"])
			self.assertEqual(
				[m.content for m in search("shopify inventory")["messages"]],
				["Shopify inventory sync is failing"],
			)

	def test_search_never_leaks_private_channels(self):
		private = self.channel("Private", members=[self.bob])
		with self.set_user(self.alice):
			chat.send_message(private, "top secret launch plan xyzzy")
		with self.set_user(self.bob):
			self.assertEqual(len(search("xyzzy")["messages"]), 1)
		with self.set_user(self.carol):
			self.assertEqual(search("xyzzy")["messages"], [])

	def test_search_like_wildcards_are_literal(self):
		channel = self.channel()
		with self.set_user(self.alice):
			chat.send_message(channel, "discount is 50% today")
			chat.send_message(channel, "nothing to see here")
			contents = [m.content for m in search("50%")["messages"]]
		self.assertEqual(contents, ["discount is 50% today"])

	def test_search_files_by_name_and_type(self):
		channel = self.channel()
		with self.set_user(self.alice):
			for name in ("API_Documentation.txt", "architecture.png"):
				file = frappe.get_doc(
					{
						"doctype": "File",
						"file_name": name,
						"content": frappe.generate_hash().encode(),
						"is_private": 1,
						"attached_to_doctype": "AS Channel",
						"attached_to_name": channel,
					}
				).insert(ignore_permissions=True)
				chat.send_message(channel, "", files=[file.name])
			self.assertEqual(
				[f["file_name"] for f in search("documentation")["files"]], ["API_Documentation.txt"]
			)
			self.assertEqual(
				[
					f["file_name"]
					for f in search(
						f"type:image in:#{frappe.db.get_value('AS Channel', channel, 'channel_name')}"
					)["files"]
				],
				["architecture.png"],
			)

	# ---- notifications -------------------------------------------------

	def test_mention_notifies_even_in_mentions_only_channel(self):
		channel = self.channel(members=[self.bob, self.carol])
		with self.set_user(self.alice):
			msg = chat.send_message(channel, f"<@{self.bob}> can you review the PR?")
		bob = notifications_for(self.bob, notification_type="Mention")
		self.assertEqual([(n.notification_type, n.message) for n in bob], [("Mention", msg["name"])])
		self.assertIn("@", bob[0].preview)
		self.assertNotIn("<@", bob[0].preview)
		self.assertEqual(notifications_for(self.carol, notification_type="Mention"), [])

	def test_muted_channel_gets_nothing(self):
		channel = self.channel(members=[self.bob])
		with self.set_user(self.bob):
			notify_api.set_channel_notify(channel, "Nothing")
		with self.set_user(self.alice):
			chat.send_message(channel, f"<@{self.bob}> ping")
		self.assertEqual(notifications_for(self.bob, notification_type="Mention"), [])

	def test_channel_wide_mention(self):
		channel = self.channel(members=[self.bob, self.carol])
		with self.set_user(self.alice):
			chat.send_message(channel, "<!channel> standup in 5 minutes")
		self.assertEqual(len(notifications_for(self.bob, notification_type="Mention")), 1)
		self.assertEqual(len(notifications_for(self.carol, notification_type="Mention")), 1)
		self.assertEqual(notifications_for(self.alice, notification_type="Mention"), [])

	def test_thread_reply_notifies_followers_only(self):
		channel = self.channel(members=[self.bob, self.carol])
		with self.set_user(self.alice):
			root = chat.send_message(channel, "Shopify sync failing")["name"]
		with self.set_user(self.bob):
			chat.send_message(channel, "checking the scheduler", thread_root=root)
		self.assertEqual(len(notifications_for(self.alice, notification_type="Thread Reply")), 1)
		self.assertEqual(notifications_for(self.carol, notification_type="Thread Reply"), [])

	def test_invite_notifications(self):
		self.channel(members=[self.bob])
		self.assertEqual(len(notifications_for(self.bob, notification_type="Invite")), 1)
		self.assertEqual(notifications_for(self.alice, notification_type="Invite"), [])

	def test_mark_read_and_unread_count(self):
		channel = self.channel(members=[self.bob])
		with self.set_user(self.alice):
			chat.send_message(channel, f"<@{self.bob}> one")
			chat.send_message(channel, f"<@{self.bob}> two")
		with self.set_user(self.bob):
			self.assertEqual(notify_api.get_unread_count(), 3)  # invite + 2 mentions
			first = notify_api.get_notifications()[0]
			self.assertEqual(notify_api.mark_notifications_read([first.name]), 2)
			self.assertEqual(notify_api.mark_notifications_read(), 0)
		with self.set_user(self.carol):
			self.assertEqual(notify_api.get_notifications(), [])  # notifications are personal

	def test_sidebar_preview_shows_names_not_tokens(self):
		channel = self.channel(members=[self.bob])
		with self.set_user(self.alice):
			chat.send_message(channel, f"hey <@{self.bob}>")
		preview = frappe.db.get_value("AS Channel", channel, "last_message_preview")
		self.assertNotIn("<@", preview)

	def test_preview_strips_markdown(self):
		from aeraspace.notifications import plain_preview

		text = "Deploy **today** with `bench migrate`\n```\nbench --site x migrate\n```\n> note [docs](https://x.y)"
		self.assertEqual(
			plain_preview(text), "Deploy today with bench migrate bench --site x migrate note docs"
		)
