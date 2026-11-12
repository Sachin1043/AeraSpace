import { defineStore } from "pinia";
import { ref } from "vue";
import { call } from "frappe-ui";

import { useSocket } from "@/socket";

const API = "aeraspace.api.hr_requests";

// leave / WFH / attendance-correction requests: options and the approvals badge
export const useRequests = defineStore("requests", () => {
	const options = ref({ leave_types: [], taken_this_year: {}, pending_approvals: 0 });
	const version = ref(0); // bumps on every change, so open pages reload
	let initialized = false;

	async function load() {
		options.value = await call(`${API}.get_options`).catch(() => options.value);
	}

	function changed() {
		version.value += 1;
		load();
	}

	function init() {
		if (initialized) return;
		initialized = true;
		useSocket()?.on("as_requests", changed);
		load();
	}

	return { options, version, init, load, changed };
});

export const KIND_LABELS = {
	leave: "Leave",
	wfh: "Work from home",
	correction: "Attendance correction",
};

export const REQUEST_STATUS_STYLES = {
	Pending: "bg-surface-amber-2 text-ink-amber-3",
	Approved: "bg-surface-green-2 text-ink-green-3",
	Rejected: "bg-surface-red-2 text-ink-red-4",
	Cancelled: "bg-surface-gray-2 text-ink-gray-6",
};
