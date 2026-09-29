import frappe
from frappe import _


def require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use AeraSpace"), frappe.AuthenticationError)
	return frappe.session.user


def get_member(channel: str, user: str | None = None):
	return frappe.db.get_value(
		"AS Channel Member",
		{"channel": channel, "user": user or frappe.session.user},
		["name", "role", "last_read_at"],
		as_dict=True,
	)


def get_member_users(channel: str) -> list[str]:
	return frappe.get_all("AS Channel Member", filters={"channel": channel}, pluck="user")


def get_channel_or_throw(channel: str):
	doc = frappe.db.get_value(
		"AS Channel",
		channel,
		[
			"name",
			"channel_name",
			"channel_type",
			"description",
			"is_archived",
			"owner",
			"creation",
			"project",
		],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("Channel not found"), frappe.DoesNotExistError)
	return doc


OPEN_TYPES = ("Public", "Announcement")


def can_read(channel) -> bool:
	"""Open (public/announcement) channels are readable by everyone; everything else needs membership."""
	return channel.channel_type in OPEN_TYPES or bool(get_member(channel.name))


def check_read(channel: str):
	doc = get_channel_or_throw(channel)
	if not can_read(doc):
		frappe.throw(_("You don't have access to this channel"), frappe.PermissionError)
	return doc


def check_member(channel: str):
	doc = get_channel_or_throw(channel)
	member = get_member(channel)
	if not member:
		frappe.throw(_("Join this channel to take part"), frappe.PermissionError)
	doc.my_role = member.role
	return doc


def check_channel_admin(channel: str):
	doc = check_member(channel)
	if doc.my_role != "Admin":
		frappe.throw(_("Only channel admins can do this"), frappe.PermissionError)
	return doc


def add_member(channel: str, user: str, role: str = "Member"):
	if get_member(channel, user):
		return
	frappe.get_doc({"doctype": "AS Channel Member", "channel": channel, "user": user, "role": role}).insert(
		ignore_permissions=True
	)


def post_system_message(channel: str, content: str):
	frappe.get_doc(
		{
			"doctype": "AS Message",
			"channel": channel,
			"sender": frappe.session.user,
			"message_type": "System",
			"content": content,
		}
	).insert(ignore_permissions=True)


def publish_to_channel(channel: str, event: str, message: dict, after_commit: bool = True, exclude=None):
	"""Open channels broadcast to all desk users; other channels only reach their members."""
	channel_type = frappe.db.get_value("AS Channel", channel, "channel_type")
	if channel_type in OPEN_TYPES and not exclude:
		frappe.publish_realtime(event, message, after_commit=after_commit)
		return

	for user in get_member_users(channel):
		if user != exclude:
			frappe.publish_realtime(event, message, user=user, after_commit=after_commit)


def notify_sidebar_change(users: list[str]):
	for user in set(users):
		frappe.publish_realtime("as_sidebar_update", {}, user=user, after_commit=True)


def get_active_users() -> list[str]:
	return frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ("not in", ("Guest",))},
		pluck="name",
	)
