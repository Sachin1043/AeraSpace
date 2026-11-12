"""Scheduled meetings: a time, a list of people and a place to talk.

A meeting lives in a conversation: a channel the host picks, or a new group made of the invitees (a direct
chat when there is only one). Joining is just a call in that conversation (see api/call.py), so the
meeting chat, files and call history all stay together. The browser pops a reminder 5 minutes before;
`send_reminders` also adds it to Activity when the scheduler is running.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	format_datetime,
	get_datetime,
	get_fullname,
	now_datetime,
)

from aeraspace.api.chat import get_or_create_dm
from aeraspace.notifications import push
from aeraspace.utils import (
	add_member,
	check_member,
	get_member_users,
	notify_sidebar_change,
	post_system_message,
	require_login,
)

DURATIONS = (15, 30, 45, 60, 90, 120)
REMINDER_MINUTES = 5


def _when(doc) -> str:
	return format_datetime(doc.starts_at, "EEE d MMM, h:mm a")


def _people(doc) -> list[str]:
	return [doc.host, *[i.user for i in doc.invitees]]


def _payload(doc, viewer: str) -> dict:
	starts = get_datetime(doc.starts_at)
	ends = starts + timedelta(minutes=cint(doc.duration))
	channel = frappe.db.get_value("AS Channel", doc.channel, ["channel_name", "channel_type"], as_dict=True)
	call = frappe.db.get_value(
		"AS Call",
		{"channel": doc.channel, "started_at": ("between", (starts - timedelta(minutes=15), ends))},
		["name", "status", "started_at", "ended_at", "participants"],
		as_dict=True,
		order_by="started_at asc",
	)
	mine = next((i for i in doc.invitees if i.user == viewer), None)
	return {
		"name": doc.name,
		"title": doc.title,
		"agenda": doc.agenda,
		"starts_at": str(starts),
		"ends_at": str(ends),
		"duration": cint(doc.duration),
		"call_type": doc.call_type,
		"status": doc.status,
		"host": doc.host,
		"host_name": get_fullname(doc.host),
		"channel": doc.channel,
		"channel_name": channel.channel_name if channel else None,
		"channel_type": channel.channel_type if channel else None,
		"invitees": [{"user": i.user, "response": i.response} for i in doc.invitees],
		"is_host": doc.host == viewer,
		"my_response": "Accepted" if doc.host == viewer else (mine.response if mine else None),
		"live": bool(call and call.status == "Active"),
		"call": {
			"status": call.status,
			"started_at": str(call.started_at),
			"ended_at": str(call.ended_at) if call.ended_at else None,
			"joined": [u for u in (call.participants or "").splitlines() if u],
		}
		if call
		else None,
	}


def _get(name: str):
	doc = frappe.get_doc("AS Meeting", name)
	viewer = require_login()
	if viewer not in _people(doc):
		frappe.throw(_("You're not invited to this meeting"), frappe.PermissionError)
	return doc, viewer


def _host_only(name: str):
	doc, viewer = _get(name)
	if doc.host != viewer:
		frappe.throw(_("Only the host can change this meeting"), frappe.PermissionError)
	return doc, viewer


def _meeting_chat(host, invitees, title) -> str:
	"""The direct chat for a one-to-one meeting, else a new group named after the meeting.
	(The meeting invite is the notification, so no separate "added you to a group" one.)"""
	if len(invitees) == 1:
		return get_or_create_dm(invitees[0])
	channel = frappe.get_doc(
		{"doctype": "AS Channel", "channel_type": "Group", "channel_name": f"📅 {title}"[:140]}
	).insert(ignore_permissions=True)
	add_member(channel.name, host, role="Admin")
	for user in invitees:
		add_member(channel.name, user)
	notify_sidebar_change([host, *invitees])
	return channel.name


def _refresh(users):
	for user in set(users):
		frappe.publish_realtime("as_meetings", {}, user=user, after_commit=True)


def _clean(title, starts_at, duration, call_type):
	title = (title or "").strip()
	if not title:
		frappe.throw(_("Give the meeting a title"))
	starts = get_datetime(starts_at)
	if starts < now_datetime() - timedelta(minutes=5):
		frappe.throw(_("Pick a time in the future"))
	duration = cint(duration)
	if duration not in DURATIONS:
		frappe.throw(_("Pick a duration"))
	return title, starts, duration, "Audio" if call_type == "Audio" else "Video"


@frappe.whitelist(methods=["POST"])
def schedule(
	title: str,
	starts_at: str,
	duration: int = 30,
	call_type: str = "Video",
	agenda: str | None = None,
	users=None,
	channel: str | None = None,
):
	"""Invite people (a new group/direct chat is made for them) or everyone in a channel."""
	host = require_login()
	title, starts, duration, call_type = _clean(title, starts_at, duration, call_type)
	if channel:
		check_member(channel)
		invitees = [u for u in get_member_users(channel) if u != host]
	else:
		users = frappe.parse_json(users) if isinstance(users, str) else users
		invitees = sorted({u for u in (users or []) if u and u != host})
		if not invitees:
			frappe.throw(_("Invite at least one person"))
		channel = _meeting_chat(host, invitees, title)

	doc = frappe.get_doc(
		{
			"doctype": "AS Meeting",
			"title": title,
			"starts_at": starts,
			"duration": duration,
			"call_type": call_type,
			"agenda": (agenda or "").strip() or None,
			"host": host,
			"channel": channel,
			"status": "Scheduled",
			"invitees": [{"user": u, "response": "Pending"} for u in invitees],
		}
	).insert(ignore_permissions=True)

	post_system_message(
		channel,
		_("{0} scheduled {1} · {2} ({3} min)").format(get_fullname(host), title, _when(doc), duration),
	)
	for user in invitees:
		push(
			user,
			"Meeting",
			from_user=host,
			channel=channel,
			preview=_("invited you to {0} · {1}").format(title, _when(doc)),
		)
	_refresh(_people(doc))
	return _payload(doc, host)


@frappe.whitelist(methods=["POST"])
def update(
	name: str,
	title: str,
	starts_at: str,
	duration: int = 30,
	call_type: str = "Video",
	agenda: str | None = None,
):
	doc, host = _host_only(name)
	if doc.status == "Cancelled":
		frappe.throw(_("This meeting was cancelled"))
	title, starts, duration, call_type = _clean(title, starts_at, duration, call_type)
	moved = get_datetime(doc.starts_at) != starts or cint(doc.duration) != duration
	doc.update(
		{
			"title": title,
			"starts_at": starts,
			"duration": duration,
			"call_type": call_type,
			"agenda": (agenda or "").strip() or None,
		}
	)
	if moved:
		doc.reminder_sent = 0
		for invitee in doc.invitees:  # a new time needs a new answer
			invitee.response = "Pending"
	doc.save(ignore_permissions=True)

	if moved:
		post_system_message(doc.channel, _("{0} moved to {1}").format(title, _when(doc)))
		for invitee in doc.invitees:
			push(
				invitee.user,
				"Meeting",
				from_user=host,
				channel=doc.channel,
				preview=_("moved {0} to {1}").format(title, _when(doc)),
			)
	_refresh(_people(doc))
	return _payload(doc, host)


@frappe.whitelist(methods=["POST"])
def cancel(name: str):
	doc, host = _host_only(name)
	if doc.status == "Cancelled":
		return _payload(doc, host)
	doc.status = "Cancelled"
	doc.save(ignore_permissions=True)
	post_system_message(
		doc.channel, _("{0} cancelled {1} ({2})").format(get_fullname(host), doc.title, _when(doc))
	)
	for invitee in doc.invitees:
		push(
			invitee.user,
			"Meeting",
			from_user=host,
			channel=doc.channel,
			preview=_("cancelled {0} · {1}").format(doc.title, _when(doc)),
		)
	_refresh(_people(doc))
	return _payload(doc, host)


@frappe.whitelist(methods=["POST"])
def respond(name: str, response: str):
	doc, user = _get(name)
	if response not in ("Accepted", "Declined"):
		frappe.throw(_("Answer Accepted or Declined"))
	row = next((i for i in doc.invitees if i.user == user), None)
	if not row:
		frappe.throw(_("The host doesn't need to answer"))
	row.response = response
	doc.save(ignore_permissions=True)
	if response == "Declined":
		push(
			doc.host,
			"Meeting",
			from_user=user,
			channel=doc.channel,
			preview=_("can't make it to {0} · {1}").format(doc.title, _when(doc)),
		)
	_refresh(_people(doc))
	return _payload(doc, user)


@frappe.whitelist()
def get_meetings(scope: str = "upcoming"):
	"""Upcoming (not yet over) or past (last 30 days) meetings I host or am invited to."""
	user = require_login()
	invited = frappe.get_all("AS Meeting Invitee", filters={"user": user}, pluck="parent")
	now = now_datetime()
	or_filters = [["AS Meeting", "host", "=", user], ["AS Meeting", "name", "in", invited or [""]]]
	if scope == "past":
		filters = [["AS Meeting", "starts_at", "between", (add_days(now, -30), now)]]
		order = "starts_at desc"
	else:
		# anything that hasn't ended yet (longest meeting is 2h)
		filters = [["AS Meeting", "starts_at", ">=", now - timedelta(minutes=max(DURATIONS))]]
		order = "starts_at asc"
	names = frappe.get_all("AS Meeting", filters=filters, or_filters=or_filters, pluck="name", order_by=order)
	rows = [_payload(frappe.get_doc("AS Meeting", n), user) for n in names]
	if scope == "past":
		return [r for r in rows if get_datetime(r["ends_at"]) <= now][:50]
	return [r for r in rows if get_datetime(r["ends_at"]) > now]


def send_reminders():
	"""Every minute: meetings starting within the next few minutes."""
	now = now_datetime()
	for name in frappe.get_all(
		"AS Meeting",
		filters={
			"status": "Scheduled",
			"reminder_sent": 0,
			"starts_at": ("between", (now, now + timedelta(minutes=REMINDER_MINUTES))),
		},
		pluck="name",
	):
		doc = frappe.get_doc("AS Meeting", name)
		doc.db_set("reminder_sent", 1)
		going = [doc.host, *[i.user for i in doc.invitees if i.response != "Declined"]]
		for user in going:
			push(
				user,
				"Meeting",
				from_user=doc.host,
				channel=doc.channel,
				preview=_("{0} starts at {1}").format(doc.title, format_datetime(doc.starts_at, "h:mm a")),
			)
