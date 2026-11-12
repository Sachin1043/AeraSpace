# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ASMeeting(Document):
	pass


def on_doctype_update():
	frappe.db.add_index("AS Meeting", ["status", "starts_at"])
