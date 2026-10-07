import frappe

AERASPACE_ROLE = "AeraSpace User"


def after_install():
	ensure_role()


def after_migrate():
	ensure_role()
	from aeraspace.hr import link_all_users

	link_all_users()  # no-op until ERPNext + HRMS are installed and set up
	if "erpnext" in frappe.get_installed_apps():
		from aeraspace.projects import ensure_custom_fields

		ensure_custom_fields()


def ensure_role():
	if not frappe.db.exists("Role", AERASPACE_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": AERASPACE_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
