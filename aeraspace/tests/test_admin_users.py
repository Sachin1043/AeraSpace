from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime
from frappe.utils.password import check_password

from aeraspace.api import admin_users, password_reset
from aeraspace.tests.test_chat import make_user

ADMIN = "au-admin@example.com"
MEMBER = "au-member@example.com"
NEW = "au-new@example.com"
STRONG = "Kx9#mPq2vL"


class TestAdminUsers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(ADMIN)
		make_user(MEMBER)
		admin = frappe.get_doc("User", ADMIN)
		if not any(r.role == "System Manager" for r in admin.roles):
			admin.append("roles", {"role": "System Manager"})
			admin.save(ignore_permissions=True)

	def setUp(self):
		frappe.db.delete("AS Password Reset Request", {"user": ("in", (MEMBER, NEW))})
		frappe.db.delete("AS Notification", {"notification_type": "Password Reset"})
		if frappe.db.exists("User", NEW):
			frappe.delete_doc("User", NEW, force=True, ignore_permissions=True)
			frappe.db.delete("AS Employee Profile", {"user": NEW})

	# ---- admin-only -----------------------------------------------------------

	def test_members_cannot_use_admin_endpoints(self):
		with self.set_user(MEMBER):
			for call in (
				lambda: admin_users.list_users(),
				lambda: admin_users.create_user("X", "x@example.com"),
				lambda: admin_users.set_enabled(ADMIN, 0),
				lambda: admin_users.set_password(ADMIN),
				lambda: admin_users.list_reset_requests(),
			):
				self.assertRaises(frappe.PermissionError, call)

	def test_create_user_ready_to_log_in(self):
		with self.set_user(ADMIN):
			result = admin_users.create_user(
				"Arun", NEW, last_name="K", designation="Developer", manager=ADMIN
			)
		password = result["password"]
		self.assertTrue(password)  # generated, shown once
		self.assertEqual(check_password(NEW, password), NEW)
		self.assertTrue(frappe.db.exists("Has Role", {"parent": NEW, "role": "AeraSpace User"}))
		self.assertFalse(frappe.db.exists("Has Role", {"parent": NEW, "role": "System Manager"}))
		profile = frappe.db.get_value("AS Employee Profile", NEW, ["designation", "manager"], as_dict=True)
		self.assertEqual((profile.designation, profile.manager), ("Developer", ADMIN))
		with self.set_user(ADMIN):
			self.assertRaises(frappe.ValidationError, admin_users.create_user, "Arun", NEW)  # duplicate
			self.assertRaises(frappe.ValidationError, admin_users.create_user, "Bad", "not-an-email")
			self.assertIn(NEW, [u.user for u in admin_users.list_users(search="arun")])

	def test_admin_flag_disable_and_password_reset(self):
		with self.set_user(ADMIN):
			admin_users.create_user("Arun", NEW, password=STRONG, is_admin=1)
			self.assertTrue(next(u for u in admin_users.list_users() if u.user == NEW).is_admin)
			admin_users.update_user(NEW, is_admin=0, designation="QA")
			self.assertFalse(frappe.db.exists("Has Role", {"parent": NEW, "role": "System Manager"}))

			admin_users.set_enabled(NEW, 0)
			self.assertEqual(frappe.db.get_value("User", NEW, "enabled"), 0)
			self.assertNotIn(NEW, [u.user for u in admin_users.list_users(status="active")])
			admin_users.set_enabled(NEW, 1)

			self.assertRaises(frappe.ValidationError, admin_users.set_enabled, ADMIN, 0)  # not yourself
			self.assertRaises(frappe.ValidationError, admin_users.update_user, ADMIN, is_admin=0)
			self.assertRaises(frappe.ValidationError, admin_users.set_password, NEW, "short")

			new_password = admin_users.set_password(NEW)["password"]
		self.assertEqual(check_password(NEW, new_password), NEW)

	# ---- forgot password --------------------------------------------------------

	def test_unknown_email_looks_the_same_and_creates_nothing(self):
		before = frappe.db.count("AS Password Reset Request")
		result = password_reset.request_reset("nobody-here@example.com")
		self.assertEqual(set(result), {"request", "claim_key", "message"})
		self.assertEqual(frappe.db.count("AS Password Reset Request"), before)
		self.assertEqual(
			password_reset.get_status(result["request"], result["claim_key"])["status"], "pending"
		)

	def test_full_reset_flow_needs_approval_and_is_single_use(self):
		asked = password_reset.request_reset(MEMBER)
		key, request = asked["claim_key"], asked["request"]
		self.assertTrue(
			frappe.db.exists("AS Notification", {"user": ADMIN, "notification_type": "Password Reset"})
		)
		self.assertEqual(password_reset.get_status(request, key)["status"], "pending")
		self.assertRaises(
			frappe.ValidationError, password_reset.complete_reset, request, key, STRONG
		)  # not approved

		with self.set_user(ADMIN):
			self.assertIn(request, [r.name for r in admin_users.list_reset_requests()])
			admin_users.approve_reset_request(request)

		self.assertEqual(password_reset.get_status(request, key)["status"], "approved")
		self.assertRaises(frappe.ValidationError, password_reset.complete_reset, request, "wrong-key", STRONG)
		self.assertRaises(frappe.ValidationError, password_reset.complete_reset, request, key, "weak")
		self.assertEqual(password_reset.complete_reset(request, key, STRONG)["email"], MEMBER)
		self.assertEqual(check_password(MEMBER, STRONG), MEMBER)
		self.assertRaises(
			frappe.ValidationError, password_reset.complete_reset, request, key, STRONG
		)  # once only

	def test_reject_and_expiry(self):
		asked = password_reset.request_reset(MEMBER)
		with self.set_user(ADMIN):
			admin_users.reject_reset_request(asked["request"], note="Not you")
		self.assertEqual(
			password_reset.get_status(asked["request"], asked["claim_key"])["status"], "rejected"
		)

		again = password_reset.request_reset(MEMBER)
		with self.set_user(ADMIN):
			admin_users.approve_reset_request(again["request"])
		frappe.db.set_value(
			"AS Password Reset Request",
			again["request"],
			"approved_until",
			now_datetime() - timedelta(minutes=1),
		)
		self.assertEqual(password_reset.get_status(again["request"], again["claim_key"])["status"], "expired")
		self.assertRaises(
			frappe.ValidationError,
			password_reset.complete_reset,
			again["request"],
			again["claim_key"],
			STRONG,
		)

	def test_new_request_replaces_open_one(self):
		first = password_reset.request_reset(MEMBER)
		second = password_reset.request_reset(MEMBER)
		self.assertEqual(
			frappe.db.get_value("AS Password Reset Request", first["request"], "status"), "Expired"
		)
		self.assertEqual(
			frappe.db.get_value("AS Password Reset Request", second["request"], "status"), "Pending"
		)
