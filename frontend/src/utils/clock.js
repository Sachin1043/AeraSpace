// 3725 -> "01:02:05"
export function formatClock(totalSeconds) {
	const s = Math.max(0, Math.floor(totalSeconds || 0));
	const pad = (n) => String(n).padStart(2, "0");
	return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

// 18900 -> "5h 15m", 600 -> "10m"
export function formatHours(totalSeconds) {
	const m = Math.max(0, Math.floor((totalSeconds || 0) / 60));
	const h = Math.floor(m / 60);
	if (!h) return `${m}m`;
	return m % 60 ? `${h}h ${m % 60}m` : `${h}h`;
}
