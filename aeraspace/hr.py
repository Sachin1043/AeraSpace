"""Bridge between AeraSpace users and Frappe HRMS.

AeraSpace stays the screen people use; HRMS owns Employees, shifts and attendance.
Everything here is idempotent, so it is safe to run again (after_migrate, new users, etc.).
"""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from aeraspace.install import AERASPACE_ROLE

DEFAULT_SHIFT = "General Shift"
EMPLOYEE_ROLE = "Employee"
# HRMS needs these on every Employee; HR corrects them later in Desk
PLACEHOLDER_GENDER = "Prefer not to say"
PLACEHOLDER_DOB = "2000-01-01"
CHECKIN_SOURCES = ("", "Web", "Mobile", "Device", "Auto", "Regularization")
# expected working time per day until the company's HR rules are configured
EXPECTED_SECONDS = 8 * 3600


def hrms_ready() -> bool:
	"""True once ERPNext + HRMS are installed and their setup wizard has run."""
	return "hrms" in frappe.get_installed_apps() and bool(
		frappe.db.get_single_value("Global Defaults", "default_company")
	)


def default_company() -> str | None:
	return frappe.db.get_single_value("Global Defaults", "default_company")


# ---- one-time company setup ---------------------------------------------------


def ensure_hr_setup():
	"""Holiday list + General Shift for the default company (safe to call repeatedly)."""
	if not hrms_ready():
		return
	company = default_company()
	holiday_list = ensure_holiday_list(company)
	ensure_default_shift(holiday_list)
	ensure_checkin_fields()


def ensure_holiday_list(company: str) -> str:
	"""Current fiscal year, with Sundays as weekly off. HR can add festivals in Desk."""
	existing = frappe.db.get_value("Company", company, "default_holiday_list")
	if existing:
		return existing

	fiscal_year = frappe.db.get_value(
		"Fiscal Year",
		{"year_start_date": ("<=", today()), "year_end_date": (">=", today())},
		["name", "year_start_date", "year_end_date"],
		as_dict=True,
	)
	start = fiscal_year.year_start_date if fiscal_year else getdate(f"{getdate().year}-01-01")
	end = fiscal_year.year_end_date if fiscal_year else getdate(f"{getdate().year}-12-31")
	name = f"{company} {start.year}-{end.year}"

	if not frappe.db.exists("Holiday List", name):
		holiday_list = frappe.get_doc(
			{"doctype": "Holiday List", "holiday_list_name": name, "from_date": start, "to_date": end}
		)
		holiday_list.weekly_off = "Sunday"
		holiday_list.get_weekly_off_dates()
		holiday_list.insert(ignore_permissions=True)

	frappe.db.set_value("Company", company, "default_holiday_list", name)
	return name


def ensure_default_shift(holiday_list: str | None = None) -> str:
	if frappe.db.exists("Shift Type", DEFAULT_SHIFT):
		return DEFAULT_SHIFT
	frappe.get_doc(
		{
			"doctype": "Shift Type",
			"name": DEFAULT_SHIFT,
			"start_time": "09:00:00",
			"end_time": "18:00:00",
			"holiday_list": holiday_list,
			"determine_check_in_and_check_out": "Strictly based on Log Type in Employee Checkin",
			"working_hours_calculation_based_on": "Every Valid Check-in and Check-out",
			"working_hours_threshold_for_half_day": 4,
			"working_hours_threshold_for_absent": 2,
			"begin_check_in_before_shift_start_time": 60,
			"allow_check_out_after_shift_end_time": 60,
			"enable_late_entry_marking": 1,
			"late_entry_grace_period": 15,
			"enable_early_exit_marking": 1,
			"early_exit_grace_period": 15,
			"enable_auto_attendance": 1,
			# web check-ins arrive live, so HRMS may process up to "now"
			"auto_update_last_sync": 1,
			"process_attendance_after": add_days(today(), -1),
		}
	).insert(ignore_permissions=True)
	return DEFAULT_SHIFT


def ensure_checkin_fields():
	"""Extra audit details AeraSpace records on every HRMS Employee Checkin."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Employee Checkin": [
				{
					"fieldname": "as_source",
					"label": "Source",
					"fieldtype": "Select",
					"options": "\n".join(CHECKIN_SOURCES),
					"insert_after": "log_type",
					"read_only": 1,
					"in_list_view": 1,
				},
				{
					"fieldname": "as_reason",
					"label": "Reason",
					"fieldtype": "Select",
					"options": "\nWork\nBreak",
					"insert_after": "as_source",
					"read_only": 1,
					"in_list_view": 1,
				},
				{
					"fieldname": "as_ip_address",
					"label": "IP Address",
					"fieldtype": "Data",
					"insert_after": "device_id",
					"read_only": 1,
				},
				{
					"fieldname": "as_user_agent",
					"label": "User Agent",
					"fieldtype": "Small Text",
					"insert_after": "as_ip_address",
					"read_only": 1,
				},
			]
		},
		update=True,
	)


def protect_checkin(doc, method=None):
	"""Check-ins are an audit trail: insert-only for everyone but System Managers.
	(HRMS links attendance to them with direct DB updates, which don't pass through here.)"""
	if method == "validate" and doc.is_new():
		return
	if "System Manager" in frappe.get_roles():
		return
	frappe.throw(
		_("Check-ins can't be changed or deleted. Ask HR to correct your attendance."),
		frappe.PermissionError,
	)


# ---- users ↔ employees -------------------------------------------------------


@contextmanager
def _syncing():
	"""Saving an Employee updates its User, whose on_update hook calls back into this module.
	Yields True for the outermost call only, so the callback doesn't loop."""
	if frappe.flags.as_syncing_employee:
		yield False
		return
	frappe.flags.as_syncing_employee = True
	try:
		yield True
	finally:
		frappe.flags.as_syncing_employee = False


def employee_for(user: str) -> str | None:
	"""The active Employee linked to this login, if any."""
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


def is_aeraspace_member(user: str) -> bool:
	return user == "Administrator" or bool(
		frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": AERASPACE_ROLE})
	)


def ensure_employee(user: str) -> str | None:
	"""Create (or refresh) the HRMS Employee for an AeraSpace user."""
	if not hrms_ready() or user == "Guest" or not is_aeraspace_member(user):
		return None
	with _syncing() as first:
		return _ensure_employee(user) if first else None


def _ensure_employee(user: str) -> str | None:
	name = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if name:
		_sync_employee(user)
		return name

	ensure_hr_setup()
	account = frappe.db.get_value(
		"User", user, ["first_name", "last_name", "email", "creation", "enabled"], as_dict=True
	)
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": account.first_name or user,
			"last_name": account.last_name,
			"user_id": user,
			"company_email": account.email if account.email and "@" in account.email else None,
			"company": default_company(),
			"status": "Active" if account.enabled else "Inactive",
			"gender": PLACEHOLDER_GENDER,
			"date_of_birth": PLACEHOLDER_DOB,
			"date_of_joining": getdate(account.creation),
			"default_shift": DEFAULT_SHIFT,
			"create_user_permission": 0,
		}
	)
	_apply_profile(employee, user)
	employee.insert(ignore_permissions=True)
	_add_employee_role(user)
	return employee.name


def sync_employee(user: str):
	"""Copy AeraSpace profile details (designation, department, manager) onto the Employee."""
	if not hrms_ready():
		return
	with _syncing() as first:
		if first:
			_sync_employee(user)


def _sync_employee(user: str):
	name = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not name:
		return
	employee = frappe.get_doc("Employee", name)
	if _apply_profile(employee, user):
		employee.save(ignore_permissions=True)


def _apply_profile(employee, user) -> bool:
	"""Returns True when something changed."""
	profile = frappe.db.get_value(
		"AS Employee Profile", user, ["designation", "department", "manager", "phone"], as_dict=True
	)
	if not profile:
		return False
	values = {
		"designation": _ensure_designation(profile.designation),
		"department": _ensure_department(profile.department, employee.company),
		"reports_to": employee_for(profile.manager) if profile.manager else None,
		"cell_number": profile.phone,
	}
	changed = False
	for field, value in values.items():
		if (employee.get(field) or None) != (value or None):
			employee.set(field, value)
			changed = True
	return changed


def _ensure_designation(name: str | None) -> str | None:
	name = (name or "").strip()
	if not name:
		return None
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
	return name


def _ensure_department(name: str | None, company: str) -> str | None:
	"""AeraSpace shows plain names ("Engineering"); ERPNext stores "Engineering - ATPL"."""
	name = (name or "").strip()
	if not name:
		return None
	existing = frappe.db.get_value("Department", {"department_name": name, "company": company}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Department",
			"department_name": name,
			"company": company,
			"parent_department": "All Departments",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _add_employee_role(user: str):
	if user == "Administrator":
		return
	if not frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": EMPLOYEE_ROLE}):
		doc = frappe.get_doc("User", user)
		doc.append("roles", {"role": EMPLOYEE_ROLE})
		doc.save(ignore_permissions=True)


def link_all_users():
	"""Make sure every AeraSpace user has an Employee (run after HRMS is set up)."""
	if not hrms_ready():
		return []
	ensure_hr_setup()
	users = set(
		frappe.get_all("Has Role", filters={"parenttype": "User", "role": AERASPACE_ROLE}, pluck="parent")
	) | {"Administrator"}
	created = []
	for user in sorted(users):
		if frappe.db.exists("User", {"name": user, "enabled": 1}):
			before = frappe.db.get_value("Employee", {"user_id": user}, "name")
			name = ensure_employee(user)
			if name and not before:
				created.append((user, name))
	return created
