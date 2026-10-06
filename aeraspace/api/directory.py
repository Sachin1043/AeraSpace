import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import now_datetime

from aeraspace.utils import require_login

PROFILE_FIELDS = (
	"designation",
	"department",
	"team",
	"manager",
	"phone",
	"skills",
	"availability",
	"status_emoji",
	"status_text",
	"status_expires_on",
)
EDITABLE_FIELDS = set(PROFILE_FIELDS)
AVAILABILITY = ("Auto", "Away", "Busy", "Do Not Disturb", "Invisible")


@frappe.whitelist()
def get_people():
	"""Every active desk user, merged with their AeraSpace profile (if one exists)."""
	require_login()
	User = DocType("User")
	Profile = DocType("AS Employee Profile")

	rows = (
		frappe.qb.from_(User)
		.left_join(Profile)
		.on(Profile.user == User.name)
		.select(
			User.name.as_("user"),
			User.full_name,
			User.user_image,
			User.email,
			User.time_zone,
			*[Profile[field] for field in PROFILE_FIELDS],
		)
		.where((User.enabled == 1) & (User.user_type == "System User") & (User.name != "Guest"))
		.orderby(User.full_name)
		.run(as_dict=True)
	)

	now = now_datetime()
	me = frappe.session.user
	for row in rows:
		row.full_name = row.full_name or row.user
		row.availability = row.availability or "Auto"
		if row.availability == "Invisible" and row.user != me:
			row.availability = "Auto"  # never reveal that someone is invisible
		if row.status_expires_on and row.status_expires_on < now:
			row.status_emoji = row.status_text = row.status_expires_on = None
	return rows


@frappe.whitelist()
def update_my_profile(**values):
	user = require_login()
	values = {key: value for key, value in values.items() if key in EDITABLE_FIELDS}
	if values.get("availability") not in (None, *AVAILABILITY):
		frappe.throw(_("Invalid availability"))

	profile = get_or_create_profile(user)
	was_invisible = profile.availability == "Invisible"
	profile.update(values)
	profile.save(ignore_permissions=True)

	from aeraspace.hr import sync_employee

	sync_employee(user)
	frappe.publish_realtime("as_profile_update", {"user": user}, after_commit=True)
	if "availability" in values and (was_invisible or profile.availability == "Invisible"):
		# going invisible looks like signing off; coming back looks like signing in
		from aeraspace.api.presence import broadcast_state

		broadcast_state(user)
	return profile.as_dict()


def get_or_create_profile(user: str):
	if frappe.db.exists("AS Employee Profile", user):
		return frappe.get_doc("AS Employee Profile", user)
	return frappe.get_doc({"doctype": "AS Employee Profile", "user": user}).insert(ignore_permissions=True)


def create_profile_for_user(doc, method=None):
	"""User.on_update hook: every desk user gets a directory profile (also after gaining a desk role)."""
	if doc.user_type == "System User" and not frappe.db.exists("AS Employee Profile", doc.name):
		frappe.get_doc({"doctype": "AS Employee Profile", "user": doc.name}).insert(ignore_permissions=True)

	# every AeraSpace user is also an HRMS Employee (attendance, leave, timesheets)
	from aeraspace.hr import ensure_employee

	ensure_employee(doc.name)


PHOTO_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "gif")
PHOTO_MAX_BYTES = 5 * 1024 * 1024


@frappe.whitelist(methods=["POST"])
def upload_profile_photo():
	"""Set the current user's profile photo (public, so every teammate can see the avatar)."""
	user = require_login()
	uploaded = frappe.request.files.get("file")
	if not uploaded:
		frappe.throw(_("No file received"))

	extension = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
	if extension not in PHOTO_EXTENSIONS:
		frappe.throw(_("Please upload a PNG, JPG, WEBP or GIF image"))
	content = uploaded.stream.read()
	if len(content) > PHOTO_MAX_BYTES:
		frappe.throw(_("Profile photos can be at most 5 MB"))

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.scrub(user)}-avatar.{extension}",
			"content": content,
			"is_private": 0,
			"attached_to_doctype": "User",
			"attached_to_name": user,
			"attached_to_field": "user_image",
		}
	).insert(ignore_permissions=True)
	_set_photo(user, file.file_url)
	return file.file_url


@frappe.whitelist(methods=["POST"])
def remove_profile_photo():
	_set_photo(require_login(), None)


def _set_photo(user, url):
	frappe.db.set_value("User", user, "user_image", url)
	if frappe.db.exists("AS Employee Profile", user):
		frappe.db.set_value("AS Employee Profile", user, "user_image", url)
	frappe.publish_realtime("as_profile_update", {"user": user}, after_commit=True)
