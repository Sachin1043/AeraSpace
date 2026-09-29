import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from aeraspace.messages import (
	MESSAGE_FIELDS,
	add_thread_follower,
	build_payloads,
	publish_message_update,
)
from aeraspace.notifications import notify_invite
from aeraspace.utils import (
	add_member,
	check_member,
	check_read,
	get_member,
	notify_sidebar_change,
	publish_to_channel,
	require_login,
)

PAGE_SIZE = 50
REACTION_MAX_LENGTH = 16


@frappe.whitelist()
def get_sidebar():
	"""Channels, groups and DMs the current user belongs to, with unread counts (thread replies excluded)."""
	user = require_login()
	channels = frappe.db.sql(
		"""
		select
			c.name, c.channel_name, c.channel_type, c.description, c.project,
			c.last_message_at, c.last_message_preview,
			m.role, m.last_read_at, m.notify,
			(
				select count(*) from `tabAS Message` msg
				where msg.channel = c.name
					and coalesce(msg.thread_root, '') = ''
					and msg.sender != %(user)s
					and msg.creation > coalesce(m.last_read_at, '1970-01-01')
			) as unread
		from `tabAS Channel Member` m
		join `tabAS Channel` c on c.name = m.channel
		where m.user = %(user)s and c.is_archived = 0
		order by coalesce(c.last_message_at, c.creation) desc
		""",
		{"user": user},
		as_dict=True,
	)

	conversations = [c.name for c in channels if c.channel_type in ("Direct", "Group")]
	members = {}
	if conversations:
		for row in frappe.get_all(
			"AS Channel Member",
			filters={"channel": ("in", conversations)},
			fields=["channel", "user"],
			order_by="creation asc",
		):
			members.setdefault(row.channel, []).append(row.user)

	for channel in channels:
		channel.members = members.get(channel.name, [])
	return channels


@frappe.whitelist()
def get_channel(channel: str):
	doc = check_read(channel)
	member = get_member(channel)
	doc.members = frappe.get_all(
		"AS Channel Member",
		filters={"channel": channel},
		fields=["user", "role"],
		order_by="creation asc",
	)
	doc.is_member = bool(member)
	doc.my_role = member.role if member else None
	doc.pinned_count = frappe.db.count("AS Message", {"channel": channel, "is_pinned": 1, "is_deleted": 0})
	return doc


@frappe.whitelist()
def get_messages(channel: str, before: str | None = None, limit: int = PAGE_SIZE):
	"""Top-level messages of a channel, newest page first (thread replies live in get_thread)."""
	check_read(channel)
	limit = min(cint(limit) or PAGE_SIZE, 100)

	filters = {"channel": channel, "thread_root": ("is", "not set")}
	if before:
		filters["creation"] = ("<", get_datetime(before))

	# fetch one extra row to know whether older messages exist
	rows = frappe.get_all(
		"AS Message",
		filters=filters,
		fields=MESSAGE_FIELDS,
		order_by="creation desc",
		limit=limit + 1,
	)
	has_more = len(rows) > limit
	rows = rows[:limit]
	rows.reverse()
	return {"messages": build_payloads(rows), "has_more": has_more}


@frappe.whitelist()
def get_thread(thread_root: str):
	root = frappe.db.get_value("AS Message", thread_root, MESSAGE_FIELDS, as_dict=True)
	if not root or root.thread_root:
		frappe.throw(_("Thread not found"), frappe.DoesNotExistError)
	check_read(root.channel)

	replies = frappe.get_all(
		"AS Message",
		filters={"thread_root": thread_root},
		fields=MESSAGE_FIELDS,
		order_by="creation asc",
	)
	following = frappe.db.exists(
		"AS Thread Follower", {"thread_root": thread_root, "user": frappe.session.user}
	)
	return {
		"root": build_payloads([root])[0],
		"replies": build_payloads(replies),
		"is_following": bool(following),
	}


@frappe.whitelist(methods=["POST"])
def send_message(
	channel: str,
	content: str | None = None,
	client_id: str | None = None,
	files=None,
	thread_root: str | None = None,
	reply_to: str | None = None,
):
	user = require_login()
	doc = check_member(channel)
	if doc.channel_type == "Announcement" and not thread_root and doc.my_role != "Admin":
		frappe.throw(
			_("Only admins can post in #{0}. You can reply in threads.").format(doc.channel_name),
			frappe.PermissionError,
		)

	message = frappe.get_doc(
		{
			"doctype": "AS Message",
			"channel": channel,
			"sender": user,
			"content": content,
			"files": frappe.as_json(_validate_uploaded_files(channel, files)) if files else None,
			"thread_root": thread_root or None,
			"reply_to": reply_to or None,
		}
	)
	message.flags.client_id = client_id
	message.insert(ignore_permissions=True)
	if not message.thread_root:
		_set_last_read(channel, user, message.creation)
	return message.as_payload()


@frappe.whitelist(methods=["POST"])
def edit_message(message: str, content: str):
	doc = _get_own_message(message)
	if not (content or "").strip():
		frappe.throw(_("Message cannot be empty. Delete it instead."))
	doc.content = content
	doc.is_edited = 1
	doc.save(ignore_permissions=True)
	return publish_message_update(message)


@frappe.whitelist(methods=["POST"])
def delete_message(message: str):
	user = require_login()
	doc = frappe.get_doc("AS Message", message)
	member = get_member(doc.channel)
	if doc.message_type == "System" or not (doc.sender == user or (member and member.role == "Admin")):
		frappe.throw(_("You can only delete your own messages"), frappe.PermissionError)

	for file in doc.get_files():
		if frappe.db.exists("File", file.get("name")):
			frappe.delete_doc("File", file["name"], ignore_permissions=True)

	doc.db_set({"is_deleted": 1, "content": "", "files": None, "is_pinned": 0}, update_modified=False)
	frappe.db.delete("AS Message Reaction", {"message": message})
	frappe.db.delete("AS Bookmark", {"message": message})
	return publish_message_update(message)


@frappe.whitelist(methods=["POST"])
def toggle_reaction(message: str, emoji: str):
	user = require_login()
	emoji = (emoji or "").strip()
	if not emoji or len(emoji) > REACTION_MAX_LENGTH:
		frappe.throw(_("Invalid reaction"))
	doc = _get_live_message(message)
	check_member(doc.channel)

	existing = frappe.db.exists("AS Message Reaction", {"message": message, "user": user, "emoji": emoji})
	if existing:
		frappe.delete_doc("AS Message Reaction", existing, ignore_permissions=True)
	else:
		frappe.get_doc(
			{"doctype": "AS Message Reaction", "message": message, "user": user, "emoji": emoji}
		).insert(ignore_permissions=True)
	return publish_message_update(message)


@frappe.whitelist(methods=["POST"])
def toggle_pin(message: str):
	user = require_login()
	doc = _get_live_message(message)
	check_member(doc.channel)
	if doc.thread_root:
		frappe.throw(_("Only top-level messages can be pinned"))
	pinned = not doc.is_pinned
	doc.db_set({"is_pinned": pinned, "pinned_by": user if pinned else None}, update_modified=False)
	return publish_message_update(message)


@frappe.whitelist()
def get_pinned(channel: str):
	check_read(channel)
	rows = frappe.get_all(
		"AS Message",
		filters={"channel": channel, "is_pinned": 1, "is_deleted": 0},
		fields=MESSAGE_FIELDS,
		order_by="creation desc",
	)
	return build_payloads(rows)


@frappe.whitelist(methods=["POST"])
def toggle_bookmark(message: str):
	user = require_login()
	doc = _get_live_message(message)
	check_read(doc.channel)
	existing = frappe.db.exists("AS Bookmark", {"user": user, "message": message})
	if existing:
		frappe.delete_doc("AS Bookmark", existing, ignore_permissions=True)
		return False
	frappe.get_doc({"doctype": "AS Bookmark", "user": user, "message": message}).insert(
		ignore_permissions=True
	)
	return True


@frappe.whitelist()
def get_bookmarks():
	"""Saved messages the user can still read, newest save first."""
	user = require_login()
	saved = frappe.get_all(
		"AS Bookmark", filters={"user": user}, fields=["message", "creation"], order_by="creation desc"
	)
	if not saved:
		return []

	rows = {
		row.name: row
		for row in frappe.get_all(
			"AS Message", filters={"name": ("in", [s.message for s in saved])}, fields=MESSAGE_FIELDS
		)
	}
	channels = {}
	result = []
	for bookmark in saved:
		row = rows.get(bookmark.message)
		if not row or row.is_deleted:
			continue
		if row.channel not in channels:
			try:
				channels[row.channel] = check_read(row.channel)
			except frappe.PermissionError:
				channels[row.channel] = None
				frappe.clear_last_message()
		if channels[row.channel]:
			payload = build_payloads([row])[0]
			payload["channel_name"] = channels[row.channel].channel_name
			payload["channel_type"] = channels[row.channel].channel_type
			payload["saved_on"] = str(bookmark.creation)
			result.append(payload)
	return result


@frappe.whitelist()
def get_bookmarked_ids():
	return frappe.get_all("AS Bookmark", filters={"user": require_login()}, pluck="message")


@frappe.whitelist(methods=["POST"])
def toggle_follow(thread_root: str):
	user = require_login()
	doc = _get_live_message(thread_root)
	check_read(doc.channel)
	existing = frappe.db.exists("AS Thread Follower", {"thread_root": thread_root, "user": user})
	if existing:
		frappe.delete_doc("AS Thread Follower", existing, ignore_permissions=True)
		return False
	add_thread_follower(thread_root, user)
	return True


@frappe.whitelist(methods=["POST"])
def mark_read(channel: str):
	user = require_login()
	if get_member(channel):
		_set_last_read(channel, user, now_datetime())


@frappe.whitelist(methods=["POST"])
def typing(channel: str, thread_root: str | None = None):
	user = require_login()
	check_member(channel)
	publish_to_channel(
		channel,
		"as_typing",
		{"channel": channel, "thread_root": thread_root, "user": user},
		after_commit=False,
		exclude=user,
	)


@frappe.whitelist(methods=["POST"])
def get_or_create_dm(user: str):
	me = require_login()
	if not frappe.db.exists("User", {"name": user, "enabled": 1}):
		frappe.throw(_("User not found"), frappe.DoesNotExistError)

	dm_key = "::".join(sorted({me, user}))
	existing = frappe.db.get_value("AS Channel", {"dm_key": dm_key}, "name")
	if existing:
		return existing

	channel = frappe.get_doc({"doctype": "AS Channel", "channel_type": "Direct", "dm_key": dm_key}).insert(
		ignore_permissions=True
	)
	for member in {me, user}:
		add_member(channel.name, member)
	notify_sidebar_change([me, user])
	return channel.name


@frappe.whitelist(methods=["POST"])
def create_group(users, channel_name: str | None = None):
	me = require_login()
	users = frappe.parse_json(users) if isinstance(users, str) else users
	users = {u for u in (users or []) if u and u != me}
	if not users:
		frappe.throw(_("Pick at least one person"))
	if len(users) == 1:
		return get_or_create_dm(users.pop())

	channel = frappe.get_doc(
		{
			"doctype": "AS Channel",
			"channel_type": "Group",
			"channel_name": (channel_name or "").strip() or None,
		}
	).insert(ignore_permissions=True)
	add_member(channel.name, me, role="Admin")
	for user in users:
		add_member(channel.name, user)
	notify_sidebar_change([me, *users])
	notify_invite(channel.name, users)
	return channel.name


def _get_live_message(message: str):
	doc = frappe.get_doc("AS Message", message)
	if doc.is_deleted:
		frappe.throw(_("This message was deleted"))
	return doc


def _get_own_message(message: str):
	doc = _get_live_message(message)
	if doc.sender != require_login() or doc.message_type == "System":
		frappe.throw(_("You can only edit your own messages"), frappe.PermissionError)
	return doc


def _validate_uploaded_files(channel: str, files) -> list[dict]:
	"""Files must have been uploaded to this channel by the sender (see api.files.upload)."""
	names = frappe.parse_json(files) if isinstance(files, str) else files
	result = []
	for name in names or []:
		file = frappe.db.get_value(
			"File",
			name,
			[
				"name",
				"file_name",
				"file_url",
				"file_size",
				"owner",
				"attached_to_doctype",
				"attached_to_name",
			],
			as_dict=True,
		)
		if (
			not file
			or file.owner != frappe.session.user
			or file.attached_to_doctype != "AS Channel"
			or file.attached_to_name != channel
		):
			frappe.throw(_("Attachment {0} is not available").format(name))
		result.append(
			{
				"name": file.name,
				"file_name": file.file_name,
				"file_url": file.file_url,
				"file_size": file.file_size,
			}
		)
	return result


def _set_last_read(channel: str, user: str, timestamp):
	frappe.db.set_value(
		"AS Channel Member",
		{"channel": channel, "user": user},
		"last_read_at",
		timestamp,
		update_modified=False,
	)
