"""Shared helpers for turning AS Message rows into client payloads and broadcasting changes."""

import frappe

from aeraspace.utils import publish_to_channel

MESSAGE_FIELDS = [
	"name",
	"channel",
	"sender",
	"message_type",
	"content",
	"files",
	"thread_root",
	"reply_to",
	"reply_count",
	"last_reply_at",
	"is_edited",
	"is_deleted",
	"is_pinned",
	"pinned_by",
	"creation",
]


def build_payloads(rows: list[dict]) -> list[dict]:
	"""Attach reactions, reply previews and parsed files to message rows (batched)."""
	if not rows:
		return []
	names = [row["name"] for row in rows]

	reactions = {}
	for r in frappe.get_all(
		"AS Message Reaction",
		filters={"message": ("in", names)},
		fields=["message", "emoji", "user"],
		order_by="creation asc",
	):
		reactions.setdefault(r.message, {}).setdefault(r.emoji, []).append(r.user)

	reply_ids = list({row.get("reply_to") for row in rows if row.get("reply_to")})
	replies = {}
	if reply_ids:
		for r in frappe.get_all(
			"AS Message",
			filters={"name": ("in", reply_ids)},
			fields=["name", "sender", "content", "is_deleted", "files"],
		):
			replies[r.name] = {
				"name": r.name,
				"sender": r.sender,
				"content": "" if r.is_deleted else (r.content or "")[:200],
				"is_deleted": r.is_deleted,
				"has_files": bool(not r.is_deleted and r.files and frappe.parse_json(r.files)),
			}

	payloads = []
	for row in rows:
		deleted = bool(row.get("is_deleted"))
		payloads.append(
			frappe._dict(
				{
					"name": row["name"],
					"channel": row["channel"],
					"sender": row["sender"],
					"message_type": row.get("message_type") or "Text",
					"content": "" if deleted else (row.get("content") or ""),
					"files": [] if deleted else (frappe.parse_json(row["files"]) if row.get("files") else []),
					"thread_root": row.get("thread_root"),
					"reply_to": replies.get(row.get("reply_to")),
					"reply_count": row.get("reply_count") or 0,
					"last_reply_at": str(row["last_reply_at"]) if row.get("last_reply_at") else None,
					"is_edited": bool(row.get("is_edited")),
					"is_deleted": deleted,
					"is_pinned": bool(row.get("is_pinned")),
					"pinned_by": row.get("pinned_by"),
					"reactions": {} if deleted else reactions.get(row["name"], {}),
					"creation": str(row["creation"]),
				}
			)
		)
	return payloads


def get_payload(message: str) -> dict:
	row = frappe.db.get_value("AS Message", message, MESSAGE_FIELDS, as_dict=True)
	return build_payloads([row])[0]


def publish_message_update(message: str):
	payload = get_payload(message)
	publish_to_channel(payload["channel"], "as_message_update", payload)
	return payload


def add_thread_follower(thread_root: str, user: str):
	if user and not frappe.db.exists("AS Thread Follower", {"thread_root": thread_root, "user": user}):
		frappe.get_doc({"doctype": "AS Thread Follower", "thread_root": thread_root, "user": user}).insert(
			ignore_permissions=True
		)
