"""Forgot password, approved by an admin.

1. The person asks for a reset with their email and gets back a request id + a secret claim key
   (kept in their browser). The response is identical whether or not the email exists.
2. An admin approves (or rejects) it in AeraSpace.
3. Within 24 hours, the same browser sets a new password with the request id + claim key. One use only.
"""

import hashlib
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_fullname, now_datetime

from aeraspace.api.admin_users import _broadcast_request_change, expire_old_requests, get_admins
from aeraspace.install import AERASPACE_ROLE
from aeraspace.notifications import push
from aeraspace.passwords import set_user_password

GENERIC_MESSAGE = (
	"If this email belongs to an AeraSpace account, an admin has been asked to approve your reset."
)


def _hash(value: str) -> str:
	return hashlib.sha256((value or "").encode()).hexdigest()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def request_reset(email: str):
	email = (email or "").strip().lower()
	claim_key = secrets.token_urlsafe(32)
	user = frappe.db.get_value("User", {"name": email, "enabled": 1, "user_type": "System User"}, "name")
	is_member = user and frappe.db.exists(
		"Has Role", {"parent": user, "parenttype": "User", "role": AERASPACE_ROLE}
	)

	if not is_member:
		# same shape as a real request, so nobody can probe which emails exist
		return {
			"request": frappe.generate_hash(length=10),
			"claim_key": claim_key,
			"message": _(GENERIC_MESSAGE),
		}

	expire_old_requests()
	# one open request per person: a new ask replaces the previous one
	frappe.db.set_value(
		"AS Password Reset Request",
		{"user": user, "status": ("in", ("Pending", "Approved"))},
		"status",
		"Expired",
		update_modified=False,
	)
	doc = frappe.get_doc(
		{
			"doctype": "AS Password Reset Request",
			"user": user,
			"status": "Pending",
			"claim_key_hash": _hash(claim_key),
			"ip_address": frappe.local.request_ip,
		}
	).insert(ignore_permissions=True)

	for admin in get_admins():
		if admin != user:
			push(
				admin,
				"Password Reset",
				from_user=user,
				preview=_("{0} forgot their password and is asking for a reset").format(get_fullname(user)),
			)
	_broadcast_request_change()
	return {"request": doc.name, "claim_key": claim_key, "message": _(GENERIC_MESSAGE)}


def _find(request: str, claim_key: str):
	doc = frappe.db.get_value(
		"AS Password Reset Request",
		request,
		["name", "user", "status", "claim_key_hash", "approved_until"],
		as_dict=True,
	)
	if not doc or not secrets.compare_digest(doc.claim_key_hash or "", _hash(claim_key)):
		return None
	return doc


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60 * 60)
def get_status(request: str, claim_key: str):
	expire_old_requests()
	doc = _find(request, claim_key)
	if not doc:
		return {"status": "pending"}  # unknown requests look like they're waiting
	return {"status": doc.status.lower()}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def complete_reset(request: str, claim_key: str, new_password: str):
	expire_old_requests()
	doc = _find(request, claim_key)
	if not doc or doc.status != "Approved" or not doc.approved_until or doc.approved_until < now_datetime():
		frappe.throw(
			_("This reset isn't approved, has expired, or was already used. Please request a new one.")
		)

	set_user_password(doc.user, new_password, logout=True)
	frappe.db.set_value("AS Password Reset Request", doc.name, "status", "Completed")
	_broadcast_request_change()
	return {"email": doc.user}
