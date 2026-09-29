"""Global search across messages, files, people and channels.

Query syntax (terms are AND-ed, filters can be combined):
    shopify inventory from:sachin in:#engineering after:2026-09-01 before:2026-10-01 type:pdf has:file
"""

import re
import shlex

import frappe
from frappe.utils import getdate

from aeraspace.api.directory import get_people
from aeraspace.messages import MESSAGE_FIELDS, build_payloads
from aeraspace.utils import OPEN_TYPES, require_login

LIMIT = 30
FILTER_PATTERN = re.compile(r"^(from|in|before|after|type|has):(.+)$", re.IGNORECASE)
TYPE_GROUPS = {
	"image": {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "avif"},
	"doc": {"doc", "docx", "odt", "rtf", "txt", "md"},
	"sheet": {"xls", "xlsx", "ods", "csv"},
	"slides": {"ppt", "pptx", "odp"},
	"code": {"py", "js", "ts", "vue", "json", "sql", "html", "css", "sh", "yml", "yaml"},
	"archive": {"zip", "tar", "gz", "rar", "7z"},
}


def parse_query(query: str) -> tuple[list[str], dict]:
	try:
		parts = shlex.split(query or "")
	except ValueError:
		parts = (query or "").split()

	terms, filters = [], {}
	for part in parts:
		match = FILTER_PATTERN.match(part)
		if match and match.group(2).strip():
			filters.setdefault(match.group(1).lower(), []).append(match.group(2).strip())
		elif part.strip():
			terms.append(part.strip())
	return terms, filters


def like(value: str) -> str:
	escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
	return f"%{escaped}%"


def readable_channels(user: str) -> dict:
	"""name -> channel row, for every channel the user may search."""
	rows = frappe.db.sql(
		"""
		select c.name, c.channel_name, c.channel_type, c.dm_key
		from `tabAS Channel` c
		where c.is_archived = 0 and (
			c.channel_type in %(open)s
			or exists (select 1 from `tabAS Channel Member` m where m.channel = c.name and m.user = %(user)s)
		)
		""",
		{"open": OPEN_TYPES, "user": user},
		as_dict=True,
	)
	return {row.name: row for row in rows}


def resolve_users(values: list[str]) -> set[str]:
	users = set()
	for value in values:
		value = value.lstrip("@")
		users.update(
			frappe.get_all(
				"User",
				or_filters={"name": ("like", like(value)), "full_name": ("like", like(value))},
				filters={"enabled": 1},
				pluck="name",
			)
		)
	return users


def resolve_channels(values: list[str], channels: dict, user: str) -> set[str]:
	"""in:#name matches channel names; in:@person matches your direct message with them."""
	result = set()
	for value in values:
		if value.startswith("@"):
			for other in resolve_users([value]):
				key = "::".join(sorted({user, other}))
				result.update(c.name for c in channels.values() if c.dm_key == key)
		else:
			name = value.lstrip("#").lower()
			result.update(
				c.name for c in channels.values() if c.channel_name and name in c.channel_name.lower()
			)
	return result


def matches_type(file_name: str, types: list[str]) -> bool:
	extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
	for value in types:
		value = value.lower().lstrip(".")
		if extension == value or extension in TYPE_GROUPS.get(value, set()):
			return True
	return False


@frappe.whitelist()
def search(query: str, scope: str = "all"):
	user = require_login()
	terms, filters = parse_query(query)
	if not terms and not filters:
		return {"messages": [], "files": [], "people": [], "channels": [], "tasks": [], "terms": []}

	channels = readable_channels(user)
	scope_channels = set(channels)
	if filters.get("in"):
		scope_channels &= resolve_channels(filters["in"], channels, user)

	conditions = ["m.is_deleted = 0", "m.message_type = 'Text'", "m.channel in %(channels)s"]
	params = {"channels": tuple(scope_channels) or ("",)}

	for i, term in enumerate(terms):
		# a term also matches mentions of people whose name contains it
		mention_users = resolve_users([term]) if len(term) >= 3 else set()
		clause = [f"m.content like %(term{i})s"]
		params[f"term{i}"] = like(term)
		for j, mentioned in enumerate(sorted(mention_users)[:10]):
			clause.append(f"m.content like %(mention{i}_{j})s")
			params[f"mention{i}_{j}"] = like(f"<@{mentioned}>")
		conditions.append("(" + " or ".join(clause) + ")")

	if filters.get("from"):
		conditions.append("m.sender in %(senders)s")
		params["senders"] = tuple(resolve_users(filters["from"])) or ("",)
	if filters.get("after"):
		conditions.append("m.creation >= %(after)s")
		params["after"] = getdate(filters["after"][-1])
	if filters.get("before"):
		conditions.append("m.creation < %(before)s")
		params["before"] = getdate(filters["before"][-1])

	result = {"messages": [], "files": [], "people": [], "channels": [], "tasks": [], "terms": terms}
	wants_files = bool(filters.get("type") or "file" in [v.lower() for v in filters.get("has", [])])

	if scope in ("all", "messages") and not wants_files:
		rows = frappe.db.sql(
			f"""select {", ".join("m." + f for f in MESSAGE_FIELDS)}
			from `tabAS Message` m where {" and ".join(conditions)}
			order by m.creation desc limit {LIMIT}""",
			params,
			as_dict=True,
		)
		result["messages"] = _with_channel(build_payloads(rows), channels)

	if scope in ("all", "files"):
		file_conditions = [c for c in conditions if not c.startswith("(m.content")] + [
			"m.files is not null",
			"m.files != '[]'",
		]
		rows = frappe.db.sql(
			f"""select m.name, m.channel, m.sender, m.files, m.thread_root, m.creation
			from `tabAS Message` m where {" and ".join(file_conditions)}
			order by m.creation desc limit 500""",
			params,
			as_dict=True,
		)
		for row in rows:
			for file in frappe.parse_json(row.files) or []:
				name = (file.get("file_name") or "").lower()
				if terms and not all(t.lower() in name for t in terms):
					continue
				if filters.get("type") and not matches_type(name, filters["type"]):
					continue
				channel = channels[row.channel]
				result["files"].append(
					{
						**file,
						"message": row.name,
						"thread_root": row.thread_root,
						"channel": row.channel,
						"channel_name": channel.channel_name,
						"channel_type": channel.channel_type,
						"sender": row.sender,
						"creation": str(row.creation),
					}
				)
				if len(result["files"]) >= LIMIT:
					break
			if len(result["files"]) >= LIMIT:
				break

	only_terms = terms and not filters
	if scope in ("all", "people") and only_terms:
		fields = ("full_name", "user", "designation", "department", "team", "skills")
		result["people"] = [
			p
			for p in get_people()
			if all(any(t.lower() in (p.get(f) or "").lower() for f in fields) for t in terms)
		][:LIMIT]

	if scope in ("all", "channels") and only_terms:
		result["channels"] = [
			{"name": c.name, "channel_name": c.channel_name, "channel_type": c.channel_type}
			for c in channels.values()
			if c.channel_type not in ("Direct", "Group")
			and all(t.lower().lstrip("#") in (c.channel_name or "").lower() for t in terms)
		][:LIMIT]

	if scope in ("all", "tasks") and terms and not filters.get("type") and not filters.get("has"):
		result["tasks"] = _search_tasks(terms, filters, channels, user)

	return result


def _search_tasks(terms, filters, channels, user):
	projects = frappe.get_all(
		"AS Project",
		filters={"channel": ("in", list(channels) or [""])},
		fields=["name", "project_name", "channel"],
	)
	if filters.get("in"):
		allowed = resolve_channels(filters["in"], channels, user)
		projects = [p for p in projects if p.channel in allowed]
	if not projects:
		return []

	conditions = ["t.project in %(projects)s"]
	params = {"projects": [p.name for p in projects]}
	for i, term in enumerate(terms):
		conditions.append(f"(t.title like %(t{i})s or t.name like %(t{i})s or t.description like %(t{i})s)")
		params[f"t{i}"] = like(term)
	if filters.get("from"):
		conditions.append("(t.assignee in %(people)s or t.reporter in %(people)s)")
		params["people"] = tuple(resolve_users(filters["from"])) or ("",)

	names = {p.name: p.project_name for p in projects}
	rows = frappe.db.sql(
		f"""select t.name, t.title, t.project, t.status, t.priority, t.assignee, t.due_date
		from `tabAS Task` t where {" and ".join(conditions)}
		order by field(t.status, 'Done'), t.modified desc limit {LIMIT}""",
		params,
		as_dict=True,
	)
	for row in rows:
		row.project_name = names.get(row.project)
		row.due_date = str(row.due_date) if row.due_date else None
	return rows


def _with_channel(messages, channels):
	for message in messages:
		channel = channels[message.channel]
		message.channel_name = channel.channel_name
		message.channel_type = channel.channel_type
	return messages
