# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

NAMED_TYPES = ("Public", "Private", "Announcement")


class ASChannel(Document):
	def validate(self):
		if self.channel_type in NAMED_TYPES:
			self.channel_name = normalize_channel_name(self.channel_name)
			if not self.channel_name:
				frappe.throw(_("Channel name is required"))
			self.validate_unique_name()
		elif self.channel_type == "Direct" and not self.dm_key:
			frappe.throw(_("Direct channels need a member key"))

	def validate_unique_name(self):
		duplicate = frappe.db.exists(
			"AS Channel",
			{
				"channel_name": self.channel_name,
				"channel_type": ("in", NAMED_TYPES),
				"is_archived": 0,
				"name": ("!=", self.name),
			},
		)
		if duplicate:
			frappe.throw(_("A channel named #{0} already exists").format(self.channel_name))


def normalize_channel_name(name: str | None) -> str:
	"""Slack-style names: lowercase, hyphen separated, letters/digits/-/_ only."""
	name = (name or "").strip().lstrip("#").lower()
	name = re.sub(r"\s+", "-", name)
	name = re.sub(r"[^a-z0-9\-_]", "", name)
	return re.sub(r"-{2,}", "-", name).strip("-")[:80]
