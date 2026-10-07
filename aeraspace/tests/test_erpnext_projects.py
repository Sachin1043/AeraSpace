import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from aeraspace.api import project as project_api
from aeraspace.api import task as task_api
from aeraspace.tests.test_chat import make_user

ALICE, BOB = "ep-alice@example.com", "ep-bob@example.com"


class TestErpnextProjects(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(ALICE)
		make_user(BOB)

	def setUp(self):
		suffix = frappe.generate_hash(length=4).upper()
		with self.set_user(ALICE):
			self.project = project_api.create_project(f"Erp {suffix}", f"E{suffix}", members=[BOB])

	def task(self, **values):
		with self.set_user(ALICE):
			return task_api.create_task(self.project, values.pop("title", "Ship it"), **values)

	def test_project_is_an_erpnext_project_named_by_key(self):
		doc = frappe.get_doc("Project", self.project)
		self.assertEqual(doc.as_project_key, self.project)
		self.assertEqual(
			(doc.status, doc.as_status, doc.percent_complete_method), ("Open", "Active", "Manual")
		)
		self.assertTrue(doc.as_channel)
		with self.set_user(ALICE):
			project_api.update_project(self.project, status="On Hold")
		self.assertEqual(frappe.db.get_value("Project", self.project, "status"), "On hold")

	def test_board_status_drives_erpnext_status(self):
		task = self.task(status="Code Review")
		self.assertEqual(
			frappe.db.get_value("Task", task.name, ["status", "as_status"]), ("Working", "Code Review")
		)
		with self.set_user(BOB):
			done = task_api.update_task(task.name, status="Done")
		self.assertEqual(done.status, "Done")
		row = frappe.db.get_value("Task", task.name, ["status", "completed_on", "completed_by"], as_dict=True)
		self.assertEqual((row.status, str(row.completed_on), row.completed_by), ("Completed", today(), BOB))

	def test_desk_status_change_moves_the_card(self):
		task = self.task(status="Backlog")
		doc = frappe.get_doc("Task", task.name)
		doc.status = "Pending Review"
		doc.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Task", task.name, "as_status"), "Testing")
		# Open matches Backlog too, so a Backlog card created as Open stays put
		self.assertEqual(
			frappe.db.get_value("Task", self.task(status="Backlog").name, "as_status"), "Backlog"
		)

	def test_task_created_in_desk_shows_on_board(self):
		doc = frappe.get_doc(
			{"doctype": "Task", "subject": "From Desk", "project": self.project, "status": "Working"}
		).insert(ignore_permissions=True)
		with self.set_user(BOB):
			board = {t.name: t for t in task_api.get_tasks(self.project)}
		self.assertIn(doc.name, board)
		self.assertEqual((board[doc.name].title, board[doc.name].status), ("From Desk", "In Progress"))
		self.assertEqual(board[doc.name].project, self.project)

	def test_overdue_job_does_not_move_cards(self):
		from erpnext.projects.doctype.task.task import set_tasks_as_overdue

		task = self.task(status="In Progress", due_date=add_days(today(), -2))
		set_tasks_as_overdue()
		self.assertEqual(
			frappe.db.get_value("Task", task.name, ["status", "as_status"]), ("Overdue", "In Progress")
		)
		with self.set_user(ALICE):
			self.assertEqual(task_api.get_task(task.name).status, "In Progress")

	def test_assignee_is_mirrored_quietly(self):
		task = self.task(assignee=BOB)
		todos = frappe.get_all(
			"ToDo",
			filters={"reference_type": "Task", "reference_name": task.name, "status": "Open"},
			pluck="allocated_to",
		)
		self.assertEqual(todos, [BOB])
		self.assertIn(BOB, frappe.parse_json(frappe.db.get_value("Task", task.name, "_assign")))
		self.assertFalse(frappe.db.exists("Notification Log", {"for_user": BOB, "document_name": task.name}))

		with self.set_user(ALICE):
			task_api.update_task(task.name, assignee=ALICE)
		self.assertEqual(
			frappe.get_all(
				"ToDo",
				filters={"reference_type": "Task", "reference_name": task.name, "status": "Open"},
				pluck="allocated_to",
			),
			[ALICE],
		)

	def test_done_closes_assignment_and_reopening_restores_it(self):
		task = self.task(assignee=BOB)
		open_todos = {"reference_type": "Task", "reference_name": task.name, "status": "Open"}
		with self.set_user(BOB):
			task_api.update_task(task.name, status="Done")
			self.assertFalse(frappe.db.exists("ToDo", open_todos))
			task_api.update_task(task.name, status="Todo")
		self.assertTrue(frappe.db.exists("ToDo", open_todos))

	def test_no_erpnext_emails(self):
		before = frappe.db.count("Email Queue")
		self.task(assignee=BOB, status="Todo")
		self.assertEqual(frappe.db.count("Email Queue"), before)
