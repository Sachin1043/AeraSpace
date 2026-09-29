import frappe
from frappe.tests import IntegrationTestCase

from aeraspace.api import chat
from aeraspace.api import project as project_api
from aeraspace.api import task as task_api
from aeraspace.api.search import search
from aeraspace.tests.test_chat import make_user

USERS = ("pj-alice@example.com", "pj-bob@example.com", "pj-carol@example.com")


def notifications(user, kind):
	return frappe.get_all(
		"AS Notification", filters={"user": user, "notification_type": kind}, fields=["task", "preview"]
	)


class TestProjects(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.alice, cls.bob, cls.carol = (make_user(u) for u in USERS)

	def setUp(self):
		frappe.db.delete("AS Notification", {"user": ("in", USERS)})

	def project(self, visibility="Private", members=None):
		suffix = frappe.generate_hash(length=5)
		with self.set_user(self.alice):
			return project_api.create_project(
				f"Shopify {suffix}",
				f"S{suffix.upper()[:4]}",
				"Sync work",
				visibility,
				members=members if members is not None else [self.bob],
			)

	def test_project_creates_channel_with_members(self):
		name = self.project()
		project = frappe.get_doc("AS Project", name)
		channel = frappe.get_doc("AS Channel", project.channel)
		self.assertEqual(channel.project, name)
		self.assertEqual(channel.channel_type, "Private")
		members = set(frappe.get_all("AS Channel Member", filters={"channel": channel.name}, pluck="user"))
		self.assertEqual(members, {self.alice, self.bob})

	def test_private_project_hidden_from_non_members(self):
		name = self.project()
		with self.set_user(self.carol):
			self.assertNotIn(name, [p.name for p in project_api.get_projects()])
			self.assertRaises(frappe.PermissionError, project_api.get_project, name)
			self.assertRaises(frappe.PermissionError, task_api.get_tasks, name)

	def test_public_project_readable_but_members_edit(self):
		name = self.project("Public")
		with self.set_user(self.alice):
			task = task_api.create_task(name, "Fix inventory sync")
		with self.set_user(self.carol):
			self.assertEqual([t.name for t in task_api.get_tasks(name)], [task.name])
			self.assertRaises(frappe.PermissionError, task_api.update_task, task.name, status="Done")

	def test_task_ids_are_sequential_per_project(self):
		name = self.project()
		key = frappe.db.get_value("AS Project", name, "project_key")
		with self.set_user(self.alice):
			first = task_api.create_task(name, "One")
			second = task_api.create_task(name, "Two")
		self.assertEqual((first.name, second.name), (f"{key}-1", f"{key}-2"))

	def test_assignment_and_status_notifications(self):
		name = self.project()
		with self.set_user(self.alice):
			task = task_api.create_task(name, "Review PR", assignee=self.bob)
		self.assertEqual([n.task for n in notifications(self.bob, "Assignment")], [task.name])

		with self.set_user(self.bob):
			updated = task_api.update_task(task.name, status="Done")
		self.assertEqual(updated.status, "Done")
		self.assertTrue(updated.completed_on)
		self.assertEqual(len(notifications(self.alice, "Task Update")), 1)  # reporter hears about it
		self.assertEqual(notifications(self.bob, "Task Update"), [])  # not about their own change

		with self.set_user(self.bob):
			reopened = task_api.update_task(task.name, status="In Progress")
		self.assertIsNone(reopened.completed_on)

	def test_assignee_must_be_project_member(self):
		name = self.project()
		with self.set_user(self.alice):
			self.assertRaises(frappe.ValidationError, task_api.create_task, name, "Nope", assignee=self.carol)

	def test_create_task_from_message(self):
		name = self.project()
		channel = frappe.db.get_value("AS Project", name, "channel")
		with self.set_user(self.bob):
			message = chat.send_message(channel, "Shopify inventory sync is failing")
		with self.set_user(self.alice):
			task = task_api.create_task(name, "Investigate inventory sync", source_message=message.name)
			details = task_api.get_task(task.name)
		self.assertEqual(details.source.channel, channel)

	def test_comments_notify_and_mentions(self):
		name = self.project(members=[self.bob, self.carol])
		with self.set_user(self.alice):
			task = task_api.create_task(name, "Write tests", assignee=self.bob)
			task_api.add_comment(task.name, f"<@{self.carol}> can you pair on this?")
			details = task_api.get_task(task.name)
		self.assertEqual(len(details.comments), 1)
		self.assertTrue(details.comments[0]["content"].startswith(f"<@{self.carol}>"))  # not html-escaped
		self.assertEqual(len(notifications(self.carol, "Mention")), 1)
		self.assertEqual(len(notifications(self.bob, "Task Update")), 1)

	def test_reorder_and_delete_rules(self):
		name = self.project()
		with self.set_user(self.alice):
			a = task_api.create_task(name, "A")
			b = task_api.create_task(name, "B")
			task_api.reorder(name, "Todo", [b.name, a.name])
			self.assertEqual([t.name for t in task_api.get_tasks(name)], [b.name, a.name])
		with self.set_user(self.bob):  # neither reporter nor admin
			self.assertRaises(frappe.PermissionError, task_api.delete_task, a.name)
		with self.set_user(self.alice):
			task_api.delete_task(a.name)
		self.assertFalse(frappe.db.exists("AS Task", a.name))

	def test_my_tasks_across_projects(self):
		one, two = self.project(), self.project()
		with self.set_user(self.alice):
			task_api.create_task(one, "In one", assignee=self.bob)
			task_api.create_task(two, "In two", assignee=self.bob)
			task_api.create_task(two, "Alice's own", assignee=self.alice)
		with self.set_user(self.bob):
			mine = {t.title for t in task_api.get_tasks(assignee="me")}
		self.assertTrue({"In one", "In two"} <= mine)
		self.assertNotIn("Alice's own", mine)

	def test_tasks_in_search(self):
		name = self.project()
		with self.set_user(self.alice):
			task_api.create_task(name, "Unicommerce invoice zzqq issue")
			self.assertEqual([t.title for t in search("zzqq")["tasks"]], ["Unicommerce invoice zzqq issue"])
		with self.set_user(self.carol):
			self.assertEqual(search("zzqq")["tasks"], [])
