"""Aerele's HR rules, in one place, applied through HRMS.

- Working week: Monday to Friday. Saturday and Sunday are weekly offs; festivals are in the holiday list.
- Late: checking in more than 15 minutes after 9:00 (the shift's grace period). Every 3rd late day in a
  month is marked as a half day in HRMS attendance.
- Half day / absent: under 4h worked is a half day, under 2h absent (the General Shift thresholds).
- Forgot to check out: the day is closed at shift end (6 PM) with an automatic check-out, and flagged so
  the person can ask for a correction.
- Leave per year: Casual 12, Sick 6, Privilege 12 (pro-rata for people who join mid-year). Only
  Privilege Leave carries forward. No leave beyond the balance (the rest is Leave Without Pay).
  Casual and Privilege Leave need a day's notice; Sick Leave can be applied the same day or after.
- Overtime: time worked beyond 9h in a day is shown, not paid.
"""

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today

WEEKLY_OFFS = ("Saturday", "Sunday")
LATE_DAYS_PER_HALF_DAY = 3
OVERTIME_AFTER_SECONDS = 9 * 3600
LEAVE_POLICY = "Aerele Standard"
ANNUAL_LEAVE = {"Casual Leave": 12, "Sick Leave": 6, "Privilege Leave": 12}
CARRY_FORWARD = ("Privilege Leave",)
NOTICE_DAYS = {"Casual Leave": 1, "Privilege Leave": 1}

# Tamil Nadu holidays for April 2026 - March 2027. Festivals that follow the moon (marked *) can move
# by a day; HR confirms them in Desk (Holiday List) once the government list is out.
FESTIVALS = {
	"2026-04-03": "Good Friday",
	"2026-04-14": "Tamil New Year",
	"2026-05-01": "May Day",
	"2026-05-27": "Bakrid *",
	"2026-08-15": "Independence Day",
	"2026-09-04": "Krishna Jayanthi *",
	"2026-09-14": "Vinayagar Chathurthi *",
	"2026-10-02": "Gandhi Jayanti",
	"2026-10-19": "Ayudha Pooja *",
	"2026-10-20": "Vijayadasami *",
	"2026-11-08": "Deepavali *",
	"2026-12-25": "Christmas",
	"2027-01-01": "New Year",
	"2027-01-15": "Pongal *",
	"2027-01-16": "Thiruvalluvar Day *",
	"2027-01-26": "Republic Day",
}


# ---- setup (idempotent; runs from hr.ensure_hr_setup) ---------------------------------------


def apply_setup(company: str, holiday_list: str):
	ensure_weekly_offs_and_festivals(holiday_list)
	ensure_leave_types()
	ensure_leave_policy()
	ensure_leave_period(company)
	clear_absent_on_holidays(holiday_list)


def ensure_weekly_offs_and_festivals(holiday_list: str):
	doc = frappe.get_doc("Holiday List", holiday_list)
	have = {getdate(h.holiday_date) for h in doc.holidays}
	start, end = getdate(doc.from_date), getdate(doc.to_date)
	day, added = start, False
	while day <= end:
		if day.strftime("%A") in WEEKLY_OFFS and day not in have:
			doc.append("holidays", {"holiday_date": day, "description": day.strftime("%A"), "weekly_off": 1})
			have.add(day)
			added = True
		day = add_days(day, 1)
	for date, name in FESTIVALS.items():
		date = getdate(date)
		if start <= date <= end and date not in have:  # a festival on a weekend is already off
			doc.append("holidays", {"holiday_date": date, "description": name, "weekly_off": 0})
			have.add(date)
			added = True
	if added:
		doc.holidays.sort(key=lambda h: getdate(h.holiday_date))
		for i, row in enumerate(doc.holidays, 1):
			row.idx = i
		doc.flags.ignore_permissions = True
		doc.save()


def ensure_leave_types():
	for leave_type, days in ANNUAL_LEAVE.items():
		frappe.db.set_value(
			"Leave Type",
			leave_type,
			{
				"allow_negative": 0,  # beyond the balance it's Leave Without Pay
				"include_holiday": 0,  # a Friday-to-Monday leave is 2 days, not 4
				"is_carry_forward": int(leave_type in CARRY_FORWARD),
				"max_leaves_allowed": days,
			},
		)


def ensure_leave_policy() -> str:
	name = frappe.db.get_value("Leave Policy", {"title": LEAVE_POLICY, "docstatus": 1}, "name")
	if name:
		return name
	policy = frappe.get_doc(
		{
			"doctype": "Leave Policy",
			"title": LEAVE_POLICY,
			"leave_policy_details": [
				{"leave_type": leave_type, "annual_allocation": days}
				for leave_type, days in ANNUAL_LEAVE.items()
			],
		}
	)
	policy.insert(ignore_permissions=True)
	policy.submit()
	return policy.name


def ensure_leave_period(company: str) -> str | None:
	"""The leave year follows the fiscal year (April to March)."""
	current = frappe.db.get_value(
		"Leave Period",
		{"company": company, "from_date": ("<=", today()), "to_date": (">=", today())},
		"name",
	)
	if current:
		return current
	fiscal_year = frappe.db.get_value(
		"Fiscal Year",
		{"year_start_date": ("<=", today()), "year_end_date": (">=", today())},
		["year_start_date", "year_end_date"],
		as_dict=True,
	)
	if not fiscal_year:
		return None
	return (
		frappe.get_doc(
			{
				"doctype": "Leave Period",
				"from_date": fiscal_year.year_start_date,
				"to_date": fiscal_year.year_end_date,
				"company": company,
				"is_active": 1,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def assign_leave_policy(employee: str):
	"""Give the employee this year's leave (HRMS pro-rates it from their joining date)."""
	company = frappe.db.get_value("Employee", employee, "company")
	period = ensure_leave_period(company)
	if not period:
		return
	start, end = frappe.db.get_value("Leave Period", period, ["from_date", "to_date"])
	if frappe.db.exists(
		"Leave Policy Assignment",
		{"employee": employee, "docstatus": 1, "effective_from": ("<=", end), "effective_to": (">=", start)},
	):
		return
	assignment = frappe.get_doc(
		{
			"doctype": "Leave Policy Assignment",
			"employee": employee,
			"leave_policy": ensure_leave_policy(),
			"assignment_based_on": "Leave Period",
			"leave_period": period,
			"effective_from": start,
			"effective_to": end,
			"carry_forward": 1,
		}
	)
	assignment.insert(ignore_permissions=True)
	assignment.submit()  # creates the Leave Allocations


def assign_leave_to_everyone():
	for employee in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
		assign_leave_policy(employee)


def clear_absent_on_holidays(holiday_list: str):
	"""HRMS marked people absent on Saturdays before they became weekly offs; undo that."""
	holidays = frappe.get_all("Holiday", filters={"parent": holiday_list}, pluck="holiday_date")
	for name in frappe.get_all(
		"Attendance",
		filters={
			"status": "Absent",
			"attendance_date": ("in", holidays or [""]),
			"docstatus": ("<", 2),
			"leave_application": ("is", "not set"),
			"attendance_request": ("is", "not set"),
		},
		pluck="name",
	):
		doc = frappe.get_doc("Attendance", name)
		doc.flags.ignore_permissions = True
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)


# ---- forgot to check out ----------------------------------------------------------------


def close_open_sessions(employee: str | None = None):
	"""Anyone still checked in from an earlier day gets an automatic check-out at that day's shift end."""
	from aeraspace.api.attendance import _shift_start, _state_of

	day_start = datetime.combine(getdate(today()), datetime.min.time())
	employees = (
		[employee] if employee else frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
	)
	for emp in employees:
		last = frappe.db.get_value(
			"Employee Checkin",
			{"employee": emp, "time": ("<", day_start)},
			["log_type", "as_reason", "time"],
			as_dict=True,
			order_by="time desc, creation desc",
		)
		if not last or _state_of(last) == "out":
			continue
		shift = _shift_start(emp, getdate(last.time))
		shift_end = shift[1] - shift[0].start_time + shift[0].end_time if shift else last.time
		out_at = max(shift_end, last.time)
		if last.log_type == "OUT":  # left on a break: close the break first
			frappe.get_doc(_checkin(emp, "IN", "Break", out_at)).insert(ignore_permissions=True)
		frappe.get_doc(_checkin(emp, "OUT", "Work", out_at)).insert(ignore_permissions=True)


def _checkin(employee, log_type, reason, time):
	return {
		"doctype": "Employee Checkin",
		"employee": employee,
		"log_type": log_type,
		"as_reason": reason,
		"as_source": "Auto",
		"time": time,
	}


# ---- late penalty ------------------------------------------------------------------------


def late_days(employee: str, from_date, to_date) -> list:
	"""Dates in the range on which the employee checked in late."""
	from aeraspace.api.attendance import _events, _shift_row, _shift_start, summarize

	row = _shift_row(employee)
	by_day = {}
	for event in _events(employee, from_date, to_date):
		by_day.setdefault(getdate(event.time), []).append(event)
	return sorted(
		day
		for day, events in by_day.items()
		if summarize(employee, day, events, _shift_start(employee, day, row))["late_seconds"]
	)


def apply_late_penalties(employee: str | None = None, until=None):
	"""Every 3rd late day of the month (up to yesterday) becomes a half day in HRMS attendance."""
	until = getdate(until or add_days(today(), -1))
	month_start = until.replace(day=1)
	employees = (
		[employee] if employee else frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
	)
	for emp in employees:
		late = late_days(emp, month_start, until)
		for day in late[LATE_DAYS_PER_HALF_DAY - 1 :: LATE_DAYS_PER_HALF_DAY]:
			_mark_half_day(emp, day)


def _mark_half_day(employee: str, day):
	existing = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": day, "docstatus": ("<", 2)},
		["name", "docstatus", "status", "as_late_penalty"],
		as_dict=True,
	)
	if existing and (existing.as_late_penalty or existing.status in ("On Leave", "Half Day")):
		return
	reason = _("Half day: 3rd late check-in this month")
	if existing:
		doc = frappe.get_doc("Attendance", existing.name)
		if doc.docstatus == 1:
			doc.db_set(
				{"status": "Half Day", "half_day_status": "Absent", "late_entry": 1, "as_late_penalty": 1}
			)
			doc.add_comment("Info", reason)
			return
	else:
		doc = frappe.new_doc("Attendance")
		doc.employee = employee
		doc.attendance_date = day
		doc.company = frappe.db.get_value("Employee", employee, "company")
	doc.update({"status": "Half Day", "half_day_status": "Absent", "late_entry": 1, "as_late_penalty": 1})
	doc.flags.ignore_permissions = True
	doc.save()
	doc.submit()
	doc.add_comment("Info", reason)


# ---- daily -------------------------------------------------------------------------------


def run_daily():
	"""Scheduler, just after midnight: close yesterday's open days, apply late penalties, new joiners' leave."""
	for step in (close_open_sessions, apply_late_penalties, assign_leave_to_everyone):
		try:
			step()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"AeraSpace HR rules: {step.__name__} failed")


def late_this_month(employee: str) -> int:
	now = now_datetime()
	return len(late_days(employee, getdate(now).replace(day=1), getdate(now)))


def overtime(worked_seconds: int) -> int:
	return max(0, int(worked_seconds) - OVERTIME_AFTER_SECONDS)


def notice_error(leave_type: str, from_date) -> str | None:
	days = NOTICE_DAYS.get(leave_type)
	if days and getdate(from_date) < getdate(add_days(today(), days)):
		return _("{0} needs {1} day's notice. If you're unwell, apply Sick Leave instead.").format(
			leave_type, days
		)
	return None
