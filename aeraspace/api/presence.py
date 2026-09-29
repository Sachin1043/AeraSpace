import time

import frappe

from aeraspace.utils import require_login

PRESENCE_KEY = "aeraspace_presence"
# A client heartbeats every 30s; anyone silent for longer than this is offline
OFFLINE_AFTER_SECONDS = 75


@frappe.whitelist()
def heartbeat(state: str = "online"):
	user = require_login()
	state = "away" if state == "away" else "online"

	previous = frappe.cache.hget(PRESENCE_KEY, user)
	frappe.cache.hset(PRESENCE_KEY, user, {"state": state, "ts": time.time()})

	if not previous or previous.get("state") != state or is_stale(previous):
		broadcast_state(user)
	return state


def is_invisible(user: str) -> bool:
	return frappe.db.get_value("AS Employee Profile", user, "availability") == "Invisible"


def broadcast_state(user: str):
	"""Tell everyone the user's presence; invisible users always look offline."""
	value = frappe.cache.hget(PRESENCE_KEY, user)
	state = "offline" if not value or is_stale(value) or is_invisible(user) else value.get("state")
	frappe.publish_realtime("as_presence", {"user": user, "state": state})


@frappe.whitelist()
def go_offline():
	user = require_login()
	frappe.cache.hdel(PRESENCE_KEY, user)
	frappe.publish_realtime("as_presence", {"user": user, "state": "offline"})


@frappe.whitelist()
def get_presence():
	me = require_login()
	invisible = set(
		frappe.get_all("AS Employee Profile", filters={"availability": "Invisible"}, pluck="user")
	) - {me}
	# redis hash keys come back as bytes
	states = {}
	for key, value in (frappe.cache.hgetall(PRESENCE_KEY) or {}).items():
		user = frappe.safe_decode(key)
		states[user] = "offline" if is_stale(value) or user in invisible else value.get("state")
	return states


def is_stale(value) -> bool:
	return time.time() - (value or {}).get("ts", 0) > OFFLINE_AFTER_SECONDS
