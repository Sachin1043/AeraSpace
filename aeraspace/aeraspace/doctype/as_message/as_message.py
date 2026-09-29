# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

MAX_LENGTH = 10000
PREVIEW_LENGTH = 140


class ASMessage(Document):
	def validate(self):
		self.content = (self.content or "").strip()
		if self.is_new() and not self.content and not self.get_files():
			frappe.throw(_("Message cannot be empty"))
		if len(self.content) > MAX_LENGTH:
			frappe.throw(_("Message is too long (max {0} characters)").format(MAX_LENGTH))
		if self.is_new():
			self.validate_thread_and_reply()

	def validate_thread_and_reply(self):
		if self.thread_root:
			root = frappe.db.get_value(
				"AS Message", self.thread_root, ["channel", "thread_root"], as_dict=True
			)
			if not root or root.channel != self.channel:
				frappe.throw(_("Thread not found in this channel"))
			if root.thread_root:
				# replies to a reply belong to the same thread
				self.thread_root = root.thread_root

		if self.reply_to and frappe.db.get_value("AS Message", self.reply_to, "channel") != self.channel:
			frappe.throw(_("You can only reply to messages in the same conversation"))

	def get_files(self):
		return frappe.parse_json(self.files) if self.files else []

	def after_insert(self):
		from aeraspace.messages import add_thread_follower, publish_message_update
		from aeraspace.utils import publish_to_channel

		if self.thread_root:
			frappe.db.set_value(
				"AS Message",
				self.thread_root,
				{
					"reply_count": frappe.db.count("AS Message", {"thread_root": self.thread_root}),
					"last_reply_at": self.creation,
				},
				update_modified=False,
			)
			add_thread_follower(
				self.thread_root, frappe.db.get_value("AS Message", self.thread_root, "sender")
			)
			add_thread_follower(self.thread_root, self.sender)
			publish_message_update(self.thread_root)
		else:
			from aeraspace.notifications import plain_preview

			preview = plain_preview(self.content, self.get_files())
			frappe.db.set_value(
				"AS Channel",
				self.channel,
				{"last_message_at": self.creation, "last_message_preview": preview[:PREVIEW_LENGTH]},
				update_modified=False,
			)

		publish_to_channel(self.channel, "as_message_new", self.as_payload())

		from aeraspace.notifications import notify_new_message

		notify_new_message(self)

	def as_payload(self):
		from aeraspace.messages import build_payloads

		payload = build_payloads([self.as_dict()])[0]
		payload["client_id"] = self.flags.client_id
		return payload


def on_doctype_update():
	frappe.db.add_index("AS Message", ["channel", "creation"])
