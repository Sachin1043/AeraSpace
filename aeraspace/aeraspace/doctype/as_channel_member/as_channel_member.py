# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ASChannelMember(Document):
	def validate(self):
		duplicate = frappe.db.exists(
			"AS Channel Member",
			{"channel": self.channel, "user": self.user, "name": ("!=", self.name)},
		)
		if duplicate:
			frappe.throw(_("{0} is already a member of this channel").format(self.user))


def on_doctype_update():
	frappe.db.add_unique("AS Channel Member", ["channel", "user"], constraint_name="unique_channel_user")
