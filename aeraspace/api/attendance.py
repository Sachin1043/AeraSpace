"""Check in / break / check out, stored as HRMS Employee Checkin events.

Each click adds one insert-only event; HRMS turns a day's events into Attendance.
The person's state comes from their latest event:
	nothing / OUT (Work)  -> "out"
	IN (Work or Break)    -> "working"
	OUT (Break)           -> "break"
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, now_datetime

from aeraspace import hr
from aeraspace.api.hr_requests import approved_marks
from aeraspace.team import can_view
from aeraspace.utils import require_login

FIELDS = ["name", "log_type", "as_reason", "time"]


def _state_of(event) -> str:
	if not event or (event.log_type == "OUT" and event.as_reason != "Break"):
		return "out"
	return "break" if event.log_type == "OUT" else "working"


def _last_event(employee):
	return frappe.db.get_value(
		"Employee Checkin", {"employee": employee}, FIELDS, as_dict=True, order_by="time desc, creation desc"
	)


def _current(employee, now):
	"""(state, last event). A session left open on an earlier day doesn't carry into today."""
	event = _last_event(employee)
	state = _state_of(event)
	if state != "out" and getdate(event.time) < getdate(now):
		return "out", event
	return state, event


SHIFT_FIELDS = [
	"name",
	"start_time",
	"end_time",
	"enable_late_entry_marking",
	"late_entry_grace_period",
	"working_hours_threshold_for_half_day",
	"working_hours_threshold_for_absent",
]


def _shift_row(employee):
	shift = frappe.db.get_value("Employee", employee, "default_shift") or hr.DEFAULT_SHIFT
	return frappe.db.get_value("Shift Type", shift, SHIFT_FIELDS, as_dict=True)


def _shift_start(employee, day, row=None):
	row = row or _shift_row(employee)
	if not row:
		return None
	return row, datetime.combine(getdate(day), datetime.min.time()) + row.start_time


def _events(employee, from_date, to_date):
	start = datetime.combine(getdate(from_date), datetime.min.time())
	end = datetime.combine(getdate(to_date), datetime.min.time()) + timedelta(days=1)
	return frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ("between", (start, end))},
		fields=FIELDS,
		order_by="time asc, creation asc",
	)


def summarize(employee, day=None, events=None, shift=None):
	"""A day's numbers from its events: worked, break, late, first in / last out.
	Time still running (working / on break) is left to the browser, from `since`."""
	day = getdate(day or now_datetime())
	if events is None:
		events = _events(employee, day, day)

	worked = breaks = 0
	opened = break_started = None
	for event in events:
		if event.log_type == "IN":
			if break_started:
				breaks += (event.time - break_started).total_seconds()
				break_started = None
			opened = opened or event.time
		else:
			if opened:
				worked += (event.time - opened).total_seconds()
				opened = None
			if event.as_reason == "Break":
				break_started = event.time

	first_in = next((e.time for e in events if e.log_type == "IN"), None)
	last_out = next(
		(e.time for e in reversed(events) if e.log_type == "OUT" and e.as_reason != "Break"), None
	)

	late = 0
	shift = shift or _shift_start(employee, day)
	if shift and first_in:
		row, shift_start = shift
		grace = timedelta(minutes=row.late_entry_grace_period or 0)
		shift_end = shift_start - row.start_time + row.end_time
		# a first check-in after the shift has ended is off-shift work, not lateness
		if row.enable_late_entry_marking and shift_start + grace < first_in < shift_end:
			late = (first_in - shift_start).total_seconds()

	return {
		"date": str(day),
		"first_in": str(first_in) if first_in else None,
		"last_out": str(last_out) if last_out else None,
		"worked_seconds": int(worked),
		"break_seconds": int(breaks),
		"expected_seconds": hr.EXPECTED_SECONDS,
		"late_seconds": int(late),
		"shift": shift[0].name if shift else None,
		"shift_start": str(shift[1].time()) if shift else None,
		# still checked in (or on a break) at the end of the day's events
		"open": bool(events) and _state_of(events[-1]) != "out",
	}


def _state(user):
	employee = hr.employee_for(user)
	if not employee:
		return {"enabled": False}
	now = now_datetime()
	state, event = _current(employee, now)
	missed = event and state == "out" and _state_of(event) != "out"
	return {
		"enabled": True,
		"state": state,
		"since": str(event.time) if event and state != "out" else None,
		"missed_checkout": str(getdate(event.time)) if missed else None,
		"server_now": str(now),  # lets the browser correct for clock differences
		"today": summarize(employee, getdate(now)),
	}


def _log(log_type, reason):
	"""Add one event for the current user, after checking the step is allowed."""
	user = require_login()
	employee = hr.employee_for(user)
	if not employee:
		frappe.throw(_("You don't have an employee record yet. Please ask HR."))

	now = now_datetime()
	state, _event = _current(employee, now)
	target = {("IN", "Work"): "working", ("IN", "Break"): "working", ("OUT", "Break"): "break"}.get(
		(log_type, reason), "out"
	)
	allowed = {
		("IN", "Work"): ("out",),
		("OUT", "Break"): ("working",),
		("IN", "Break"): ("break",),
		("OUT", "Work"): ("working", "break"),
	}[(log_type, reason)]

	if state == target and state != "out":
		pass  # a repeated click (or another tab got there first): nothing to do
	elif state not in allowed:
		messages = {
			"out": _("You're not checked in."),
			"break": _("You're on a break. End it first."),
			"working": _("You're already checked in."),
		}
		frappe.throw(messages[state])
	else:
		request = getattr(frappe.local, "request", None)
		frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": employee,
				"log_type": log_type,
				"time": now,
				"as_source": "Web",
				"as_reason": reason,
				"as_ip_address": getattr(frappe.local, "request_ip", None),
				"as_user_agent": (request.headers.get("User-Agent") or "")[:500] if request else None,
			}
		).insert(ignore_permissions=True)

	result = _state(user)
	# keep every open tab of this person in sync
	frappe.publish_realtime("as_attendance", result, user=user, after_commit=True)
	return result


@frappe.whitelist()
def get_state():
	return _state(require_login())


@frappe.whitelist(methods=["POST"])
def check_in():
	return _log("IN", "Work")


@frappe.whitelist(methods=["POST"])
def start_break():
	return _log("OUT", "Break")


@frappe.whitelist(methods=["POST"])
def end_break():
	return _log("IN", "Break")


@frappe.whitelist(methods=["POST"])
def check_out():
	return _log("OUT", "Work")


MAX_HISTORY_DAYS = 62


@frappe.whitelist()
def get_history(from_date: str, to_date: str, user: str | None = None):
	"""One row per day: the day's numbers plus a status (Present, Absent, Holiday, ...)."""
	viewer = require_login()
	user = user or viewer
	if not can_view(viewer, user):
		frappe.throw(_("You can only see your own or your team's attendance"), frappe.PermissionError)
	employee = hr.employee_for(user)
	if not employee:
		frappe.throw(_("No employee record for this user"))
	from_date, to_date = getdate(from_date), getdate(to_date)
	if from_date > to_date or date_diff(to_date, from_date) >= MAX_HISTORY_DAYS:
		frappe.throw(_("Pick a range of up to {0} days").format(MAX_HISTORY_DAYS))

	today = getdate(now_datetime())
	joined = frappe.db.get_value("Employee", employee, "date_of_joining")
	row = _shift_row(employee)
	holidays = _holidays(employee, from_date, to_date)
	marks = {**_hrms_attendance(employee, from_date, to_date), **approved_marks(employee, from_date, to_date)}
	by_day = {}
	for event in _events(employee, from_date, to_date):
		by_day.setdefault(getdate(event.time), []).append(event)

	days = []
	for offset in range(date_diff(to_date, from_date) + 1):
		day = add_days(from_date, offset)
		summary = summarize(employee, day, by_day.get(day, []), _shift_start(employee, day, row))
		holiday = holidays.get(day)
		summary["holiday"] = holiday.description if holiday else None
		summary["status"] = _status(summary, day, today, joined, holiday, marks.get(day), row)
		days.append(summary)
	return {"employee": employee, "today": str(today), "days": days}


def _status(summary, day, today, joined, holiday, mark, shift):
	"""`mark` comes from approved requests (or HRMS attendance): leave, WFH, a corrected day."""
	if mark in ("On Leave", "Work From Home"):
		return mark
	if mark == "Half Day Leave":
		return "Half Day"
	if day > today:
		return "Holiday" if holiday and not holiday.weekly_off else "Weekly Off" if holiday else "Upcoming"
	if summary["first_in"] is None:
		if mark == "Corrected":
			return "Present"
		if holiday:
			return "Weekly Off" if holiday.weekly_off else "Holiday"
		if joined and day < getdate(joined):
			return "Not Joined"
		return "Not Checked In" if day == today else "Absent"
	if day == today or mark == "Corrected":
		return "Present"
	if summary["open"]:
		return "Missed Check-out"
	hours = summary["worked_seconds"] / 3600
	if (
		shift
		and shift.working_hours_threshold_for_absent
		and hours < shift.working_hours_threshold_for_absent
	):
		return "Absent"
	if (
		shift
		and shift.working_hours_threshold_for_half_day
		and hours < shift.working_hours_threshold_for_half_day
	):
		return "Half Day"
	return "Present"


def _holidays(employee, from_date, to_date):
	from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:  # HRMS v16 only looks at Holiday List Assignments; fall back to the company list
		own, company = frappe.db.get_value("Employee", employee, ["holiday_list", "company"])
		holiday_list = own or frappe.db.get_value("Company", company, "default_holiday_list")
	if not holiday_list:
		return {}
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "holiday_date": ("between", (from_date, to_date))},
		fields=["holiday_date", "description", "weekly_off"],
	)
	return {getdate(r.holiday_date): r for r in rows}


def _hrms_attendance(employee, from_date, to_date):
	"""Leave / WFH marked in HRMS for these days (also covers ones entered in Desk)."""
	rows = frappe.get_all(
		"Attendance",
		filters={"employee": employee, "docstatus": 1, "attendance_date": ("between", (from_date, to_date))},
		fields=["attendance_date", "status"],
	)
	return {getdate(r.attendance_date): r.status for r in rows}
