from html import unescape

import frappe
from frappe import _
from frappe.utils import cint, get_fullname, getdate

from aeraspace.aeraspace.doctype.as_task.as_task import STATUSES
from aeraspace.api.project import check_project_member, check_project_read
from aeraspace.notifications import mentioned_users, plain_preview, push
from aeraspace.utils import (
	OPEN_TYPES,
	check_read,
	get_member,
	post_system_message,
	publish_to_channel,
	require_login,
)

TASK_FIELDS = [
	"name",
	"title",
	"project",
	"status",
	"priority",
	"assignee",
	"reporter",
	"due_date",
	"labels",
	"description",
	"files",
	"source_message",
	"sort_order",
	"completed_on",
	"creation",
	"modified",
]
EDITABLE = ("title", "description", "status", "priority", "assignee", "due_date", "labels", "files")
PRIORITIES = ("Low", "Medium", "High", "Urgent")


def to_payload(row) -> dict:
	row = frappe._dict(row)
	return frappe._dict(
		{
			**{f: row.get(f) for f in TASK_FIELDS},
			"files": frappe.parse_json(row.files) if row.get("files") else [],
			"labels": [l.strip() for l in (row.labels or "").split(",") if l.strip()],
			"due_date": str(row.due_date) if row.get("due_date") else None,
			"completed_on": str(row.completed_on) if row.get("completed_on") else None,
			"creation": str(row.creation),
			"modified": str(row.modified),
		}
	)


def get_payload(task: str) -> dict:
	row = frappe.db.get_value("AS Task", task, TASK_FIELDS, as_dict=True)
	payload = to_payload(row)
	payload.comment_count = frappe.db.count(
		"Comment", {"reference_doctype": "AS Task", "reference_name": task, "comment_type": "Comment"}
	)
	return payload


def broadcast(task: str, event: str = "as_task_update", payload: dict | None = None):
	payload = payload or get_payload(task)
	channel = frappe.db.get_value("AS Project", payload["project"], "channel")
	publish_to_channel(channel, event, payload)
	return payload


def _validate_assignee(project, assignee):
	if assignee and not get_member(project.channel, assignee):
		frappe.throw(_("{0} is not a member of this project").format(get_fullname(assignee)))


def _task_label(task) -> str:
	return f"{task.name} · {task.title}"


@frappe.whitelist()
def get_tasks(
	project: str | None = None, assignee: str | None = None, include_done: int = 1, search: str | None = None
):
	"""Tasks of one project (board), or tasks across the user's projects (e.g. assignee=me)."""
	user = require_login()
	filters = {}
	if project:
		check_project_read(project)
		filters["project"] = project
	else:
		visible = frappe.db.sql_list(
			"""select p.name from `tabAS Project` p join `tabAS Channel` c on c.name = p.channel
			where c.channel_type in %(open)s
				or exists(select 1 from `tabAS Channel Member` m where m.channel = p.channel and m.user = %(user)s)""",
			{"open": OPEN_TYPES, "user": user},
		)
		filters["project"] = ("in", visible or [""])
	if assignee:
		filters["assignee"] = user if assignee == "me" else assignee
	if not cint(include_done):
		filters["status"] = ("!=", "Done")
	if search:
		filters["title"] = ("like", f"%{search}%")

	rows = frappe.get_all(
		"AS Task", filters=filters, fields=TASK_FIELDS, order_by="sort_order asc, creation asc", limit=1000
	)
	counts = dict(
		frappe.db.sql(
			"""select reference_name, count(*) from `tabComment`
			where reference_doctype = 'AS Task' and comment_type = 'Comment' and reference_name in %(names)s
			group by reference_name""",
			{"names": [r.name for r in rows] or [""]},
		)
	)
	tasks = [to_payload(r) for r in rows]
	for task in tasks:
		task.comment_count = counts.get(task.name, 0)
	return tasks


@frappe.whitelist()
def get_task(task: str):
	row = frappe.db.get_value("AS Task", task, TASK_FIELDS, as_dict=True)
	if not row:
		frappe.throw(_("Task not found"), frappe.DoesNotExistError)
	project = check_project_read(row.project)
	payload = to_payload(row)
	payload.project_name = project.project_name
	payload.channel = project.channel
	payload.can_edit = bool(get_member(project.channel))
	# Comment.validate html-escapes content; we store plain text/markdown and sanitise on display
	payload.comments = [
		{**c, "content": unescape(c.content or ""), "creation": str(c.creation)}
		for c in frappe.get_all(
			"Comment",
			filters={"reference_doctype": "AS Task", "reference_name": task, "comment_type": "Comment"},
			fields=["name", "owner", "content", "creation"],
			order_by="creation asc",
		)
	]
	if row.source_message:
		source = frappe.db.get_value(
			"AS Message", row.source_message, ["channel", "thread_root"], as_dict=True
		)
		payload.source = source if source and _can_read_channel(source.channel) else None
	return payload


def _can_read_channel(channel):
	try:
		check_read(channel)
		return True
	except frappe.PermissionError:
		frappe.clear_last_message()
		return False


@frappe.whitelist(methods=["POST"])
def create_task(
	project: str,
	title: str,
	description: str | None = None,
	status: str = "Todo",
	priority: str = "Medium",
	assignee: str | None = None,
	due_date: str | None = None,
	labels: str | None = None,
	source_message: str | None = None,
	files=None,
):
	me = require_login()
	proj = check_project_member(project)
	_validate_assignee(proj, assignee)
	if priority not in PRIORITIES:
		frappe.throw(_("Invalid priority"))
	if source_message:
		source_channel = frappe.db.get_value("AS Message", source_message, "channel")
		if not source_channel or not _can_read_channel(source_channel):
			frappe.throw(_("Source message not found"))

	last = frappe.db.sql(
		"select coalesce(max(sort_order), 0) from `tabAS Task` where project = %s and status = %s",
		(project, status),
	)[0][0]
	task = frappe.get_doc(
		{
			"doctype": "AS Task",
			"project": project,
			"title": title,
			"description": description,
			"status": status,
			"priority": priority,
			"assignee": assignee or None,
			"reporter": me,
			"due_date": getdate(due_date) if due_date else None,
			"labels": labels,
			"source_message": source_message,
			"files": frappe.as_json(_validate_files(proj, files)) if files else None,
			"sort_order": last + 1,
		}
	).insert(ignore_permissions=True)

	post_system_message(proj.channel, _("{0} created {1}").format(get_fullname(me), _task_label(task)))
	if task.assignee and task.assignee != me:
		push(
			task.assignee,
			"Assignment",
			from_user=me,
			channel=proj.channel,
			task=task.name,
			preview=_("assigned you {0}").format(_task_label(task)),
		)
	return broadcast(task.name)


@frappe.whitelist(methods=["POST"])
def update_task(task: str, **values):
	me = require_login()
	doc = frappe.get_doc("AS Task", task)
	proj = check_project_member(doc.project)

	values = {k: v for k, v in values.items() if k in EDITABLE}
	if "assignee" in values:
		values["assignee"] = values["assignee"] or None
		_validate_assignee(proj, values["assignee"])
	if "priority" in values and values["priority"] not in PRIORITIES:
		frappe.throw(_("Invalid priority"))
	if "due_date" in values:
		values["due_date"] = getdate(values["due_date"]) if values["due_date"] else None
	if "files" in values:
		values["files"] = frappe.as_json(_validate_files(proj, values["files"], existing=doc.get_files()))
	if isinstance(values.get("labels"), list):
		values["labels"] = ", ".join(values["labels"])

	old_status, old_assignee = doc.status, doc.assignee
	if "status" in values and values["status"] != old_status:
		# moved to another column: append at its end
		values["sort_order"] = frappe.db.sql(
			"select coalesce(max(sort_order), 0) + 1 from `tabAS Task` where project = %s and status = %s",
			(doc.project, values["status"]),
		)[0][0]
	doc.update(values)
	doc.save(ignore_permissions=True)

	if doc.assignee and doc.assignee != old_assignee and doc.assignee != me:
		push(
			doc.assignee,
			"Assignment",
			from_user=me,
			channel=proj.channel,
			task=doc.name,
			preview=_("assigned you {0}").format(_task_label(doc)),
		)
	if doc.status != old_status:
		if doc.status == "Done":
			post_system_message(
				proj.channel, _("{0} completed {1}").format(get_fullname(me), _task_label(doc))
			)
		for user in {doc.assignee, doc.reporter} - {me, None}:
			push(
				user,
				"Task Update",
				from_user=me,
				channel=proj.channel,
				task=doc.name,
				preview=_("moved {0} to {1}").format(_task_label(doc), doc.status),
			)
	return broadcast(doc.name)


@frappe.whitelist(methods=["POST"])
def reorder(project: str, status: str, tasks):
	"""Persist the order of a board column after a drag and drop."""
	check_project_member(project)
	if status not in STATUSES:
		frappe.throw(_("Invalid status"))
	tasks = frappe.parse_json(tasks) if isinstance(tasks, str) else tasks
	valid = set(
		frappe.get_all("AS Task", filters={"project": project, "name": ("in", tasks or [""])}, pluck="name")
	)
	for index, name in enumerate(t for t in tasks if t in valid):
		frappe.db.set_value("AS Task", name, "sort_order", index + 1, update_modified=False)
	channel = frappe.db.get_value("AS Project", project, "channel")
	publish_to_channel(channel, "as_task_reorder", {"project": project, "status": status, "tasks": tasks})


@frappe.whitelist(methods=["POST"])
def delete_task(task: str):
	me = require_login()
	doc = frappe.get_doc("AS Task", task)
	proj = check_project_member(doc.project)
	if doc.reporter != me and proj.my_role != "Admin":
		frappe.throw(_("Only the reporter or a project admin can delete a task"), frappe.PermissionError)
	payload = {"name": doc.name, "project": doc.project}
	frappe.db.delete("Comment", {"reference_doctype": "AS Task", "reference_name": doc.name})
	frappe.db.delete("AS Notification", {"task": doc.name})
	frappe.delete_doc("AS Task", doc.name, ignore_permissions=True)
	publish_to_channel(proj.channel, "as_task_delete", payload)


@frappe.whitelist(methods=["POST"])
def add_comment(task: str, content: str):
	me = require_login()
	doc = frappe.get_doc("AS Task", task)
	proj = check_project_member(doc.project)
	content = (content or "").strip()
	if not content:
		frappe.throw(_("Comment cannot be empty"))

	comment = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "AS Task",
			"reference_name": task,
			"content": content,
			"comment_email": me,
			"comment_by": get_fullname(me),
		}
	).insert(ignore_permissions=True)

	preview = plain_preview(content)
	mentioned = {u for u in mentioned_users(content) if get_member(proj.channel, u)}
	for user in mentioned - {me}:
		push(user, "Mention", from_user=me, channel=proj.channel, task=task, preview=f"{doc.name}: {preview}")
	for user in {doc.assignee, doc.reporter} - mentioned - {me, None}:
		push(
			user,
			"Task Update",
			from_user=me,
			channel=proj.channel,
			task=task,
			preview=f"commented on {doc.name}: {preview}",
		)

	broadcast(task)
	return {
		"name": comment.name,
		"owner": me,
		"content": unescape(comment.content),
		"creation": str(comment.creation),
	}


def _validate_files(project, files, existing=None) -> list[dict]:
	"""New attachments must be uploads to the project channel by this user; existing ones may be kept."""
	names = frappe.parse_json(files) if isinstance(files, str) else (files or [])
	kept = {f["name"]: f for f in (existing or [])}
	result = []
	for item in names:
		name = item.get("name") if isinstance(item, dict) else item
		if name in kept:
			result.append(kept[name])
			continue
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
			or file.attached_to_name != project.channel
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
