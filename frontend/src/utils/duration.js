// "3h 20m", "3h", "20m", "1.5h", "1.5", "2:30" -> minutes. A bare number means hours.
export function parseDuration(input) {
	const text = String(input || "")
		.trim()
		.toLowerCase();
	if (!text) return null;
	const clock = text.match(/^(\d{1,2}):([0-5]\d)$/);
	if (clock) return Number(clock[1]) * 60 + Number(clock[2]);
	if (/^\d+(\.\d+)?$/.test(text)) return Math.round(Number(text) * 60);
	const match = text.match(
		/^(?:(\d+(?:\.\d+)?)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*m(?:in(?:ute)?s?)?)?$/
	);
	if (!match || (!match[1] && !match[2])) return null;
	return Math.round(Number(match[1] || 0) * 60) + Number(match[2] || 0);
}

export function formatDuration(minutes) {
	const m = Math.round(Number(minutes) || 0);
	if (!m) return "0m";
	const h = Math.floor(m / 60);
	const rest = m % 60;
	return [h && `${h}h`, rest && `${rest}m`].filter(Boolean).join(" ");
}
