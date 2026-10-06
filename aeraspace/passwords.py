"""Password rules shared by admin resets and self-service resets."""

import secrets
import string

import frappe
from frappe import _
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils.password import update_password

MIN_LENGTH = 8


def validate_new_password(user: str, password: str):
	if not password or len(password) < MIN_LENGTH:
		frappe.throw(_("Password must be at least {0} characters").format(MIN_LENGTH))
	user_data = frappe.db.get_value(
		"User", user, ["first_name", "middle_name", "last_name", "email", "birth_date"]
	)
	feedback = test_password_strength(password, user_data=user_data)
	if feedback and not feedback.get("feedback", {}).get("password_policy_validation_passed", False):
		hints = feedback.get("feedback", {})
		message = " ".join(filter(None, [hints.get("warning"), *hints.get("suggestions", [])]))
		frappe.throw(_("This password is too weak. {0}").format(message or _("Try a longer one.")))


def generate_password() -> str:
	"""12 characters with upper, lower, digit and symbol — easy to read aloud, hard to guess."""
	alphabet = string.ascii_letters + string.digits
	core = [secrets.choice(alphabet) for _ in range(9)]
	core += [secrets.choice(string.ascii_uppercase), secrets.choice(string.digits), secrets.choice("@#$%&*!")]
	secrets.SystemRandom().shuffle(core)
	return "".join(core)


def set_user_password(user: str, password: str, logout: bool = True):
	validate_new_password(user, password)
	update_password(user, password, logout_all_sessions=logout)
