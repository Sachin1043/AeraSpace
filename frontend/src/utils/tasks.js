import { dayjs } from "frappe-ui";

export const STATUSES = ["Backlog", "Todo", "In Progress", "Code Review", "Testing", "Done"];
export const PRIORITIES = ["Low", "Medium", "High", "Urgent"];

export const STATUS_COLORS = {
	Backlog: "bg-gray-300",
	Todo: "bg-gray-500",
	"In Progress": "bg-blue-500",
	"Code Review": "bg-violet-500",
	Testing: "bg-amber-500",
	Done: "bg-green-500",
};

export const PRIORITY_STYLES = {
	Low: "bg-surface-gray-2 text-ink-gray-6",
	Medium: "bg-surface-blue-1 text-ink-blue-3",
	High: "bg-surface-orange-1 text-ink-amber-3",
	Urgent: "bg-surface-red-2 text-ink-red-4",
};

// AeraSpace task names are "<PROJECT KEY>-<number>" (a project's name is its key); fallback only,
// since tasks made in Desk are named TASK-2026-00001
export function projectOf(task) {
	return (task || "").replace(/-\d+$/, "");
}

export function dueLabel(task) {
	if (!task.due_date) return null;
	const due = dayjs(task.due_date);
	const today = dayjs().startOf("day");
	const days = due.diff(today, "day");
	const overdue = days < 0 && task.status !== "Done";
	let text = due.format(due.year() === today.year() ? "MMM D" : "MMM D, YYYY");
	if (days === 0) text = "Today";
	else if (days === 1) text = "Tomorrow";
	return { text, overdue, soon: days >= 0 && days <= 2 && task.status !== "Done" };
}
