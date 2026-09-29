import frappe
from frappe import _

from aeraspace.utils import check_member, check_read, require_login


@frappe.whitelist(methods=["POST"])
def upload(channel: str):
	"""Store one uploaded file privately, attached to the channel so only people who can read it can download it."""
	require_login()
	check_member(channel)

	uploaded = frappe.request.files.get("file")
	if not uploaded:
		frappe.throw(_("No file received"))

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": uploaded.filename,
			"content": uploaded.stream.read(),
			"is_private": 1,
			"attached_to_doctype": "AS Channel",
			"attached_to_name": channel,
		}
	).insert(ignore_permissions=True)
	return {
		"name": file.name,
		"file_name": file.file_name,
		"file_url": file.file_url,
		"file_size": file.file_size,
	}


@frappe.whitelist()
def get_channel_files(channel: str):
	"""Files shared in the channel's (non-deleted) messages, newest first."""
	check_read(channel)
	rows = frappe.get_all(
		"AS Message",
		filters={"channel": channel, "is_deleted": 0, "files": ("is", "set")},
		fields=["name", "sender", "files", "creation", "thread_root"],
		order_by="creation desc",
	)
	result = []
	for row in rows:
		for file in frappe.parse_json(row.files) or []:
			result.append(
				{
					**file,
					"message": row.name,
					"thread_root": row.thread_root,
					"sender": row.sender,
					"creation": str(row.creation),
				}
			)
	return result
