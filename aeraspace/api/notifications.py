import frappe
from frappe import _
from frappe.utils import cint

from aeraspace.utils import check_member, require_login

LEVELS = ("Default", "All", "Mentions", "Nothing")


@frappe.whitelist()
def get_notifications(limit: int = 50):
	user = require_login()
	rows = frappe.get_all(
		"AS Notification",
		filters={"user": user},
		fields=[
			"name",
			"notification_type",
			"from_user",
			"channel",
			"message",
			"thread_root",
			"task",
			"preview",
			"is_read",
			"creation",
		],
		order_by="creation desc",
		limit=min(cint(limit) or 50, 200),
	)
	channels = (
		{
			c.name: c
			for c in frappe.get_all(
				"AS Channel",
				filters={"name": ("in", list({r.channel for r in rows if r.channel}))},
				fields=["name", "channel_name", "channel_type"],
			)
		}
		if rows
		else {}
	)
	projects = dict(
		frappe.get_all(
			"Task",
			filters={"name": ("in", [r.task for r in rows if r.task] or [""])},
			fields=["name", "project"],
			as_list=True,
		)
	)
	for row in rows:
		row.creation = str(row.creation)
		row.project = projects.get(row.task)
		channel = channels.get(row.channel)
		row.channel_name = channel.channel_name if channel else None
		row.channel_type = channel.channel_type if channel else None
	return rows


@frappe.whitelist()
def get_unread_count():
	return frappe.db.count("AS Notification", {"user": require_login(), "is_read": 0})


@frappe.whitelist(methods=["POST"])
def mark_notifications_read(names=None):
	"""Mark the given notifications (or all of them) as read for the current user."""
	user = require_login()
	filters = {"user": user, "is_read": 0}
	if names:
		filters["name"] = ("in", frappe.parse_json(names) if isinstance(names, str) else names)
	frappe.db.set_value("AS Notification", filters, "is_read", 1, update_modified=False)
	return get_unread_count()


@frappe.whitelist(methods=["POST"])
def set_channel_notify(channel: str, level: str):
	user = require_login()
	check_member(channel)
	if level not in LEVELS:
		frappe.throw(_("Invalid notification level"))
	frappe.db.set_value("AS Channel Member", {"channel": channel, "user": user}, "notify", level)
	return level
