import csv
import io

import frappe
from frappe import _
from frappe.utils import cint, get_fullname, getdate, today

from aeraspace.api.project import check_project_member
from aeraspace.team import team_scope
from aeraspace.utils import require_login

LOG_FIELDS = ["name", "user", "log_date", "project", "task", "minutes", "description", "creation"]
GROUPS = {
	"project": ("l.project", "p.project_name"),
	"employee": ("l.user", "u.full_name"),
	"client": (
		"coalesce(nullif(p.as_client, ''), '(No client)')",
		"coalesce(nullif(p.as_client, ''), '(No client)')",
	),
	"task": ("coalesce(l.task, '')", "coalesce(concat(l.task, ' · ', t.subject), '(No task)')"),
	"date": ("l.log_date", "l.log_date"),
}


def _row(r):
	return {**r, "log_date": str(r["log_date"]), "creation": str(r.get("creation", ""))}


@frappe.whitelist(methods=["POST"])
def log_time(
	project: str,
	minutes: int,
	log_date: str | None = None,
	task: str | None = None,
	description: str | None = None,
):
	user = require_login()
	check_project_member(project)
	doc = frappe.get_doc(
		{
			"doctype": "AS Time Log",
			"user": user,
			"project": project,
			"task": task or None,
			"minutes": cint(minutes),
			"log_date": getdate(log_date or today()),
			"description": description,
		}
	).insert(ignore_permissions=True)
	return _row(doc.as_dict())


@frappe.whitelist(methods=["POST"])
def update_log(name: str, **values):
	doc = _own_log(name)
	allowed = {
		k: v for k, v in values.items() if k in ("project", "task", "minutes", "log_date", "description")
	}
	if "project" in allowed:
		check_project_member(allowed["project"])
	if "minutes" in allowed:
		allowed["minutes"] = cint(allowed["minutes"])
	if "task" in allowed:
		allowed["task"] = allowed["task"] or None
	doc.update(allowed)
	doc.save(ignore_permissions=True)
	return _row(doc.as_dict())


@frappe.whitelist(methods=["POST"])
def delete_log(name: str):
	frappe.delete_doc("AS Time Log", _own_log(name).name, ignore_permissions=True)


def _own_log(name):
	doc = frappe.get_doc("AS Time Log", name)
	if doc.user != require_login():
		frappe.throw(_("You can only change your own time entries"), frappe.PermissionError)
	return doc


@frappe.whitelist()
def get_my_logs(from_date: str, to_date: str):
	user = require_login()
	rows = frappe.db.sql(
		"""select l.name, l.user, l.log_date, l.project, p.project_name, l.task, t.subject as task_title,
			l.minutes, l.description, l.creation
		from `tabAS Time Log` l
		join `tabProject` p on p.name = l.project
		left join `tabTask` t on t.name = l.task
		where l.user = %(user)s and l.log_date between %(from)s and %(to)s
		order by l.log_date desc, l.creation desc""",
		{"user": user, "from": getdate(from_date), "to": getdate(to_date)},
		as_dict=True,
	)
	return [_row(r) for r in rows]


def _visible_condition(viewer):
	"""SQL condition + params limiting logs to what the viewer may see."""
	people, everyone = team_scope(viewer)
	if everyone:
		return "1=1", {}
	# plus: all time on projects where the viewer is an admin of the project channel
	admin_projects = frappe.db.sql_list(
		"""select p.name from `tabProject` p join `tabAS Channel Member` m on m.channel = p.as_channel
		where m.user = %s and m.role = 'Admin'""",
		viewer,
	)
	return "(l.user in %(people)s or l.project in %(admin_projects)s)", {
		"people": people,
		"admin_projects": admin_projects or [""],
	}


def _report_rows(viewer, from_date, to_date, project=None, user=None):
	condition, params = _visible_condition(viewer)
	filters = [condition, "l.log_date between %(from)s and %(to)s"]
	params.update({"from": getdate(from_date), "to": getdate(to_date)})
	if project:
		filters.append("l.project = %(project)s")
		params["project"] = project
	if user:
		filters.append("l.user = %(user)s")
		params["user"] = user
	return frappe.db.sql(
		f"""select l.name, l.user, u.full_name, l.log_date, l.project, p.project_name,
			coalesce(nullif(p.as_client, ''), '(No client)') as client,
			l.task, t.subject as task_title, l.minutes, l.description
		from `tabAS Time Log` l
		join `tabProject` p on p.name = l.project
		join `tabUser` u on u.name = l.user
		left join `tabTask` t on t.name = l.task
		where {" and ".join(filters)}
		order by l.log_date desc, u.full_name""",
		params,
		as_dict=True,
	)


@frappe.whitelist()
def get_report(
	from_date: str,
	to_date: str,
	group_by: str = "project",
	project: str | None = None,
	user: str | None = None,
):
	viewer = require_login()
	if group_by not in GROUPS:
		frappe.throw(_("Invalid grouping"))
	rows = _report_rows(viewer, from_date, to_date, project, user)

	key_of = {
		"project": lambda r: (r.project, r.project_name),
		"employee": lambda r: (r.user, r.full_name or r.user),
		"client": lambda r: (r.client, r.client),
		"task": lambda r: (r.task or "", f"{r.task} · {r.task_title}" if r.task else "(No task)"),
		"date": lambda r: (str(r.log_date), str(r.log_date)),
	}[group_by]

	groups = {}
	for r in rows:
		key, label = key_of(r)
		group = groups.setdefault(key, {"key": key, "label": label, "minutes": 0, "entries": []})
		group["minutes"] += r.minutes
		group["entries"].append(_row(r))
	ordered = sorted(groups.values(), key=lambda g: (-g["minutes"], g["label"]))
	if group_by == "date":
		ordered.sort(key=lambda g: g["key"], reverse=True)

	people, everyone = team_scope(viewer)
	return {
		"groups": ordered,
		"total_minutes": sum(r.minutes for r in rows),
		"people": []
		if not everyone and len(people) == 1
		else [{"user": u, "full_name": get_fullname(u)} for u in people],
	}


@frappe.whitelist()
def export_report(from_date: str, to_date: str, project: str | None = None, user: str | None = None):
	"""CSV download of the visible entries."""
	viewer = require_login()
	rows = _report_rows(viewer, from_date, to_date, project, user)
	out = io.StringIO()
	writer = csv.writer(out)
	writer.writerow(["Date", "Employee", "Project", "Client", "Task", "Hours", "Description"])
	for r in rows:
		task = f"{r.task} {r.task_title}" if r.task else ""
		writer.writerow(
			[
				r.log_date,
				r.full_name or r.user,
				r.project_name,
				r.client,
				task,
				round(r.minutes / 60, 2),
				r.description or "",
			]
		)
	frappe.response["type"] = "download"
	frappe.response["filename"] = f"timesheet-{from_date}-to-{to_date}.csv"
	frappe.response["filecontent"] = out.getvalue()
