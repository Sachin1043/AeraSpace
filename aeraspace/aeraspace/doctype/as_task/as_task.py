# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

STATUSES = ("Backlog", "Todo", "In Progress", "Code Review", "Testing", "Done")


class ASTask(Document):
	def autoname(self):
		# lock the project row so two people creating tasks at once never get the same number
		key, last = frappe.db.sql(
			"select project_key, last_task_number from `tabAS Project` where name = %s for update",
			self.project,
		)[0]
		number = (last or 0) + 1
		frappe.db.set_value("AS Project", self.project, "last_task_number", number, update_modified=False)
		self.name = f"{key}-{number}"

	def validate(self):
		self.title = (self.title or "").strip()
		if not self.title:
			frappe.throw(_("Task title is required"))
		if self.status not in STATUSES:
			frappe.throw(_("Invalid status"))
		if self.status == "Done" and not self.completed_on:
			self.completed_on = now_datetime()
		elif self.status != "Done":
			self.completed_on = None
		if self.labels:
			self.labels = ", ".join(dict.fromkeys(l.strip() for l in self.labels.split(",") if l.strip()))

	def get_files(self):
		return frappe.parse_json(self.files) if self.files else []


def on_doctype_update():
	frappe.db.add_index("AS Task", ["project", "status", "sort_order"])
