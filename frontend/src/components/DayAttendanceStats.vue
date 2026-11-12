<template>
	<dl class="grid grid-cols-3 gap-y-3 sm:grid-cols-7">
		<div v-for="stat in stats" :key="stat.label">
			<dt class="text-2xs uppercase tracking-wide text-ink-gray-5">{{ stat.label }}</dt>
			<dd
				class="mt-0.5 text-base font-medium tabular-nums"
				:class="stat.class || 'text-ink-gray-9'"
			>
				{{ stat.value }}
			</dd>
		</div>
	</dl>
</template>

<script setup>
import { computed } from "vue";
import { useAttendance } from "@/stores/attendance";
import { formatHours } from "@/utils/clock";

// one day's numbers; today's worked/break keep ticking from the attendance store
const props = defineProps({
	day: { type: Object, required: true },
	isToday: { type: Boolean, default: false },
});

const attendance = useAttendance();

const stats = computed(() => {
	const d = props.day;
	const hasTime = !!d.first_in;
	const worked = props.isToday ? attendance.workedSeconds : d.worked_seconds;
	const breaks = props.isToday ? attendance.breakSeconds : d.break_seconds;
	const short = Math.max(0, (d.expected_seconds || 0) - worked);
	const dash = (value, format) => (hasTime ? format(value) : "—");
	return [
		{ label: "Check-in", value: attendance.time(d.first_in) || "—" },
		{
			label: "Check-out",
			value: attendance.time(d.last_out) || (d.open && !props.isToday ? "Missed" : "—"),
			class: d.open && !props.isToday ? "text-ink-amber-3" : "",
		},
		{ label: "Worked", value: dash(worked, formatHours) },
		{ label: "Break", value: dash(breaks, formatHours) },
		{ label: "Expected", value: hasTime ? formatHours(d.expected_seconds) : "—" },
		{
			label: props.isToday ? "Remaining" : "Short by",
			value: hasTime ? (short ? formatHours(short) : "—") : "—",
			class: !props.isToday && hasTime && short ? "text-ink-amber-3" : "",
		},
		{
			label: "Late",
			value: d.late_seconds ? formatHours(d.late_seconds) : "—",
			class: d.late_seconds ? "text-ink-red-4" : "",
		},
	];
});
</script>
