# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

MAX_MINUTES_PER_ENTRY = 24 * 60


class ASTimeLog(Document):
	def validate(self):
		if not self.minutes or self.minutes <= 0:
			frappe.throw(_("Duration must be more than zero"))
		if self.minutes > MAX_MINUTES_PER_ENTRY:
			frappe.throw(_("A single entry can't be more than 24 hours"))
		if getdate(self.log_date) > getdate(today()):
			frappe.throw(_("You can't log time for a future date"))
		if self.task and frappe.db.get_value("Task", self.task, "project") != self.project:
			frappe.throw(_("Task {0} is not part of this project").format(self.task))
		self.description = (self.description or "").strip()


def on_doctype_update():
	frappe.db.add_index("AS Time Log", ["user", "log_date"])
	frappe.db.add_index("AS Time Log", ["project", "log_date"])
