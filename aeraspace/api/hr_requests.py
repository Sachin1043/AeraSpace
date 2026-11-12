"""Leave, work-from-home and attendance-correction requests, stored as HRMS documents.

- Leave                 -> Leave Application (approved/rejected ones are submitted, as HRMS expects)
- Work from home        -> Attendance Request, reason "Work From Home"
- Attendance correction -> Attendance Request, reason "On Duty" (marks the day Present)

Requests go to the person's manager (AeraSpace profile), or to Administrator when they have none.
Attendance Requests have no approval state of their own, so AeraSpace keeps it in `as_status`.
HRMS can only mark attendance for days that have come, so a future WFH request is submitted
by `submit_due_attendance_requests` once its last day arrives.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, formatdate, get_fullname, getdate, today

from aeraspace import hr, hr_rules
from aeraspace.notifications import push
from aeraspace.permissions import is_admin
from aeraspace.utils import require_login

AR_REASON = {"wfh": "Work From Home", "correction": "On Duty"}
TITLES = {"wfh": _("Work from home"), "correction": _("Attendance correction")}
LEAVE_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"leave_type",
	"from_date",
	"to_date",
	"half_day",
	"half_day_date",
	"total_leave_days",
	"description",
	"status",
	"docstatus",
	"leave_approver",
	"as_decision_note",
	"creation",
	"modified",
]
AR_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"reason",
	"from_date",
	"to_date",
	"half_day",
	"half_day_date",
	"explanation",
	"docstatus",
	"as_status",
	"as_approver",
	"as_decision_note",
	"creation",
	"modified",
]


# ---- who approves ---------------------------------------------------------------


def approver_for(user: str) -> str:
	"""The person's manager, else Administrator."""
	manager = frappe.db.get_value("AS Employee Profile", user, "manager")
	if manager and manager != user and frappe.db.get_value("User", manager, "enabled"):
		return manager
	return "Administrator"


def _can_decide(viewer: str, row) -> bool:
	if row["user"] == viewer and viewer != "Administrator":
		return False  # nobody approves their own request (the lone Administrator excepted)
	return row["approver"] == viewer or is_admin(viewer)


# ---- rows -------------------------------------------------------------------------


def _users(employees) -> dict:
	rows = frappe.get_all(
		"Employee", filters={"name": ("in", list(employees) or [""])}, fields=["name", "user_id"]
	)
	return {r.name: r.user_id for r in rows}


def _leave_row(doc, users) -> dict:
	status = "Cancelled" if doc.docstatus == 2 else {"Open": "Pending"}.get(doc.status, doc.status)
	return {
		"name": doc.name,
		"kind": "leave",
		"title": doc.leave_type,
		"leave_type": doc.leave_type,
		"user": users.get(doc.employee),
		"full_name": doc.employee_name,
		"from_date": str(doc.from_date),
		"to_date": str(doc.to_date),
		"half_day": cint(doc.half_day),
		"half_day_date": str(doc.half_day_date) if doc.half_day_date else None,
		"days": doc.total_leave_days,
		"reason": doc.description,
		"status": status,
		"approver": doc.leave_approver,
		"note": doc.as_decision_note,
		"creation": str(doc.creation),
		"modified": str(doc.modified),
	}


def _ar_row(doc, users) -> dict:
	kind = "wfh" if doc.reason == "Work From Home" else "correction"
	if doc.docstatus == 2:
		status = doc.as_status if doc.as_status in ("Rejected", "Cancelled") else "Cancelled"
	else:
		status = {"Open": "Pending"}.get(doc.as_status or "Open", doc.as_status)
	days = date_diff(doc.to_date, doc.from_date) + 1 - (0.5 if doc.half_day else 0)
	return {
		"name": doc.name,
		"kind": kind,
		"title": TITLES[kind],
		"leave_type": None,
		"user": users.get(doc.employee),
		"full_name": doc.employee_name,
		"from_date": str(doc.from_date),
		"to_date": str(doc.to_date),
		"half_day": cint(doc.half_day),
		"half_day_date": str(doc.half_day_date) if doc.half_day_date else None,
		"days": days,
		"reason": doc.explanation,
		"status": status,
		"approver": doc.as_approver,
		"note": doc.as_decision_note,
		"creation": str(doc.creation),
		"modified": str(doc.modified),
	}


def _rows(leave_filters, ar_filters, viewer, limit=100) -> list[dict]:
	leaves = frappe.get_all(
		"Leave Application", filters=leave_filters, fields=LEAVE_FIELDS, order_by="creation desc", limit=limit
	)
	ars = frappe.get_all(
		"Attendance Request", filters=ar_filters, fields=AR_FIELDS, order_by="creation desc", limit=limit
	)
	users = _users({r.employee for r in leaves + ars})
	rows = [_leave_row(r, users) for r in leaves] + [_ar_row(r, users) for r in ars]
	for row in rows:
		row["approver_name"] = get_fullname(row["approver"]) if row["approver"] else None
		row["can_decide"] = row["status"] == "Pending" and _can_decide(viewer, row)
		row["can_cancel"] = row["user"] == viewer and (
			row["status"] == "Pending"
			or (row["status"] == "Approved" and getdate(row["from_date"]) >= getdate(today()))
		)
	rows.sort(key=lambda r: r["creation"], reverse=True)
	return rows[:limit]


def _get(kind: str, name: str):
	doctype = "Leave Application" if kind == "leave" else "Attendance Request"
	doc = frappe.get_doc(doctype, name)
	users = _users([doc.employee])
	row = _leave_row(doc, users) if kind == "leave" else _ar_row(doc, users)
	return doc, row


def _when(row) -> str:
	start, end = formatdate(row["from_date"], "d MMM"), formatdate(row["to_date"], "d MMM")
	return start if start == end else f"{start} - {end}"


def _refresh(*users):
	for user in {u for u in users if u}:
		frappe.publish_realtime("as_requests", {}, user=user, after_commit=True)


# ---- endpoints ----------------------------------------------------------------------


@frappe.whitelist()
def get_options():
	user = require_login()
	employee = hr.employee_for(user)
	year_start = f"{getdate(today()).year}-01-01"
	taken = frappe.db.sql(
		"""select leave_type, sum(total_leave_days) as days from `tabLeave Application`
		where employee = %s and status = 'Approved' and docstatus = 1 and from_date >= %s
		group by leave_type""",
		(employee or "", year_start),
		as_dict=True,
	)
	approver = approver_for(user)
	leave_types = [t for t in hr.LEAVE_TYPES if frappe.db.exists("Leave Type", t)]
	return {
		"enabled": bool(employee),
		"leave_types": leave_types,
		"taken_this_year": {r.leave_type: r.days for r in taken},
		"balances": _balances(employee, leave_types) if employee else {},
		"notice_days": hr_rules.NOTICE_DAYS,
		"approver": approver,
		"approver_name": get_fullname(approver),
		"can_approve": is_admin(user) or bool(frappe.db.exists("AS Employee Profile", {"manager": user})),
		"pending_approvals": _pending_count(user),
	}


def _balances(employee, leave_types) -> dict:
	"""Days left of each paid leave type today (Leave Without Pay has no balance)."""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	return {
		t: get_leave_balance_on(employee, t, today(), consider_all_leaves_in_the_allocation_period=True)
		for t in leave_types
		if t in hr_rules.ANNUAL_LEAVE
	}


def _check_balance(employee, leave_type, from_date, to_date, half_day, half_day_date):
	if leave_type not in hr_rules.ANNUAL_LEAVE:
		return
	from hrms.hr.doctype.leave_application.leave_application import (
		get_leave_balance_on,
		get_number_of_leave_days,
	)

	days = get_number_of_leave_days(employee, leave_type, from_date, to_date, half_day, half_day_date)
	left = get_leave_balance_on(
		employee, leave_type, from_date, to_date, consider_all_leaves_in_the_allocation_period=True
	)
	if days > left:
		frappe.throw(
			_(
				"You have {0} day(s) of {1} left and this needs {2}. Apply {0} as {1} and the rest as Leave Without Pay."
			).format(frappe.utils.flt(left, 1), leave_type, frappe.utils.flt(days, 1))
		)


def _pending_count(user) -> int:
	return len([r for r in _approval_rows(user) if r["can_decide"]])


def _approval_rows(user):
	if is_admin(user):
		return _rows({"status": "Open", "docstatus": 0}, {"docstatus": 0, "as_status": "Open"}, user)
	return _rows(
		{"status": "Open", "docstatus": 0, "leave_approver": user},
		{"docstatus": 0, "as_status": "Open", "as_approver": user},
		user,
	)


@frappe.whitelist()
def get_my_requests():
	user = require_login()
	employee = hr.employee_for(user)
	if not employee:
		return []
	return _rows({"employee": employee}, {"employee": employee}, user, limit=50)


@frappe.whitelist()
def get_approvals():
	"""Requests waiting for me, plus the ones I decided in the last 30 days."""
	user = require_login()
	pending = [r for r in _approval_rows(user) if r["can_decide"]]
	since = frappe.utils.add_days(today(), -30)
	decided = _rows(
		{"leave_approver": user, "status": ("in", ("Approved", "Rejected")), "modified": (">=", since)},
		{"as_approver": user, "as_status": ("in", ("Approved", "Rejected")), "modified": (">=", since)},
		user,
		limit=30,
	)
	return {"pending": pending, "decided": [r for r in decided if r["user"] != user]}


@frappe.whitelist(methods=["POST"])
def apply(
	kind: str,
	from_date: str,
	to_date: str | None = None,
	reason: str | None = None,
	leave_type: str | None = None,
	half_day: int = 0,
	half_day_date: str | None = None,
):
	user = require_login()
	employee = hr.employee_for(user)
	if not employee:
		frappe.throw(_("You don't have an employee record yet. Please ask HR."))
	from_date, to_date = getdate(from_date), getdate(to_date or from_date)
	if to_date < from_date:
		frappe.throw(_("The end date can't be before the start date"))
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please add a reason"))
	half_day = cint(half_day)
	half_day_date = getdate(half_day_date or from_date) if half_day else None
	approver = approver_for(user)
	company = frappe.db.get_value("Employee", employee, "company")

	if kind == "leave":
		if leave_type not in hr.LEAVE_TYPES:
			frappe.throw(_("Please pick a leave type"))
		notice = hr_rules.notice_error(leave_type, from_date)
		if notice:
			frappe.throw(notice)
		_check_balance(employee, leave_type, from_date, to_date, half_day, half_day_date)
		doc = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": employee,
				"company": company,
				"leave_type": leave_type,
				"from_date": from_date,
				"to_date": to_date,
				"half_day": half_day,
				"half_day_date": half_day_date,
				"description": reason,
				"leave_approver": approver,
				"status": "Open",
				"posting_date": today(),
				"follow_via_email": 0,
			}
		)
	elif kind in AR_REASON:
		if kind == "correction" and to_date > getdate(today()):
			frappe.throw(_("You can only correct today or earlier days"))
		doc = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": employee,
				"company": company,
				"from_date": from_date,
				"to_date": to_date,
				"half_day": half_day,
				"half_day_date": half_day_date,
				"reason": AR_REASON[kind],
				"explanation": reason,
				"as_approver": approver,
				"as_status": "Open",
			}
		)
	else:
		frappe.throw(_("Unknown request type"))

	doc.insert(ignore_permissions=True)
	frappe.clear_messages()  # HRMS warnings (e.g. no leave balance yet) aren't for this screen
	_doc, row = _get(kind, doc.name)
	push(
		approver, "Request", from_user=user, preview=_("requested {0} · {1}").format(row["title"], _when(row))
	)
	_refresh(user, approver)
	return row


@frappe.whitelist(methods=["POST"])
def decide(kind: str, name: str, approve: int, note: str | None = None):
	user = require_login()
	doc, row = _get(kind, name)
	if not _can_decide(user, row):
		frappe.throw(_("Only the approver or an admin can decide this request"), frappe.PermissionError)
	if row["status"] != "Pending":
		frappe.throw(_("This request has already been {0}").format(row["status"].lower()))
	approve = cint(approve)
	note = (note or "").strip() or None
	doc.flags.ignore_permissions = True

	if kind == "leave":
		doc.status = "Approved" if approve else "Rejected"
		doc.as_decision_note = note
		doc.submit()
	elif approve:
		doc.as_status = "Approved"
		doc.as_decision_note = note
		if getdate(doc.to_date) <= getdate(today()):
			doc.submit()
		else:
			doc.save()  # submitted on its last day by submit_due_attendance_requests
	else:
		doc.db_set({"as_status": "Rejected", "as_decision_note": note, "as_approver": user})
		doc.discard()
	frappe.clear_messages()

	verb = _("approved") if approve else _("rejected")
	preview = _("{0} your {1} request · {2}").format(verb, row["title"], _when(row))
	push(row["user"], "Request", from_user=user, preview=preview + (f" — {note}" if note else ""))
	_refresh(user, row["user"], row["approver"])
	return _get(kind, name)[1]


@frappe.whitelist(methods=["POST"])
def cancel(kind: str, name: str):
	user = require_login()
	doc, row = _get(kind, name)
	if row["user"] != user:
		frappe.throw(_("You can only cancel your own requests"), frappe.PermissionError)
	if row["status"] == "Approved" and getdate(row["from_date"]) < getdate(today()):
		frappe.throw(_("This has already started. Ask HR to change it."))
	if row["status"] not in ("Pending", "Approved"):
		frappe.throw(_("This request is already {0}").format(row["status"].lower()))
	doc.flags.ignore_permissions = True
	if doc.docstatus == 1:
		doc.cancel()
	else:
		if kind != "leave":
			doc.db_set("as_status", "Cancelled")
		doc.discard()
	frappe.clear_messages()
	if row["status"] == "Approved" and row["approver"] != user:
		push(
			row["approver"],
			"Request",
			from_user=user,
			preview=_("cancelled their {0} · {1}").format(row["title"], _when(row)),
		)
	_refresh(user, row["approver"])
	return _get(kind, name)[1]


def submit_due_attendance_requests():
	"""Daily: approved future WFH requests become HRMS attendance once their days have come."""
	for name in frappe.get_all(
		"Attendance Request",
		filters={"docstatus": 0, "as_status": "Approved", "to_date": ("<=", today())},
		pluck="name",
	):
		doc = frappe.get_doc("Attendance Request", name)
		doc.flags.ignore_permissions = True
		try:
			doc.submit()
			frappe.db.commit()  # one request failing shouldn't undo the others
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Could not submit Attendance Request {name}")


# ---- for the attendance calendar --------------------------------------------------------


def approved_marks(employee: str, from_date, to_date) -> dict:
	"""{date: "On Leave" | "Half Day Leave" | "Work From Home" | "Corrected"} from approved requests."""
	marks = {}
	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"status": "Approved",
			"docstatus": 1,
			"from_date": ("<=", to_date),
			"to_date": (">=", from_date),
		},
		fields=["from_date", "to_date", "half_day", "half_day_date"],
	)
	requests = frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"as_status": "Approved",
			"docstatus": ("<", 2),
			"from_date": ("<=", to_date),
			"to_date": (">=", from_date),
		},
		fields=["from_date", "to_date", "reason"],
	)
	for r in requests:
		for day in _days(r.from_date, r.to_date):
			marks[day] = "Work From Home" if r.reason == "Work From Home" else "Corrected"
	for r in leaves:
		for day in _days(r.from_date, r.to_date):
			half = r.half_day and r.half_day_date and getdate(r.half_day_date) == day
			marks[day] = "Half Day Leave" if half else "On Leave"
	return marks


def _days(start, end):
	start, end = getdate(start), getdate(end)
	return [frappe.utils.add_days(start, i) for i in range(date_diff(end, start) + 1)]
