"""Bridge between AeraSpace projects/tasks and ERPNext Project / Task.

ERPNext owns the records; AeraSpace keeps its board, IDs (SHOP-12) and channel-based access.
AeraSpace-only details live in `as_` custom fields, and the AeraSpace status of each record is kept
in sync with ERPNext's own status so Desk, reports and AeraSpace agree.
"""

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate, today

# ---- statuses ------------------------------------------------------------------

TASK_STATUSES = ("Backlog", "Todo", "In Progress", "Code Review", "Testing", "Done")
TASK_TO_ERPNEXT = {
	"Backlog": "Open",
	"Todo": "Open",
	"In Progress": "Working",
	"Code Review": "Working",
	"Testing": "Pending Review",
	"Done": "Completed",
}
# a status changed in Desk moves the card; Overdue / Cancelled leave the board column alone
TASK_FROM_ERPNEXT = {
	"Open": "Todo",
	"Working": "In Progress",
	"Pending Review": "Testing",
	"Completed": "Done",
}

PROJECT_STATUSES = ("Active", "On Hold", "Completed", "Archived")
PROJECT_TO_ERPNEXT = {
	"Active": "Open",
	"On Hold": "On hold",
	"Completed": "Completed",
	"Archived": "Cancelled",
}
PROJECT_FROM_ERPNEXT = {v: k for k, v in PROJECT_TO_ERPNEXT.items()}

# ---- AeraSpace field -> ERPNext column ------------------------------------------

PROJECT_COLUMNS = {
	"name": "name",
	"project_name": "project_name",
	"project_key": "as_project_key",
	"description": "notes",
	"status": "as_status",
	"visibility": "as_visibility",
	"lead": "as_lead",
	"client": "as_client",
	"channel": "as_channel",
	"creation": "creation",
}
TASK_COLUMNS = {
	"name": "name",
	"title": "subject",
	"project": "project",
	"status": "as_status",
	"priority": "priority",
	"assignee": "as_assignee",
	"reporter": "as_reporter",
	"due_date": "exp_end_date",
	"labels": "as_labels",
	"description": "description",
	"files": "as_files",
	"source_message": "as_source_message",
	"sort_order": "as_sort_order",
	"completed_on": "completed_on",
	"creation": "creation",
	"modified": "modified",
}


def select_fields(columns: dict, alias: str = "") -> list[str]:
	"""Field list for get_all / SQL that returns AeraSpace names, e.g. 'subject as title'."""
	prefix = f"{alias}." if alias else ""
	return [f"{prefix}{col} as {key}" if col != key else f"{prefix}{col}" for key, col in columns.items()]


def to_columns(columns: dict, values: dict) -> dict:
	"""AeraSpace field names -> ERPNext fieldnames, for writes."""
	return {columns.get(k, k): v for k, v in values.items()}


PROJECT_SELECT = select_fields(PROJECT_COLUMNS)
TASK_SELECT = select_fields(TASK_COLUMNS)


# ---- custom fields ----------------------------------------------------------------


def ensure_custom_fields():
	select = lambda options: "\n".join(options)  # noqa: E731
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "as_section",
					"label": "AeraSpace",
					"fieldtype": "Section Break",
					"insert_after": "notes",
					"collapsible": 1,
				},
				{
					"fieldname": "as_project_key",
					"label": "Project Key",
					"fieldtype": "Data",
					"insert_after": "as_section",
					"unique": 1,
					"read_only": 1,
				},
				{
					"fieldname": "as_status",
					"label": "AeraSpace Status",
					"fieldtype": "Select",
					"options": select(PROJECT_STATUSES),
					"default": "Active",
					"insert_after": "as_project_key",
				},
				{
					"fieldname": "as_visibility",
					"label": "Visibility",
					"fieldtype": "Select",
					"options": "Private\nPublic",
					"default": "Private",
					"insert_after": "as_status",
				},
				{"fieldname": "as_cb", "fieldtype": "Column Break", "insert_after": "as_visibility"},
				{
					"fieldname": "as_lead",
					"label": "Lead",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "as_cb",
				},
				{"fieldname": "as_client", "label": "Client", "fieldtype": "Data", "insert_after": "as_lead"},
				{
					"fieldname": "as_channel",
					"label": "Channel",
					"fieldtype": "Link",
					"options": "AS Channel",
					"insert_after": "as_client",
					"read_only": 1,
				},
				{
					"fieldname": "as_last_task_number",
					"label": "Last Task Number",
					"fieldtype": "Int",
					"default": "0",
					"insert_after": "as_channel",
					"read_only": 1,
				},
			],
			"Task": [
				{
					"fieldname": "as_section",
					"label": "AeraSpace",
					"fieldtype": "Section Break",
					"insert_after": "description",
					"collapsible": 1,
				},
				{
					"fieldname": "as_status",
					"label": "Board Column",
					"fieldtype": "Select",
					"options": select(TASK_STATUSES),
					"default": "Todo",
					"insert_after": "as_section",
					"in_standard_filter": 1,
				},
				{
					"fieldname": "as_assignee",
					"label": "Assignee",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "as_status",
					"in_standard_filter": 1,
				},
				{
					"fieldname": "as_reporter",
					"label": "Reporter",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "as_assignee",
				},
				{
					"fieldname": "as_labels",
					"label": "Labels",
					"fieldtype": "Data",
					"insert_after": "as_reporter",
				},
				{"fieldname": "as_cb", "fieldtype": "Column Break", "insert_after": "as_labels"},
				{
					"fieldname": "as_source_message",
					"label": "Source Message",
					"fieldtype": "Link",
					"options": "AS Message",
					"insert_after": "as_cb",
					"read_only": 1,
				},
				{
					"fieldname": "as_sort_order",
					"label": "Board Order",
					"fieldtype": "Float",
					"insert_after": "as_source_message",
					"hidden": 1,
				},
				{
					"fieldname": "as_files",
					"label": "Files",
					"fieldtype": "JSON",
					"insert_after": "as_sort_order",
					"hidden": 1,
				},
			],
		},
		update=True,
	)
	frappe.db.add_index("Task", ["project", "as_status", "as_sort_order"])


# ---- keys and task numbers -------------------------------------------------------

KEY_PATTERN = r"[A-Z][A-Z0-9]{1,7}"


def clean_key(key: str) -> str:
	key = (key or "").strip().upper()
	if not re.fullmatch(KEY_PATTERN, key):
		frappe.throw(_("Project key must be 2-8 letters or digits and start with a letter, e.g. SHOP"))
	if frappe.db.exists("Project", key) or frappe.db.exists("Project", {"as_project_key": key}):
		frappe.throw(_("Project key {0} is already used").format(key))
	return key


def suggest_key(project_name: str) -> str:
	"""SHOPIFY INTEGRATION -> SI, Shopify -> SHOP; never collides with an existing key."""
	words = re.findall(r"[A-Za-z0-9]+", project_name or "")
	base = (
		"".join(w[0] for w in words).upper() if len(words) > 1 else (words[0][:4].upper() if words else "PRJ")
	)
	if not base[:1].isalpha():
		base = "P" + base
	base = (base + "X")[: max(2, len(base))][:6]
	key, n = base, 2
	while frappe.db.exists("Project", key) or frappe.db.exists("Project", {"as_project_key": key}):
		key, n = f"{base}{n}", n + 1
	return key


def next_task_name(project: str) -> str:
	"""SHOP-13. Locks the project row so two people creating tasks at once never get the same number."""
	key, last = frappe.db.sql(
		"select coalesce(as_project_key, name), as_last_task_number from `tabProject` where name = %s for update",
		project,
	)[0]
	number = (last or 0) + 1
	while frappe.db.exists("Task", f"{key}-{number}"):
		number += 1
	frappe.db.set_value("Project", project, "as_last_task_number", number, update_modified=False)
	return f"{key}-{number}"


# ---- people ------------------------------------------------------------------------


def set_assignee(task: str, user: str | None):
	"""Mirror the AeraSpace assignee as a Frappe assignment so Desk shows it.
	ToDos are written directly: AeraSpace sends its own notifications, so Frappe's stay quiet."""
	for todo in frappe.get_all(
		"ToDo",
		filters={"reference_type": "Task", "reference_name": task, "status": "Open"},
		fields=["name", "allocated_to"],
	):
		if todo.allocated_to == user:
			user = None  # already assigned
			continue
		frappe.db.set_value("ToDo", todo.name, "status", "Cancelled")
	if user:
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": user,
				"reference_type": "Task",
				"reference_name": task,
				"description": frappe.db.get_value("Task", task, "subject"),
				"assigned_by": frappe.session.user,
				"status": "Open",
				"date": today(),
			}
		).insert(ignore_permissions=True)
	_update_assign_cache(task)


def _update_assign_cache(task: str):
	assigned = frappe.get_all(
		"ToDo",
		filters={"reference_type": "Task", "reference_name": task, "status": "Open"},
		pluck="allocated_to",
	)
	frappe.db.set_value("Task", task, "_assign", frappe.as_json(assigned), update_modified=False)


# ---- doc events: keep the two statuses in step (before_validate, so ERPNext sees the result) ----


def sync_task_status(doc, method=None):
	"""AeraSpace board column <-> ERPNext status, whichever side changed."""
	before = doc.get_doc_before_save()
	board_changed = not before or before.as_status != doc.as_status
	status_changed = not before or before.status != doc.status

	# a status set in Desk (or by ERPNext) moves the card, unless the column already matches it
	# (a new task takes its column from the status only when no column was chosen, i.e. the default "Todo")
	if (
		status_changed
		and (not board_changed if before else doc.as_status in (None, "", "Todo"))
		and doc.status in TASK_FROM_ERPNEXT
		and TASK_TO_ERPNEXT.get(doc.as_status) != doc.status
	):
		doc.as_status = TASK_FROM_ERPNEXT[doc.status]
		board_changed = True
	doc.as_status = doc.as_status or "Todo"
	if doc.as_status not in TASK_STATUSES:
		frappe.throw(_("Invalid status"))
	# Overdue / Cancelled / Template are ERPNext's own; keep them until the card is moved
	if board_changed or doc.status not in ("Overdue", "Cancelled", "Template"):
		doc.status = TASK_TO_ERPNEXT[doc.as_status]

	if doc.status == "Completed" and (not before or before.status != "Completed"):
		# ERPNext closes assignments on completion with the user's Desk permissions; do it here instead
		_close_assignments(doc.name)

	doc.subject = (doc.subject or "").strip()
	if doc.as_status == "Done":
		doc.completed_on = doc.completed_on or getdate()
		doc.completed_by = doc.completed_by or frappe.session.user
	else:
		doc.completed_on = doc.completed_by = None
	if doc.as_labels:
		doc.as_labels = ", ".join(dict.fromkeys(l.strip() for l in doc.as_labels.split(",") if l.strip()))


def after_task_save(doc, method=None):
	before = doc.get_doc_before_save()
	reopened = before and before.as_status == "Done" and doc.as_status != "Done"
	if reopened or (before.as_assignee if before else None) != doc.as_assignee:
		set_assignee(doc.name, None if doc.as_status == "Done" else doc.as_assignee)


def _close_assignments(task: str):
	if not frappe.db.exists("Task", task):
		return  # not inserted yet
	frappe.db.set_value(
		"ToDo", {"reference_type": "Task", "reference_name": task, "status": "Open"}, "status", "Closed"
	)
	_update_assign_cache(task)


def sync_project_status(doc, method=None):
	"""Keep ERPNext's project status driven by the AeraSpace status (and vice versa from Desk)."""
	before = doc.get_doc_before_save()
	ours_changed = not before or before.as_status != doc.as_status
	theirs_changed = before and before.status != doc.status
	if theirs_changed and not ours_changed and doc.status in PROJECT_FROM_ERPNEXT:
		doc.as_status = PROJECT_FROM_ERPNEXT[doc.status]
	doc.as_status = doc.as_status or "Active"
	doc.status = PROJECT_TO_ERPNEXT[doc.as_status]
	# AeraSpace decides the status, so ERPNext must not recompute it from task completion
	doc.percent_complete_method = "Manual"
	# access comes from the project channel; never send ERPNext's project welcome emails
	for row in doc.users:
		row.welcome_email_sent = 1
