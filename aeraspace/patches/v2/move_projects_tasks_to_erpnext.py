"""Move AS Project / AS Task to ERPNext Project / Task, keeping names (GE, GE-1) so every link stays valid."""

import frappe

from aeraspace.hr import default_company
from aeraspace.projects import ensure_custom_fields, set_assignee


def execute():
	if "erpnext" not in frappe.get_installed_apps() or not frappe.db.table_exists("AS Project"):
		return
	ensure_custom_fields()
	company = default_company()

	projects = frappe.db.sql("select * from `tabAS Project` order by creation", as_dict=True)
	tasks = frappe.db.sql("select * from `tabAS Task` order by creation", as_dict=True)

	for row in projects:
		if frappe.db.exists("Project", row.name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": row.project_name,
				"company": company,
				"notes": row.description,
				"as_project_key": row.project_key,
				"as_status": row.status or "Active",
				"as_visibility": row.visibility or "Private",
				"as_lead": row.lead,
				"as_client": row.client,
				"as_channel": row.channel,
				"as_last_task_number": row.last_task_number or 0,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(set_name=row.name)
		_keep_audit(doc, row)

	for row in tasks:
		if frappe.db.exists("Task", row.name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": row.title,
				"project": row.project,
				"as_status": row.status or "Todo",
				"priority": row.priority or "Medium",
				"description": row.description,
				"exp_end_date": row.due_date,
				"as_assignee": row.assignee,
				"as_reporter": row.reporter,
				"as_labels": row.labels,
				"as_files": row.files,
				"as_source_message": row.source_message,
				"as_sort_order": row.sort_order or 0,
				"completed_on": row.completed_on and frappe.utils.getdate(row.completed_on),
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.from_project = True  # recalculated once per project below
		doc.insert(set_name=row.name)
		_keep_audit(doc, row)
		if row.assignee:
			set_assignee(doc.name, row.assignee)

	frappe.db.sql("update `tabComment` set reference_doctype = 'Task' where reference_doctype = 'AS Task'")
	frappe.db.sql("update `tabVersion` set ref_doctype = 'Task' where ref_doctype = 'AS Task'")

	moved_projects = frappe.db.count("Project", {"name": ("in", [p.name for p in projects] or [""])})
	moved_tasks = frappe.db.count("Task", {"name": ("in", [t.name for t in tasks] or [""])})
	if (moved_projects, moved_tasks) != (len(projects), len(tasks)):
		frappe.throw(
			f"Project/task migration incomplete: {moved_projects}/{len(projects)} projects, "
			f"{moved_tasks}/{len(tasks)} tasks. Old tables kept."
		)

	for doctype in ("AS Task", "AS Project"):
		frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True, ignore_permissions=True)
		frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")


def _keep_audit(doc, row):
	"""Keep the original author and dates instead of 'Administrator, today'."""
	frappe.db.set_value(
		doc.doctype,
		doc.name,
		{
			"owner": row.owner,
			"creation": row.creation,
			"modified": row.modified,
			"modified_by": row.modified_by,
		},
		update_modified=False,
	)
