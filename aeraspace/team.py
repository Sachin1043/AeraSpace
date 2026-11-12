"""Who can see whose EOD updates, time logs and attendance."""

import frappe

from aeraspace.permissions import is_admin
from aeraspace.utils import get_active_users


def reportees(user: str) -> list[str]:
	return frappe.get_all("AS Employee Profile", filters={"manager": user}, pluck="user")


def team_scope(user: str) -> tuple[list[str], bool]:
	"""(people whose updates/time the user may see, whether that is everyone)."""
	if is_admin(user):
		return get_active_users(), True
	return [user, *reportees(user)], False


def can_view(viewer: str, target: str) -> bool:
	return viewer == target or is_admin(viewer) or target in reportees(viewer)


def watchers(user: str) -> list[str]:
	"""Who sees this person on their team dashboard: their manager and the admins."""
	admins = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": "System Manager"}, pluck="parent"
	)
	manager = frappe.db.get_value("AS Employee Profile", user, "manager")
	return sorted({*admins, "Administrator", *([manager] if manager else [])} - {user, "Guest"})
