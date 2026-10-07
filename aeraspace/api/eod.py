import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, get_fullname, getdate, now_datetime, today

from aeraspace.aeraspace.doctype.as_daily_update.as_daily_update import SECTIONS
from aeraspace.aeraspace.doctype.as_settings.as_settings import get_settings, is_working_day
from aeraspace.team import can_view, reportees, team_scope
from aeraspace.utils import OPEN_TYPES, add_member, get_member, require_login

UPDATE_FIELDS = ["name", "user", "update_date", *SECTIONS, "posted_message", "creation", "modified"]
OPEN_TASK_STATUSES = ("In Progress", "Code Review", "Testing")


def _payload(row):
	return {
		**row,
		"update_date": str(row["update_date"]),
		"creation": str(row["creation"]),
		"modified": str(row["modified"]),
	}


def reminder_time():
	return str(get_settings().eod_reminder_time or "18:30:00")


@frappe.whitelist()
def get_my_update(date: str | None = None):
	"""My update for a day, plus suggestions from tasks and time logged that day."""
	user = require_login()
	date = getdate(date or today())
	row = frappe.db.get_value(
		"AS Daily Update", {"user": user, "update_date": date}, UPDATE_FIELDS, as_dict=True
	)

	done = frappe.get_all(
		"Task",
		filters={"as_assignee": user, "as_status": "Done", "completed_on": date},
		fields=["name", "subject as title"],
	)
	ongoing = frappe.get_all(
		"Task",
		filters={"as_assignee": user, "as_status": ("in", OPEN_TASK_STATUSES)},
		fields=["name", "subject as title", "as_status as status"],
		order_by="modified desc",
	)
	time_logs = frappe.db.sql(
		"""select p.project_name, t.subject as task_title, l.task, sum(l.minutes) as minutes
		from `tabAS Time Log` l
		join `tabProject` p on p.name = l.project
		left join `tabTask` t on t.name = l.task
		where l.user = %s and l.log_date = %s
		group by l.project, l.task""",
		(user, date),
		as_dict=True,
	)
	return {
		"date": str(date),
		"update": _payload(row) if row else None,
		"suggestions": {"completed": done, "in_progress": ongoing},
		"time_logs": time_logs,
		"reminder_time": reminder_time(),
		"has_team": bool(reportees(user)) or team_scope(user)[1],
	}


@frappe.whitelist(methods=["POST"])
def save_update(
	date: str | None = None,
	completed=None,
	in_progress=None,
	blockers=None,
	tomorrow=None,
	post_to_channel: int = 1,
):
	user = require_login()
	date = getdate(date or today())
	if date > getdate(today()):
		frappe.throw(_("You can't submit an update for a future date"))

	values = {"completed": completed, "in_progress": in_progress, "blockers": blockers, "tomorrow": tomorrow}
	name = frappe.db.get_value("AS Daily Update", {"user": user, "update_date": date})
	doc = (
		frappe.get_doc("AS Daily Update", name)
		if name
		else frappe.get_doc({"doctype": "AS Daily Update", "user": user, "update_date": date})
	)
	doc.update(values)
	doc.save(ignore_permissions=True)

	if int(post_to_channel or 0):
		_post_to_channel(doc)
	return _payload(frappe.db.get_value("AS Daily Update", doc.name, UPDATE_FIELDS, as_dict=True))


def _format_update(doc) -> str:
	labels = {
		"completed": "✅ Completed",
		"in_progress": "🔄 In progress",
		"blockers": "⛔ Blockers",
		"tomorrow": "📅 Tomorrow",
	}
	parts = [f"**EOD update — {getdate(doc.update_date).strftime('%d %b %Y')}**"]
	for field, label in labels.items():
		if doc.get(field):
			parts.append(f"**{label}**\n{doc.get(field)}")
	return "\n\n".join(parts)


def _post_to_channel(doc):
	"""Post (or refresh) the update in the configured EOD channel."""
	channel = get_settings().eod_channel
	if not channel or not frappe.db.exists("AS Channel", channel):
		return
	if not get_member(channel, doc.user):
		if frappe.db.get_value("AS Channel", channel, "channel_type") not in OPEN_TYPES:
			return  # private channel the user isn't in: keep the update private
		add_member(channel, doc.user)

	content = _format_update(doc)
	if doc.posted_message and frappe.db.exists("AS Message", {"name": doc.posted_message, "is_deleted": 0}):
		from aeraspace.messages import publish_message_update

		message = frappe.get_doc("AS Message", doc.posted_message)
		message.content = content
		message.is_edited = 1
		message.save(ignore_permissions=True)
		publish_message_update(message.name)
	else:
		message = frappe.get_doc(
			{"doctype": "AS Message", "channel": channel, "sender": doc.user, "content": content}
		).insert(ignore_permissions=True)
		doc.db_set("posted_message", message.name, update_modified=False)


@frappe.whitelist()
def get_team_report(date: str | None = None):
	"""Everyone the viewer may see, with submitted / pending / missed for the day."""
	viewer = require_login()
	date = getdate(date or today())
	people, everyone = team_scope(viewer)

	updates = {
		row.user: _payload(row)
		for row in frappe.get_all(
			"AS Daily Update",
			filters={"update_date": date, "user": ("in", people)},
			fields=UPDATE_FIELDS,
		)
	}
	# after the reminder time on the day (or any later day) a missing update counts as missed
	cutoff = get_datetime(f"{date} {reminder_time()}")
	is_past = now_datetime() >= cutoff
	working = is_working_day(date)

	rows = []
	for user in people:
		update = updates.get(user)
		if update:
			state = "submitted"
		elif not working:
			state = "off"
		else:
			state = "missed" if is_past else "pending"
		rows.append({"user": user, "full_name": get_fullname(user), "state": state, "update": update})
	rows.sort(
		key=lambda r: ({"missed": 0, "pending": 1, "submitted": 2, "off": 3}[r["state"]], r["full_name"])
	)

	counts = {
		state: sum(1 for r in rows if r["state"] == state)
		for state in ("submitted", "pending", "missed", "off")
	}
	return {"date": str(date), "working_day": working, "everyone": everyone, "rows": rows, "counts": counts}


@frappe.whitelist()
def get_history(user: str | None = None, days: int = 14):
	viewer = require_login()
	user = user or viewer
	if not can_view(viewer, user):
		frappe.throw(_("You can't view this person's updates"), frappe.PermissionError)
	rows = frappe.get_all(
		"AS Daily Update",
		filters={"user": user, "update_date": (">=", add_days(today(), -int(days)))},
		fields=UPDATE_FIELDS,
		order_by="update_date desc",
	)
	return [_payload(r) for r in rows]
