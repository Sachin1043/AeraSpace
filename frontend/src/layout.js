import { ref, watch } from "vue";

// sidebar hidden/shown — remembered per browser
const KEY = "aeraspace-sidebar-collapsed";

function stored() {
	try {
		return localStorage.getItem(KEY) === "1";
	} catch (e) {
		return false;
	}
}

export const sidebarCollapsed = ref(stored());

watch(sidebarCollapsed, (value) => {
	try {
		localStorage.setItem(KEY, value ? "1" : "0");
	} catch (e) {
		// storage unavailable (e.g. private mode): the choice just isn't remembered
	}
});
