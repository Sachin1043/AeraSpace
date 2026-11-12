import { dayjs } from "frappe-ui";

// the server stores naive datetimes in the site's timezone; show them in the viewer's own
export function fromSite(value) {
	return dayjs.tz(value, window.system_timezone).local();
}

// "2026-11-14" + "15:30" picked in the browser -> naive site-timezone string for the server
export function toSite(date, time) {
	return dayjs
		.tz(`${date} ${time}`, dayjs.tz.guess())
		.tz(window.system_timezone)
		.format("YYYY-MM-DD HH:mm:ss");
}
