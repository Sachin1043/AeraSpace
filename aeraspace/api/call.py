"""Audio/video calls inside a channel.

Audio and video go straight from browser to browser (WebRTC). The server only remembers who is in a call
(in Redis, refreshed by a ping while the call is open) and relays the connection offers and answers
between participants over socket.io. AS Call keeps the history: who started it, who joined, how long.
"""

import json
import time

import frappe
from frappe import _
from frappe.utils import format_duration, get_fullname, now_datetime, time_diff_in_seconds

from aeraspace.utils import check_member, get_member_users, post_system_message, require_login

MAX_PARTICIPANTS = 6  # every browser sends its video to every other one, so keep calls small
STALE_AFTER_SECONDS = 45  # clients ping every 15s while they are in a call
RING_UP_TO_MEMBERS = 8  # bigger channels get a quiet "call started" notice instead of ringing


def _key(call: str) -> str:
	return f"aeraspace_call:{call}"


def _touch(call: str, user: str):
	frappe.cache.hset(_key(call), user, time.time())


def _live(call: str) -> list[str]:
	"""Users currently in the call; anyone who stopped pinging is dropped."""
	now, users = time.time(), []
	for key, seen in (frappe.cache.hgetall(_key(call)) or {}).items():
		user = frappe.safe_decode(key)
		if now - float(seen) <= STALE_AFTER_SECONDS:
			users.append(user)
		else:
			frappe.cache.hdel(_key(call), user)
	return sorted(users)


def _payload(doc) -> dict:
	channel = frappe.db.get_value("AS Channel", doc.channel, ["channel_name", "channel_type"], as_dict=True)
	return {
		"name": doc.name,
		"channel": doc.channel,
		"channel_name": channel.channel_name,
		"channel_type": channel.channel_type,
		"call_type": doc.call_type,
		"status": doc.status,
		"started_by": doc.started_by,
		"started_by_name": get_fullname(doc.started_by),
		"started_at": str(doc.started_at),
		"participants": _live(doc.name) if doc.status == "Active" else [],
	}


def _publish(doc, action: str, **extra):
	message = {"action": action, "call": _payload(doc), **extra}
	for user in get_member_users(doc.channel):
		frappe.publish_realtime("as_call", message, user=user, after_commit=True)


def _active_call(channel: str, end_stale: bool = True):
	name = frappe.db.get_value("AS Call", {"channel": channel, "status": "Active"}, "name")
	if not name:
		return None
	doc = frappe.get_doc("AS Call", name)
	if not _live(name):  # everyone's browser went away without hanging up
		if end_stale:
			_end(doc)
		return None
	return doc


def _call_for(call: str):
	doc = frappe.get_doc("AS Call", call)
	check_member(doc.channel)
	return doc


def _end(doc):
	# lock the row so two people hanging up at once end it only once
	if frappe.db.get_value("AS Call", doc.name, "status", for_update=True) != "Active":
		return
	joined = [u for u in (doc.participants or "").splitlines() if u]
	missed = joined == [doc.started_by]
	doc.status = "Missed" if missed else "Ended"
	doc.ended_at = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.cache.delete_value(_key(doc.name))

	kind = _("video") if doc.call_type == "Video" else _("audio")
	if missed:
		content = _("Missed {0} call from {1}").format(kind, get_fullname(doc.started_by))
	else:
		seconds = max(1, int(time_diff_in_seconds(doc.ended_at, doc.started_at)))
		content = _("{0} call ended · {1}").format(kind.capitalize(), format_duration(seconds))
	post_system_message(doc.channel, content)
	_publish(doc, "end")


def _add_participant(doc, user: str):
	_touch(doc.name, user)
	joined = [u for u in (doc.participants or "").splitlines() if u]
	if user not in joined:
		doc.db_set("participants", "\n".join([*joined, user]), update_modified=False)


@frappe.whitelist(methods=["POST"])
def start_call(channel: str, call_type: str = "Video"):
	"""Start a call in the channel, or join the one already running there."""
	user = require_login()
	check_member(channel)
	existing = _active_call(channel)
	if existing:
		return join_call(existing.name)

	doc = frappe.get_doc(
		{
			"doctype": "AS Call",
			"channel": channel,
			"call_type": "Audio" if call_type == "Audio" else "Video",
			"status": "Active",
			"started_by": user,
			"started_at": now_datetime(),
			"participants": user,
		}
	).insert(ignore_permissions=True)
	_touch(doc.name, user)
	kind = _("a video") if doc.call_type == "Video" else _("an audio")
	post_system_message(channel, _("{0} started {1} call").format(get_fullname(user), kind))
	ring = len(get_member_users(channel)) <= RING_UP_TO_MEMBERS
	_publish(doc, "start", ring=ring)
	return _payload(doc)


@frappe.whitelist(methods=["POST"])
def join_call(call: str):
	user = require_login()
	doc = _call_for(call)
	if doc.status != "Active":
		frappe.throw(_("This call has already ended"))
	live = _live(doc.name)
	if user not in live and len(live) >= MAX_PARTICIPANTS:
		frappe.throw(_("This call is full ({0} people)").format(MAX_PARTICIPANTS))
	_add_participant(doc, user)
	_publish(doc, "update")
	return _payload(doc)


@frappe.whitelist(methods=["POST"])
def leave_call(call: str):
	user = require_login()
	doc = _call_for(call)
	frappe.cache.hdel(_key(doc.name), user)
	if doc.status != "Active":
		return
	if _live(doc.name):
		_publish(doc, "update", left=user)
	else:
		_end(doc)


@frappe.whitelist(methods=["POST"])
def decline_call(call: str):
	user = require_login()
	doc = _call_for(call)
	if doc.status != "Active":
		return
	message = {"action": "declined", "call": _payload(doc), "user": user}
	for participant in _live(doc.name):
		frappe.publish_realtime("as_call", message, user=participant, after_commit=True)


@frappe.whitelist(methods=["POST"])
def ping(call: str):
	"""Keeps the user in the call; returns who else is still there."""
	user = require_login()
	if user in _live(call):
		_touch(call, user)
	return _live(call)


@frappe.whitelist(methods=["POST"])
def signal(call: str, to: str, data: str):
	"""Pass a WebRTC offer/answer/state message to another participant."""
	user = require_login()
	live = _live(call)
	if user not in live or to not in live:
		frappe.throw(_("That person is no longer in the call"))
	payload = json.loads(data) if isinstance(data, str) else data
	frappe.publish_realtime("as_call_signal", {"call": call, "from": user, "data": payload}, user=to)


@frappe.whitelist()
def get_active_call(channel: str):
	require_login()
	check_member(channel)
	doc = _active_call(channel, end_stale=False)  # GET requests don't save changes
	return _payload(doc) if doc else None
