# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class ASSettings(Document):
	def validate(self):
		days = [d.strip().title()[:3] for d in (self.working_days or "").split(",") if d.strip()]
		invalid = [d for d in days if d not in DAYS]
		if invalid or not days:
			frappe.throw(_("Working days must be a comma separated list of: {0}").format(", ".join(DAYS)))
		self.working_days = ",".join(d for d in DAYS if d in days)


def get_settings():
	return frappe.get_cached_doc("AS Settings")


def is_working_day(date) -> bool:
	return DAYS[date.weekday()] in (get_settings().working_days or "Mon,Tue,Wed,Thu,Fri").split(",")
