import frappe
from frappe.utils import get_fullname, get_system_timezone

from aeraspace.permissions import is_admin

no_cache = 1


def get_context(context):
	# guests get the app too: it shows AeraSpace's own login / forgot-password pages
	context.boot = get_boot()
	return context


@frappe.whitelist()
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return get_boot()


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"socketio_port": frappe.conf.socketio_port,
			"system_timezone": get_system_timezone(),
			"session_user": frappe.session.user,
			"user_fullname": get_fullname(frappe.session.user),
			"user_image": frappe.db.get_value("User", frappe.session.user, "user_image"),
			"is_admin": frappe.session.user != "Guest" and is_admin(frappe.session.user),
		}
	)
