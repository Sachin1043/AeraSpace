import { ref } from "vue";

// 'light' | 'dark' | 'system' — remembered per browser; 'system' follows the OS setting live
const STORAGE_KEY = "aeraspace-theme";
const THEMES = ["light", "dark", "system"];
const media = window.matchMedia("(prefers-color-scheme: dark)");

function stored() {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		return THEMES.includes(value) ? value : "system";
	} catch (e) {
		return "system";
	}
}

export const theme = ref(stored());

function apply() {
	const resolved = theme.value === "system" ? (media.matches ? "dark" : "light") : theme.value;
	document.documentElement.setAttribute("data-theme", resolved);
	// native controls (date pickers, scrollbars, selects) follow along
	document.documentElement.style.colorScheme = resolved;
}

export function setTheme(value) {
	theme.value = THEMES.includes(value) ? value : "system";
	try {
		localStorage.setItem(STORAGE_KEY, theme.value);
	} catch (e) {
		// storage unavailable (e.g. private mode): the choice just isn't remembered
	}
	apply();
}

media.addEventListener("change", () => theme.value === "system" && apply());
apply();
