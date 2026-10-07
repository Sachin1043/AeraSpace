"""Who gets told about what.

Activity rows (AS Notification) are stored for mentions, thread replies and invites.
Every notification — including plain messages in "All" conversations — is also pushed
live as `as_notify` so the browser can show a desktop popup.
"""

import re

import frappe
from frappe import _
from frappe.utils import get_fullname

MENTION_PATTERN = re.compile(r"<@([^>\s]+)>")
CHANNEL_WIDE = "<!channel>"
PREVIEW_LENGTH = 200
CONVERSATION_TYPES = ("Direct", "Group")


def effective_level(notify: str | None, channel_type: str) -> str:
	if notify and notify != "Default":
		return notify
	return "All" if channel_type in CONVERSATION_TYPES else "Mentions"


def mentioned_users(content: str | None) -> set[str]:
	return set(MENTION_PATTERN.findall(content or ""))


MARKDOWN_CLEANUP = (
	(re.compile(r"```[a-z]*\n?", re.I), ""),
	(re.compile(r"`([^`]*)`"), r"\1"),
	(re.compile(r"(\*\*|__)(.+?)\1"), r"\2"),
	(re.compile(r"~~(.+?)~~"), r"\1"),
	(re.compile(r"^\s*(#{1,6}|>)\s+", re.M), ""),
	(re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),
	(re.compile(r"\s+"), " "),
)


def plain_preview(content: str | None, files=None) -> str:
	text = MENTION_PATTERN.sub(lambda m: "@" + get_fullname(m.group(1)), content or "")
	text = text.replace(CHANNEL_WIDE, "@channel")
	for pattern, replacement in MARKDOWN_CLEANUP:
		text = pattern.sub(replacement, text)
	text = text.strip()
	if not text and files:
		text = _("📎 {0} file(s)").format(len(files))
	return text[:PREVIEW_LENGTH]


def notify_new_message(message):
	if message.message_type == "System":
		return

	channel = frappe.db.get_value(
		"AS Channel", message.channel, ["channel_type", "channel_name"], as_dict=True
	)
	members = dict(
		frappe.get_all(
			"AS Channel Member", filters={"channel": message.channel}, fields=["user", "notify"], as_list=True
		)
	)
	mentioned = mentioned_users(message.content)
	everyone = CHANNEL_WIDE in (message.content or "")
	followers = (
		set(frappe.get_all("AS Thread Follower", filters={"thread_root": message.thread_root}, pluck="user"))
		if message.thread_root
		else set()
	)
	preview = plain_preview(message.content, message.get_files())

	for user, notify in members.items():
		if user == message.sender:
			continue
		level = effective_level(notify, channel.channel_type)
		if level == "Nothing":
			continue

		if user in mentioned or everyone:
			kind = "Mention"
		elif message.thread_root:
			if user not in followers:
				continue
			kind = "Thread Reply"
		elif level == "All":
			kind = "Message"  # popup only; unread badges already cover it
		else:
			continue

		push(
			user,
			kind,
			from_user=message.sender,
			channel=message.channel,
			message=message.name,
			thread_root=message.thread_root,
			preview=preview,
			store=kind != "Message",
		)


def notify_invite(channel: str, users, by: str | None = None):
	by = by or frappe.session.user
	channel_type = frappe.db.get_value("AS Channel", channel, "channel_type")
	for user in set(users):
		if user == by:
			continue
		push(
			user,
			"Invite",
			from_user=by,
			channel=channel,
			preview=_("added you to a group conversation")
			if channel_type == "Group"
			else _("added you to the channel"),
		)


def push(
	user,
	kind,
	from_user=None,
	channel=None,
	message=None,
	thread_root=None,
	preview=None,
	store=True,
	task=None,
):
	payload = {
		"notification_type": kind,
		"from_user": from_user,
		"channel": channel,
		"message": message,
		"thread_root": thread_root,
		"task": task,
		"preview": preview,
	}
	if store:
		doc = frappe.get_doc({"doctype": "AS Notification", "user": user, **payload}).insert(
			ignore_permissions=True
		)
		payload["name"] = doc.name
	if task:
		payload["project"] = frappe.db.get_value("Task", task, "project")
	frappe.publish_realtime("as_notify", payload, user=user, after_commit=True)
