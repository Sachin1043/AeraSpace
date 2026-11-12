"""Today at a glance for managers and admins: who's in, on a break, out, on leave; hours, EOD, time logged."""

import frappe
from frappe.utils import get_fullname, getdate, now_datetime

from aeraspace import hr, timesheets
from aeraspace.api import attendance
from aeraspace.api.hr_requests import approved_marks
from aeraspace.team import team_scope
from aeraspace.utils import require_login

# order on the dashboard: people at work first, then the ones still missing
ORDER = {"working": 0, "break": 1, "checked_out": 2, "wfh": 3, "not_in": 4, "leave": 5, "off": 6}


@frappe.whitelist()
def get_today():
	viewer = require_login()
	people, everyone = team_scope(viewer)
	if not everyone:
		people = [u for u in people if u != viewer]  # a manager's own day is on their Home page
	if not people:
		return {"allowed": False}

	now = now_datetime()
	day = getdate(now)
	employees = {
		r.user_id: r
		for r in frappe.get_all(
			"Employee",
			filters={"user_id": ("in", people), "status": "Active"},
			fields=["name", "user_id", "employee_name", "designation", "department"],
		)
	}
	eod_done = set(
		frappe.get_all("AS Daily Update", filters={"update_date": day, "user": ("in", people)}, pluck="user")
	)
	logged = dict(
		frappe.db.sql(
			f"""select l.user, sum(l.minutes) from {timesheets.ENTRIES} l
			where l.log_date = %s and l.user in %s group by l.user""",
			(day, people),
		)
	)
	any_employee = next(iter(employees.values()), None)
	holiday = any_employee and attendance._holidays(any_employee.name, day, day).get(day)

	rows = []
	for user in people:
		employee = employees.get(user)
		if not employee:
			continue
		state, _event = attendance._current(employee.name, now)
		summary = attendance.summarize(employee.name, day)
		mark = approved_marks(employee.name, day, day).get(day)
		if state != "out":
			status = state
		elif summary["first_in"]:
			status = "checked_out"
		elif mark == "On Leave":
			status = "leave"
		elif mark == "Work From Home":
			status = "wfh"
		elif holiday:
			status = "off"
		else:
			status = "not_in"
		rows.append(
			{
				"user": user,
				"full_name": employee.employee_name or get_fullname(user),
				"designation": employee.designation,
				"status": status,
				"mark": mark,
				"today": summary,
				"eod": user in eod_done,
				"logged_minutes": int(logged.get(user) or 0),
			}
		)
	rows.sort(key=lambda r: (ORDER[r["status"]], r["full_name"].lower()))

	counts = {status: sum(1 for r in rows if r["status"] == status) for status in ORDER}
	counts["late"] = sum(1 for r in rows if r["today"]["late_seconds"])
	counts["eod"] = sum(1 for r in rows if r["eod"])
	return {
		"allowed": True,
		"date": str(day),
		"server_now": str(now),
		"holiday": holiday.description if holiday else None,
		"expected_seconds": hr.EXPECTED_SECONDS,
		"everyone": everyone,
		"rows": rows,
		"counts": counts,
		"total": len(rows),
	}
