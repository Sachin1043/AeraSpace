import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { call, dayjs, dayjsLocal, toast } from "frappe-ui";

import { useSocket } from "@/socket";
import { showError } from "@/stores/chat";
import { formatHours } from "@/utils/clock";

const API = "aeraspace.api.attendance";

// check in / break / check out, stored as HRMS Employee Checkins on the server
export const useAttendance = defineStore("attendance", () => {
	// state: "out" | "working" | "break"; today: worked/break/late seconds from the server
	const data = ref({ enabled: false, state: "out", since: null, today: {} });
	const busy = ref(false);
	const now = ref(Date.now());
	let offset = 0; // server time minus this computer's time
	let timer = null;
	let initialized = false;

	// server times are naive, in the site timezone
	const serverMs = (value) => dayjs.tz(value, window.system_timezone).valueOf();

	function apply(state) {
		if (state.server_now) offset = serverMs(state.server_now) - Date.now();
		data.value = { today: {}, ...state };
		clearInterval(timer);
		timer = null;
		now.value = Date.now();
		if (state.state === "working" || state.state === "break") {
			timer = setInterval(() => (now.value = Date.now()), 1000);
		}
	}

	const state = computed(() => data.value.state);
	const enabled = computed(() => data.value.enabled);

	// seconds since the current state began (ticks every second)
	const runningSeconds = computed(() =>
		data.value.since
			? Math.max(0, (now.value + offset - serverMs(data.value.since)) / 1000)
			: 0
	);
	const workedSeconds = computed(
		() =>
			(data.value.today.worked_seconds || 0) +
			(state.value === "working" ? runningSeconds.value : 0)
	);
	const breakSeconds = computed(
		() =>
			(data.value.today.break_seconds || 0) +
			(state.value === "break" ? runningSeconds.value : 0)
	);
	const remainingSeconds = computed(() =>
		Math.max(0, (data.value.today.expected_seconds || 0) - workedSeconds.value)
	);
	const sinceTime = computed(() => time(data.value.since));

	function time(value) {
		return value ? dayjsLocal(value).format("h:mm A") : "";
	}

	async function load() {
		apply(await call(`${API}.get_state`));
	}

	async function act(method, successMessage) {
		if (busy.value) return;
		busy.value = true;
		try {
			apply(await call(`${API}.${method}`));
			if (successMessage) toast.create({ message: successMessage(), type: "success" });
		} catch (error) {
			showError(error);
			load();
		} finally {
			busy.value = false;
		}
	}

	const checkIn = () => act("check_in");
	const startBreak = () => act("start_break");
	const endBreak = () => act("end_break");
	const checkOut = () =>
		act("check_out", () => `Checked out · ${formatHours(workedSeconds.value)} worked today`);

	async function init() {
		if (initialized) return;
		initialized = true;
		const socket = useSocket();
		socket?.on("as_attendance", apply);
		socket?.io.on("reconnect", load);
		await load();
	}

	return {
		data,
		busy,
		state,
		enabled,
		runningSeconds,
		workedSeconds,
		breakSeconds,
		remainingSeconds,
		sinceTime,
		time,
		init,
		load,
		checkIn,
		startBreak,
		endBreak,
		checkOut,
	};
});
