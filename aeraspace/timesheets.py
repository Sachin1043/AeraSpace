"""AeraSpace time entries stored as ERPNext Timesheets.

Each employee gets one draft Timesheet per day; every entry is a Timesheet Detail row in it. People log a
duration, not clock times, so rows are laid out back to back from DAY_START. That keeps ERPNext's overlap
check happy and makes the day read naturally in Desk. Sheets stay in draft: submitting one in Desk locks
its entries (and makes ERPNext move tasks to Working/Completed), so AeraSpace never submits.
"""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, today

from aeraspace.hr import employee_for

DAY_START = time(9, 0)
MAX_MINUTES_PER_ENTRY = 24 * 60
MAX_MINUTES_PER_DAY = 24 * 60

# every non-cancelled entry, in the columns the old AS Time Log table had
ENTRIES = """(select d.name, ts.user, date(d.from_time) as log_date, d.project, d.task,
		cast(round(d.hours * 60) as signed) as minutes, d.description, d.creation, d.from_time
	from `tabTimesheet Detail` d join `tabTimesheet` ts on ts.name = d.parent
	where d.parenttype = 'Timesheet' and d.parentfield = 'time_logs' and ts.docstatus < 2)"""


def get_entry(name: str):
	return frappe.db.sql(f"select * from {ENTRIES} l where l.name = %s", name, as_dict=True)[0]


def add_entry(user, project, minutes, log_date, task=None, description=None) -> str:
	"""Add a time entry for `user` and return its name."""
	log_date = getdate(log_date or today())
	minutes = cint(minutes)
	_validate(project, task, minutes, log_date)
	employee = _lock_employee(user)
	sheet = _day_sheet(employee, user, log_date)
	row = sheet.append(
		"time_logs",
		{"project": project, "task": task or None, "description": (description or "").strip()},
	)
	row.as_minutes = minutes
	_lay_out(sheet, log_date)
	sheet.save(ignore_permissions=True)
	return row.name


def update_entry(name, user, values) -> str:
	"""Change an entry; returns its (possibly new) name. Moving it to another day moves it to that day's sheet."""
	sheet, row = _own_row(name, user)
	current = get_entry(name)
	merged = {
		"project": current.project,
		"task": current.task,
		"minutes": current.minutes,
		"log_date": current.log_date,
		"description": current.description,
		**values,
	}
	merged["minutes"] = cint(merged["minutes"])
	merged["log_date"] = getdate(merged["log_date"])
	merged["task"] = merged["task"] or None

	if merged["log_date"] != getdate(current.log_date):
		_remove_row(sheet, row)
		return add_entry(
			user,
			merged["project"],
			merged["minutes"],
			merged["log_date"],
			merged["task"],
			merged["description"],
		)

	_validate(merged["project"], merged["task"], merged["minutes"], merged["log_date"])
	_lock_employee(user)
	row.project = merged["project"]
	row.task = merged["task"]
	row.description = (merged["description"] or "").strip()
	row.as_minutes = merged["minutes"]
	_lay_out(sheet, merged["log_date"])
	sheet.save(ignore_permissions=True)
	return row.name


def delete_entry(name, user):
	sheet, row = _own_row(name, user)
	_remove_row(sheet, row)


def logged_minutes_on_task(task: str) -> int:
	return cint(
		frappe.db.sql(f"select coalesce(sum(l.minutes), 0) from {ENTRIES} l where l.task = %s", task)[0][0]
	)


def _validate(project, task, minutes, log_date):
	if minutes <= 0:
		frappe.throw(_("Duration must be more than zero"))
	if minutes > MAX_MINUTES_PER_ENTRY:
		frappe.throw(_("A single entry can't be more than 24 hours"))
	if log_date > getdate(today()):
		frappe.throw(_("You can't log time for a future date"))
	if task and frappe.db.get_value("Task", task, "project") != project:
		frappe.throw(_("Task {0} is not part of this project").format(task))


def _lock_employee(user) -> str:
	"""The user's Employee, locked so two entries saved at once don't create two sheets for one day."""
	employee = employee_for(user)
	if not employee:
		frappe.throw(_("You don't have an employee record yet. Please ask HR."))
	frappe.db.sql("select name from `tabEmployee` where name = %s for update", employee)
	return employee


def _day_sheet(employee, user, log_date):
	name = frappe.db.get_value(
		"Timesheet",
		{"employee": employee, "docstatus": 0, "start_date": log_date, "end_date": log_date},
		"name",
		order_by="creation asc",
	)
	if name:
		return frappe.get_doc("Timesheet", name)
	return frappe.get_doc(
		{
			"doctype": "Timesheet",
			"employee": employee,
			"user": user,
			"company": frappe.db.get_value("Employee", employee, "company"),
			"start_date": log_date,
			"end_date": log_date,
			"time_logs": [],
		}
	)


def _lay_out(sheet, log_date):
	"""Place the sheet's rows one after another, after any time already logged that day in other sheets."""
	day_start = datetime.combine(log_date, DAY_START)
	# rows of other sheets that reach into this day (a Desk entry may run past midnight)
	others = frappe.db.sql(
		"""select max(d.to_time), coalesce(sum(if(date(d.from_time) = %(date)s, d.hours, 0)), 0)
		from `tabTimesheet Detail` d join `tabTimesheet` ts on ts.name = d.parent
		where ts.employee = %(employee)s and ts.docstatus < 2 and ts.name != %(sheet)s
			and d.to_time > %(start)s and date(d.from_time) <= %(date)s""",
		{"employee": sheet.employee, "sheet": sheet.name or "", "date": log_date, "start": day_start},
	)[0]
	cursor = max(day_start, get_datetime(others[0])) if others[0] else day_start
	total = round(float(others[1]) * 60)

	for row in sheet.time_logs:
		minutes = getattr(row, "as_minutes", None) or round((row.hours or 0) * 60)
		row.from_time = cursor
		row.to_time = cursor + timedelta(minutes=minutes)
		row.hours = minutes / 60
		cursor = row.to_time
		total += minutes
	if total > MAX_MINUTES_PER_DAY:
		frappe.throw(_("You can't log more than 24 hours in a day"))


def _own_row(name, user):
	parent = frappe.db.get_value("Timesheet Detail", {"name": name, "parenttype": "Timesheet"}, "parent")
	if not parent:
		frappe.throw(_("Time entry {0} not found").format(name), frappe.DoesNotExistError)
	sheet = frappe.get_doc("Timesheet", parent)
	if sheet.user != user:
		frappe.throw(_("You can only change your own time entries"), frappe.PermissionError)
	if sheet.docstatus != 0:
		frappe.throw(_("This day's timesheet is already submitted, so its entries can't be changed"))
	row = next(r for r in sheet.time_logs if r.name == name)
	return sheet, row


def _remove_row(sheet, row):
	_lock_employee(sheet.user)
	sheet.remove(row)
	if not sheet.time_logs:
		frappe.delete_doc("Timesheet", sheet.name, ignore_permissions=True)
		return
	_lay_out(sheet, getdate(sheet.start_date))
	sheet.save(ignore_permissions=True)
