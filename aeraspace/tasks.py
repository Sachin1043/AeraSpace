"""Scheduled jobs (see scheduler_events in hooks.py)."""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime, today

from aeraspace.aeraspace.doctype.as_settings.as_settings import is_working_day
from aeraspace.api.eod import reminder_time
from aeraspace.notifications import push
from aeraspace.utils import get_active_users

REMINDED_KEY = "aeraspace_eod_reminded"


def eod_reminders():
	"""Once a working day, after the reminder time, nudge everyone who hasn't written their update."""
	date = getdate(today())
	if not is_working_day(date) or now_datetime() < get_datetime(f"{date} {reminder_time()}"):
		return
	if frappe.cache.hget(REMINDED_KEY, str(date)):
		return
	frappe.cache.hset(REMINDED_KEY, str(date), 1)

	submitted = set(frappe.get_all("AS Daily Update", filters={"update_date": date}, pluck="user"))
	for user in get_active_users():
		if user not in submitted and user != "Administrator":
			push(user, "Reminder", preview=_("Don't forget your EOD update for today"))
