import { defineStore } from "pinia";
import { ref } from "vue";
import { call } from "frappe-ui";

import { useSocket } from "@/socket";
import { fromSite } from "@/utils/siteTime";

const API = "aeraspace.api.meeting";
const REMIND_BEFORE_MS = 5 * 60 * 1000;

// my upcoming meetings, plus the "starting soon" pop-up timed in the browser
export const useMeetings = defineStore("meetings", () => {
	const upcoming = ref([]);
	const reminder = ref(null); // meeting to pop up now
	const version = ref(0);
	const shown = new Set(); // "<meeting>@<start>" already popped up
	let timers = [];
	let initialized = false;

	async function load() {
		upcoming.value = await call(`${API}.get_meetings`, { scope: "upcoming" }).catch(
			() => upcoming.value
		);
		schedule();
	}

	function schedule() {
		timers.forEach(clearTimeout);
		timers = [];
		for (const m of upcoming.value) {
			if (m.status !== "Scheduled" || m.my_response === "Declined") continue;
			const key = `${m.name}@${m.starts_at}`;
			const wait = fromSite(m.starts_at).valueOf() - REMIND_BEFORE_MS - Date.now();
			const ended = fromSite(m.ends_at).valueOf() < Date.now();
			if (shown.has(key) || ended) continue;
			// setTimeout can't wait longer than ~24 days; anything that far is re-planned on reload
			if (wait > 2 ** 31 - 1) continue;
			timers.push(setTimeout(() => pop(m, key), Math.max(0, wait)));
		}
	}

	function pop(meeting, key) {
		shown.add(key);
		reminder.value = meeting;
		if (
			document.visibilityState !== "visible" &&
			window.Notification?.permission === "granted"
		) {
			new Notification(`${meeting.title} is starting`, {
				body: `${fromSite(meeting.starts_at).format("h:mm A")} · ${meeting.duration} min`,
				tag: `meeting-${meeting.name}`,
			});
		}
	}

	function changed() {
		version.value += 1;
		load();
	}

	function init() {
		if (initialized) return;
		initialized = true;
		useSocket()?.on("as_meetings", changed);
		load();
	}

	return { upcoming, reminder, version, init, load, changed };
});

export function googleCalendarLink(m) {
	const fmt = (d) => d.utc().format("YYYYMMDD[T]HHmmss[Z]");
	const params = new URLSearchParams({
		action: "TEMPLATE",
		text: m.title,
		dates: `${fmt(fromSite(m.starts_at))}/${fmt(fromSite(m.ends_at))}`,
		details: `${m.agenda ? m.agenda + "\n\n" : ""}Join in AeraSpace: ${
			window.location.origin
		}/aeraspace/meetings`,
	});
	return `https://calendar.google.com/calendar/render?${params}`;
}
