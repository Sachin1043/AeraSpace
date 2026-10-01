"""Who can see whose EOD updates and time logs."""

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
