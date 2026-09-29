import frappe
from frappe import _
from frappe.utils import get_fullname

from aeraspace.notifications import notify_invite
from aeraspace.utils import (
	add_member,
	check_channel_admin,
	check_member,
	get_channel_or_throw,
	get_member,
	get_member_users,
	notify_sidebar_change,
	post_system_message,
	require_login,
)


@frappe.whitelist(methods=["POST"])
def create_channel(
	channel_name: str, channel_type: str = "Public", description: str | None = None, members=None
):
	me = require_login()
	if channel_type not in ("Public", "Private", "Announcement"):
		frappe.throw(_("Channel type must be Public, Private or Announcement"))

	channel = frappe.get_doc(
		{
			"doctype": "AS Channel",
			"channel_name": channel_name,
			"channel_type": channel_type,
			"description": description,
		}
	).insert(ignore_permissions=True)

	members = frappe.parse_json(members) if isinstance(members, str) else (members or [])
	add_member(channel.name, me, role="Admin")
	for user in members:
		if user != me and frappe.db.exists("User", {"name": user, "enabled": 1}):
			add_member(channel.name, user)

	post_system_message(channel.name, _("{0} created #{1}").format(get_fullname(me), channel.channel_name))
	notify_sidebar_change([me, *members])
	notify_invite(channel.name, [u for u in members if u != me])
	return channel.name


@frappe.whitelist()
def browse_channels(search: str | None = None):
	"""Open channels anyone can join, plus private channels the user already belongs to."""
	me = require_login()
	filters = {"channel_type": ("in", ("Public", "Private", "Announcement")), "is_archived": 0}
	if search:
		filters["channel_name"] = ("like", f"%{search.strip().lstrip('#')}%")

	channels = frappe.get_all(
		"AS Channel",
		filters=filters,
		fields=["name", "channel_name", "channel_type", "description", "creation"],
		order_by="channel_name asc",
	)
	if not channels:
		return []

	names = [c.name for c in channels]
	counts = dict(
		frappe.db.sql(
			"""select channel, count(*) from `tabAS Channel Member`
			where channel in %(names)s group by channel""",
			{"names": names},
		)
	)
	mine = set(
		frappe.get_all("AS Channel Member", filters={"channel": ("in", names), "user": me}, pluck="channel")
	)

	result = []
	for channel in channels:
		channel.is_member = channel.name in mine
		if channel.channel_type == "Private" and not channel.is_member:
			continue
		channel.member_count = counts.get(channel.name, 0)
		result.append(channel)
	return result


@frappe.whitelist(methods=["POST"])
def join_channel(channel: str):
	me = require_login()
	doc = get_channel_or_throw(channel)
	if doc.channel_type not in ("Public", "Announcement"):
		frappe.throw(_("Only public channels can be joined"), frappe.PermissionError)
	if not get_member(channel):
		add_member(channel, me)
		post_system_message(channel, _("{0} joined").format(get_fullname(me)))
		notify_sidebar_change([me])


@frappe.whitelist(methods=["POST"])
def leave_channel(channel: str):
	me = require_login()
	doc = check_member(channel)
	if doc.channel_type == "Direct":
		frappe.throw(_("You can't leave a direct conversation"))

	post_system_message(channel, _("{0} left").format(get_fullname(me)))
	frappe.db.delete("AS Channel Member", {"channel": channel, "user": me})
	notify_sidebar_change([me])


@frappe.whitelist(methods=["POST"])
def add_members(channel: str, users):
	me = require_login()
	doc = check_member(channel)
	if doc.channel_type == "Direct":
		frappe.throw(_("Start a group conversation to add more people"))

	users = frappe.parse_json(users) if isinstance(users, str) else (users or [])
	existing = set(get_member_users(channel))
	added = [u for u in users if u not in existing and frappe.db.exists("User", {"name": u, "enabled": 1})]
	for user in added:
		add_member(channel, user)

	if added:
		names = ", ".join(get_fullname(u) for u in added)
		post_system_message(channel, _("{0} added {1}").format(get_fullname(me), names))
		notify_sidebar_change(added)
		notify_invite(channel, added)
	return added


@frappe.whitelist(methods=["POST"])
def update_channel(channel: str, description: str | None = None):
	check_member(channel)
	frappe.db.set_value("AS Channel", channel, "description", (description or "").strip())


@frappe.whitelist(methods=["POST"])
def set_member_role(channel: str, user: str, role: str):
	check_channel_admin(channel)
	if role not in ("Admin", "Member"):
		frappe.throw(_("Invalid role"))
	member = frappe.db.get_value("AS Channel Member", {"channel": channel, "user": user}, "name")
	if not member:
		frappe.throw(_("{0} is not a member of this channel").format(user))
	if role == "Member" and frappe.db.count("AS Channel Member", {"channel": channel, "role": "Admin"}) <= 1:
		frappe.throw(_("A channel needs at least one admin"))
	frappe.db.set_value("AS Channel Member", member, "role", role)
