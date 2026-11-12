"""Move AS Time Log entries into ERPNext Timesheets (one draft sheet per employee per day)."""

import frappe

from aeraspace.hr import employee_for, ensure_employee
from aeraspace.timesheets import ENTRIES, add_entry


def execute():
	if "erpnext" not in frappe.get_installed_apps() or not frappe.db.table_exists("AS Time Log"):
		return

	logs = frappe.db.sql("select * from `tabAS Time Log` order by log_date, creation", as_dict=True)
	expected = {}
	for row in logs:
		if not employee_for(row.user):
			ensure_employee(row.user)
		add_entry(row.user, row.project, row.minutes, row.log_date, row.task, row.description)
		expected[row.user] = expected.get(row.user, 0) + row.minutes

	for user, minutes in expected.items():
		moved = frappe.db.sql(f"select coalesce(sum(minutes), 0) from {ENTRIES} l where l.user = %s", user)[
			0
		][0]
		if moved < minutes:
			frappe.throw(
				f"Time log migration incomplete for {user}: {moved}/{minutes} minutes. Old table kept."
			)

	frappe.delete_doc("DocType", "AS Time Log", force=True, ignore_missing=True, ignore_permissions=True)
	frappe.db.sql_ddl("drop table if exists `tabAS Time Log`")
