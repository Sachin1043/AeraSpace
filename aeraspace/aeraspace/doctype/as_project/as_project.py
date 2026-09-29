# Copyright (c) 2026, Aerele and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class ASProject(Document):
	def validate(self):
		self.project_name = (self.project_name or "").strip()
		self.project_key = (self.project_key or "").strip().upper()
		if not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", self.project_key):
			frappe.throw(_("Project key must be 2-8 letters or digits and start with a letter, e.g. SHOP"))


def suggest_key(project_name: str) -> str:
	"""SHOPIFY INTEGRATION -> SI, Shopify -> SHOP; never collides with an existing key."""
	words = re.findall(r"[A-Za-z0-9]+", project_name or "")
	base = (
		"".join(w[0] for w in words).upper() if len(words) > 1 else (words[0][:4].upper() if words else "PRJ")
	)
	if not base[:1].isalpha():
		base = "P" + base
	base = (base + "X")[: max(2, len(base))][:6]
	key, n = base, 2
	while frappe.db.exists("AS Project", key):
		key, n = f"{base}{n}", n + 1
	return key
