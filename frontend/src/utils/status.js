// One status at a time. Each choice sets the dot (availability) and, for custom ones, a message.
export const DEFAULT_STATUSES = [
	{
		label: "Available",
		value: "Auto",
		status: "online",
		hint: "Shows Away automatically when you are idle",
	},
	{ label: "Away", value: "Away", status: "away" },
	{ label: "Busy", value: "Busy", status: "busy" },
	{
		label: "Invisible",
		value: "Invisible",
		status: "invisible",
		hint: "Appear offline to everyone",
	},
	{
		label: "Do not disturb",
		value: "Do Not Disturb",
		status: "dnd",
		hint: "Pause popups and desktop notifications",
	},
];

// custom statuses carry the dot colour that fits them
export const CUSTOM_STATUSES = [
	{ emoji: "📅", text: "In a meeting", value: "Busy" },
	{ emoji: "☕", text: "Coffee break", value: "Away" },
	{ emoji: "🍴", text: "Lunch", value: "Away" },
	{ emoji: "🚆", text: "Travelling", value: "Away" },
	{ emoji: "🏠", text: "Working from home", value: "Auto" },
	{ emoji: "💻", text: "Focus time", value: "Do Not Disturb" },
	{ emoji: "🏖️", text: "On leave", value: "Away" },
];

export const AVAILABILITY_OPTIONS = DEFAULT_STATUSES.map((s) => ({
	label: s.label,
	value: s.value,
}));
