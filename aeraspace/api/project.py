import frappe
from frappe import _
from frappe.utils import get_fullname

from aeraspace.aeraspace.doctype.as_channel.as_channel import normalize_channel_name
from aeraspace.hr import default_company
from aeraspace.notifications import notify_invite
from aeraspace.projects import (
	PROJECT_COLUMNS,
	PROJECT_SELECT,
	PROJECT_STATUSES,
	clean_key,
	select_fields,
	suggest_key,
	to_columns,
)
from aeraspace.utils import (
	OPEN_TYPES,
	add_member,
	check_channel_admin,
	check_read,
	get_member,
	notify_sidebar_change,
	post_system_message,
	require_login,
)

EDITABLE = ("project_name", "description", "status", "lead", "client")


def get_project_or_throw(project: str):
	doc = frappe.db.get_value("Project", project, PROJECT_SELECT, as_dict=True)
	if not doc or not doc.channel:
		frappe.throw(_("Project not found"), frappe.DoesNotExistError)
	return doc


def check_project_read(project: str):
	doc = get_project_or_throw(project)
	check_read(doc.channel)
	return doc


def check_project_member(project: str):
	doc = check_project_read(project)
	member = get_member(doc.channel)
	if not member:
		frappe.throw(_("Join the project to make changes"), frappe.PermissionError)
	doc.my_role = member.role
	return doc


@frappe.whitelist()
def suggest_project_key(project_name: str):
	return suggest_key(project_name)


@frappe.whitelist()
def get_projects():
	"""Projects the user can see (public ones and those they belong to) with task stats."""
	user = require_login()
	projects = frappe.db.sql(
		f"""
		select {", ".join(select_fields(PROJECT_COLUMNS, "p"))},
			exists(select 1 from `tabAS Channel Member` m where m.channel = p.as_channel and m.user = %(user)s) as is_member,
			(select count(*) from `tabAS Channel Member` m where m.channel = p.as_channel) as member_count
		from `tabProject` p
		join `tabAS Channel` c on c.name = p.as_channel
		where c.channel_type in %(open)s
			or exists(select 1 from `tabAS Channel Member` m where m.channel = p.as_channel and m.user = %(user)s)
		order by field(p.as_status, 'Active', 'On Hold', 'Completed', 'Archived'), p.project_name
		""",
		{"user": user, "open": OPEN_TYPES},
		as_dict=True,
	)
	if not projects:
		return []

	counts = {}
	for project, status, count in frappe.db.sql(
		"""select project, as_status, count(*) from `tabTask`
		where project in %(projects)s group by project, as_status""",
		{"projects": [p.name for p in projects]},
	):
		counts.setdefault(project, {})[status] = count

	for project in projects:
		stats = counts.get(project.name, {})
		project.task_counts = stats
		project.total_tasks = sum(stats.values())
		project.done_tasks = stats.get("Done", 0)
		project.is_member = bool(project.is_member)
	return projects


@frappe.whitelist()
def get_project(project: str):
	doc = check_project_read(project)
	member = get_member(doc.channel)
	doc.is_member = bool(member)
	doc.my_role = member.role if member else None
	doc.members = frappe.get_all(
		"AS Channel Member",
		filters={"channel": doc.channel},
		fields=["user", "role"],
		order_by="creation asc",
	)
	doc.creation = str(doc.creation)
	return doc


@frappe.whitelist(methods=["POST"])
def create_project(
	project_name: str,
	project_key: str | None = None,
	description: str | None = None,
	visibility: str = "Private",
	members=None,
	lead: str | None = None,
	client: str | None = None,
):
	me = require_login()
	if visibility not in ("Private", "Public"):
		frappe.throw(_("Visibility must be Private or Public"))
	project_name = (project_name or "").strip()
	key = clean_key(project_key) if project_key else suggest_key(project_name)

	project = frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": project_name,
			"company": default_company(),
			**to_columns(
				PROJECT_COLUMNS,
				{
					"project_key": key,
					"description": description,
					"status": "Active",
					"visibility": visibility,
					"lead": lead or me,
					"client": (client or "").strip() or None,
				},
			),
		}
	).insert(ignore_permissions=True, set_name=key)

	channel_name = normalize_channel_name(f"project-{project.project_name}")
	if frappe.db.exists("AS Channel", {"channel_name": channel_name, "is_archived": 0}):
		channel_name = normalize_channel_name(f"project-{key}")
	channel = frappe.get_doc(
		{
			"doctype": "AS Channel",
			"channel_name": channel_name,
			"channel_type": "Public" if visibility == "Public" else "Private",
			"description": description or _("Discussions for the {0} project").format(project.project_name),
			"project": project.name,
		}
	).insert(ignore_permissions=True)
	project.db_set("as_channel", channel.name)

	members = frappe.parse_json(members) if isinstance(members, str) else (members or [])
	members = [
		u for u in dict.fromkeys(members) if u != me and frappe.db.exists("User", {"name": u, "enabled": 1})
	]
	add_member(channel.name, me, role="Admin")
	for user in members:
		add_member(channel.name, user)

	post_system_message(
		channel.name, _("{0} created the project {1}").format(get_fullname(me), project.project_name)
	)
	notify_sidebar_change([me, *members])
	notify_invite(channel.name, members)
	return project.name


@frappe.whitelist(methods=["POST"])
def update_project(project: str, **values):
	doc = get_project_or_throw(project)
	check_channel_admin(doc.channel)
	values = {k: v for k, v in values.items() if k in EDITABLE}
	if "status" in values and values["status"] not in PROJECT_STATUSES:
		frappe.throw(_("Invalid status"))
	project_doc = frappe.get_doc("Project", project)
	project_doc.update(to_columns(PROJECT_COLUMNS, values))
	project_doc.save(ignore_permissions=True)
	if "description" in values:
		frappe.db.set_value("AS Channel", doc.channel, "description", values["description"])
	return get_project(project)
