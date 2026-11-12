// colours for each day's attendance status (Last 7 days list and calendar)
export const STATUS_STYLES = {
	Present: { badge: "bg-surface-green-2 text-ink-green-3", dot: "bg-green-500" },
	"Half Day": { badge: "bg-surface-amber-2 text-ink-amber-3", dot: "bg-amber-500" },
	"Missed Check-out": { badge: "bg-surface-amber-2 text-ink-amber-3", dot: "bg-orange-500" },
	Absent: { badge: "bg-surface-red-2 text-ink-red-4", dot: "bg-red-500" },
	"On Leave": { badge: "bg-surface-blue-2 text-ink-blue-3", dot: "bg-blue-500" },
	"Work From Home": { badge: "bg-surface-blue-2 text-ink-blue-3", dot: "bg-violet-500" },
	Holiday: { badge: "bg-surface-gray-2 text-ink-gray-6", dot: "bg-gray-400" },
	"Weekly Off": { badge: "bg-surface-gray-2 text-ink-gray-6", dot: "bg-gray-400" },
	"Not Checked In": { badge: "bg-surface-gray-2 text-ink-gray-6", dot: "bg-gray-400" },
	Upcoming: { badge: "bg-surface-gray-1 text-ink-gray-5", dot: "" },
	"Not Joined": { badge: "bg-surface-gray-1 text-ink-gray-5", dot: "" },
};

export function statusStyle(status) {
	return STATUS_STYLES[status] || STATUS_STYLES.Upcoming;
}
