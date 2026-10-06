"""Admin-only user management for AeraSpace (admins = System Manager)."""

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, now_datetime, validate_email_address

from aeraspace.install import AERASPACE_ROLE
from aeraspace.passwords import generate_password, set_user_password
from aeraspace.permissions import is_admin

ADMIN_ROLE = "System Manager"
PROFILE_FIELDS = ("designation", "department", "team", "manager", "phone")
APPROVAL_HOURS = 24
PENDING_EXPIRY_DAYS = 7


def require_admin() -> str:
	user = frappe.session.user
	if user == "Guest" or not is_admin(user):
		frappe.throw(_("Only admins can manage users"), frappe.PermissionError)
	return user


def _has_role(user, role):
	return bool(frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": role}))


def _user_row(user):
	return next((u for u in list_users() if u.user == user), None)


@frappe.whitelist()
def list_users(search: str | None = None, status: str = "all"):
	require_admin()
	rows = frappe.db.sql(
		f"""
		select u.name as user, u.full_name, u.first_name, u.last_name, u.email, u.user_image,
			u.enabled, u.last_login, u.creation,
			{", ".join("p." + f for f in PROFILE_FIELDS)},
			exists(select 1 from `tabHas Role` r where r.parent = u.name and r.parenttype = 'User' and r.role = %(admin)s)
				as is_admin,
			exists(select 1 from `tabHas Role` r where r.parent = u.name and r.parenttype = 'User' and r.role = %(member)s)
				as is_aeraspace_user
		from `tabUser` u
		left join `tabAS Employee Profile` p on p.user = u.name
		where u.name not in ('Guest') and u.user_type = 'System User'
		order by u.enabled desc, u.full_name
		""",
		{"admin": ADMIN_ROLE, "member": AERASPACE_ROLE},
		as_dict=True,
	)
	term = (search or "").strip().lower()
	result = []
	for row in rows:
		row.is_admin = bool(row.is_admin) or row.user == "Administrator"
		row.is_aeraspace_user = bool(row.is_aeraspace_user)
		row.enabled = bool(row.enabled)
		row.last_login = str(row.last_login) if row.last_login else None
		row.creation = str(row.creation)
		if status == "active" and not row.enabled:
			continue
		if status == "disabled" and row.enabled:
			continue
		if term and not any(
			term in (row.get(f) or "").lower()
			for f in ("full_name", "user", "designation", "department", "team")
		):
			continue
		result.append(row)
	return result


@frappe.whitelist(methods=["POST"])
def create_user(
	first_name: str,
	email: str,
	last_name: str | None = None,
	password: str | None = None,
	designation: str | None = None,
	department: str | None = None,
	team: str | None = None,
	manager: str | None = None,
	phone: str | None = None,
	is_admin: int = 0,
):
	require_admin()
	email = (email or "").strip().lower()
	first_name = (first_name or "").strip()
	if not first_name:
		frappe.throw(_("First name is required"))
	if not validate_email_address(email):
		frappe.throw(_("{0} is not a valid email address").format(email or _("This")))
	if frappe.db.exists("User", email):
		frappe.throw(_("A user with the email {0} already exists").format(email))

	roles = [{"role": AERASPACE_ROLE}]
	if int(is_admin or 0):
		roles.append({"role": ADMIN_ROLE})
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"last_name": (last_name or "").strip() or None,
			"send_welcome_email": 0,
			"roles": roles,
		}
	).insert(ignore_permissions=True)

	generated = not password
	password = password or generate_password()
	set_user_password(email, password, logout=False)
	_update_profile(
		email,
		{
			"designation": designation,
			"department": department,
			"team": team,
			"manager": manager,
			"phone": phone,
		},
	)
	return {"user": _user_row(email), "password": password if generated else None}


@frappe.whitelist(methods=["POST"])
def update_user(user: str, **values):
	admin = require_admin()
	doc = frappe.get_doc("User", user)
	for field in ("first_name", "last_name"):
		if field in values:
			doc.set(field, (values[field] or "").strip() or None)
	if not doc.first_name:
		frappe.throw(_("First name is required"))

	if "is_admin" in values:
		make_admin = bool(int(values["is_admin"] or 0))
		if not make_admin and user in (admin, "Administrator"):
			frappe.throw(_("You can't remove admin access from yourself or Administrator"))
		has = _has_role(user, ADMIN_ROLE)
		if make_admin and not has:
			doc.append("roles", {"role": ADMIN_ROLE})
		elif not make_admin and has:
			doc.set("roles", [r for r in doc.roles if r.role != ADMIN_ROLE])
	if not any(r.role == AERASPACE_ROLE for r in doc.roles):
		doc.append("roles", {"role": AERASPACE_ROLE})
	doc.save(ignore_permissions=True)

	_update_profile(user, {k: v for k, v in values.items() if k in PROFILE_FIELDS})
	return _user_row(user)


def _update_profile(user, values):
	values = {
		k: ((v or "").strip() or None) if isinstance(v, str) or v is None else v for k, v in values.items()
	}
	if values.get("manager") == user:
		frappe.throw(_("A person can't be their own manager"))
	from aeraspace.api.directory import get_or_create_profile

	profile = get_or_create_profile(user)
	profile.update(values)
	profile.save(ignore_permissions=True)

	from aeraspace.hr import ensure_employee

	ensure_employee(user)  # creates the Employee for new users, syncs details for existing ones
	frappe.publish_realtime("as_profile_update", {"user": user}, after_commit=True)


@frappe.whitelist(methods=["POST"])
def set_enabled(user: str, enabled: int):
	admin = require_admin()
	enabled = int(enabled)
	if not enabled and user in (admin, "Administrator"):
		frappe.throw(_("You can't disable yourself or Administrator"))
	frappe.db.set_value("User", user, "enabled", enabled)
	if not enabled:
		frappe.sessions.clear_sessions(user, force=True)
	frappe.publish_realtime("as_profile_update", {"user": user}, after_commit=True)
	return _user_row(user)


@frappe.whitelist(methods=["POST"])
def set_password(user: str, password: str | None = None):
	"""Admin resets someone's password; they're signed out everywhere."""
	require_admin()
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"), frappe.DoesNotExistError)
	generated = not password
	password = password or generate_password()
	set_user_password(user, password, logout=True)
	return {"password": password if generated else None}


# ---- forgotten-password requests ------------------------------------------------


def expire_old_requests():
	frappe.db.set_value(
		"AS Password Reset Request",
		{"status": "Pending", "creation": ("<", add_days(now_datetime(), -PENDING_EXPIRY_DAYS))},
		"status",
		"Expired",
		update_modified=False,
	)
	frappe.db.set_value(
		"AS Password Reset Request",
		{"status": "Approved", "approved_until": ("<", now_datetime())},
		"status",
		"Expired",
		update_modified=False,
	)


@frappe.whitelist()
def list_reset_requests(status: str = "Pending"):
	require_admin()
	expire_old_requests()
	filters = {} if status == "all" else {"status": status}
	rows = frappe.get_all(
		"AS Password Reset Request",
		filters=filters,
		fields=[
			"name",
			"user",
			"status",
			"ip_address",
			"reviewed_by",
			"reviewed_at",
			"approved_until",
			"note",
			"creation",
		],
		order_by="creation desc",
		limit=200,
	)
	for row in rows:
		for field in ("reviewed_at", "approved_until", "creation"):
			row[field] = str(row[field]) if row[field] else None
		row.full_name = frappe.utils.get_fullname(row.user)
	return rows


@frappe.whitelist()
def pending_reset_count():
	require_admin()
	expire_old_requests()
	return frappe.db.count("AS Password Reset Request", {"status": "Pending"})


@frappe.whitelist(methods=["POST"])
def approve_reset_request(name: str):
	admin = require_admin()
	doc = _pending_request(name)
	doc.update(
		{
			"status": "Approved",
			"reviewed_by": admin,
			"reviewed_at": now_datetime(),
			"approved_until": add_to_date(now_datetime(), hours=APPROVAL_HOURS),
		}
	)
	doc.save(ignore_permissions=True)
	_broadcast_request_change()


@frappe.whitelist(methods=["POST"])
def reject_reset_request(name: str, note: str | None = None):
	admin = require_admin()
	doc = _pending_request(name)
	doc.update({"status": "Rejected", "reviewed_by": admin, "reviewed_at": now_datetime(), "note": note})
	doc.save(ignore_permissions=True)
	_broadcast_request_change()


def _pending_request(name):
	expire_old_requests()
	doc = frappe.get_doc("AS Password Reset Request", name)
	if doc.status != "Pending":
		frappe.throw(_("This request is already {0}").format(_(doc.status).lower()))
	return doc


def _broadcast_request_change():
	for admin in get_admins():
		frappe.publish_realtime("as_reset_requests", {}, user=admin, after_commit=True)


def get_admins() -> list[str]:
	admins = frappe.db.sql_list(
		"""select distinct r.parent from `tabHas Role` r join `tabUser` u on u.name = r.parent
		where r.parenttype = 'User' and r.role = %s and u.enabled = 1""",
		ADMIN_ROLE,
	)
	return sorted(set(admins) | {"Administrator"})
