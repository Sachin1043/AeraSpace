# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

SECTIONS = ("completed", "in_progress", "blockers", "tomorrow")


class ASDailyUpdate(Document):
	def validate(self):
		for field in SECTIONS:
			self.set(field, (self.get(field) or "").strip())
		if not any(self.get(field) for field in SECTIONS):
			frappe.throw(_("Write at least one section of your update"))


def on_doctype_update():
	frappe.db.add_unique("AS Daily Update", ["user", "update_date"], constraint_name="unique_user_date")
