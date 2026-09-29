"""Row-level access for AS Channel: members (and everyone, for open channels) may read; nobody writes via REST."""

import frappe

OPEN_TYPES = ("Public", "Announcement")


def is_admin(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def channel_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype not in ("read", "select", "print"):
		return False
	if doc.channel_type in OPEN_TYPES:
		return True
	return bool(frappe.db.exists("AS Channel Member", {"channel": doc.name, "user": user}))


def channel_query_conditions(user=None):
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return (
		f"(`tabAS Channel`.channel_type in ('Public', 'Announcement') or `tabAS Channel`.name in "
		f"(select channel from `tabAS Channel Member` where user = {frappe.db.escape(user)}))"
	)
