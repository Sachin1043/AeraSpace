# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ASNotification(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("AS Notification", ["user", "is_read", "creation"])
