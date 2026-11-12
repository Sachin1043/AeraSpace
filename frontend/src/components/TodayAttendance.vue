<template>
	<section v-if="attendance.enabled" class="rounded-lg border p-4">
		<div class="flex items-center gap-3">
			<h2 class="flex-1 text-base font-semibold text-ink-gray-9">Today's attendance</h2>
			<span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="badge.class">
				{{ badge.label }}
			</span>
			<Button
				v-if="attendance.state === 'out'"
				variant="solid"
				:loading="attendance.busy"
				@click="attendance.checkIn()"
			>
				Check in
			</Button>
			<Button
				v-else-if="attendance.state === 'working'"
				:loading="attendance.busy"
				@click="attendance.startBreak()"
			>
				<template #prefix><LucideCoffee class="size-4" /></template>
				Take a break
			</Button>
			<Button v-else :loading="attendance.busy" @click="attendance.endBreak()">
				End break
			</Button>
		</div>

		<div
			v-if="attendance.data.missed_checkout"
			class="mt-3 rounded bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
		>
			You didn't check out on
			{{ dayjs(attendance.data.missed_checkout).format("ddd, D MMM") }}, so it was counted
			until 6 PM. Worked longer?
			<router-link
				:to="{
					name: 'Requests',
					query: { new: 'correction', date: attendance.data.missed_checkout },
				}"
				class="font-medium underline"
				>Request a correction</router-link
			>
		</div>

		<dl
			class="mt-4 grid grid-cols-3 gap-y-4"
			:class="stats.length > 6 ? 'sm:grid-cols-7' : 'sm:grid-cols-6'"
		>
			<div v-for="stat in stats" :key="stat.label">
				<dt class="text-2xs uppercase tracking-wide text-ink-gray-5">{{ stat.label }}</dt>
				<dd class="mt-1 text-base font-medium tabular-nums" :class="stat.class">
					{{ stat.value }}
				</dd>
				<dd v-if="stat.hint" class="text-2xs" :class="stat.hintClass || 'text-ink-gray-5'">
					{{ stat.hint }}
				</dd>
			</div>
		</dl>

		<div class="mt-3 flex justify-end border-t pt-3">
			<button
				class="flex items-center gap-1 text-sm font-medium text-ink-blue-3 hover:underline"
				@click="showHistory = true"
			>
				<LucideCalendarDays class="size-4" />
				View attendance
			</button>
		</div>
		<AttendanceHistory v-if="showHistory" v-model="showHistory" />
	</section>
</template>

<script setup>
import { computed, ref } from "vue";
import { Button, dayjs } from "frappe-ui";
import { useAttendance } from "@/stores/attendance";
import { formatHours } from "@/utils/clock";
import AttendanceHistory from "./AttendanceHistory.vue";
import LucideCoffee from "~icons/lucide/coffee";
import LucideCalendarDays from "~icons/lucide/calendar-days";

const attendance = useAttendance();
const showHistory = ref(false);
const today = computed(() => attendance.data.today || {});

const badge = computed(
	() =>
		({
			out: { label: "Checked out", class: "bg-surface-gray-2 text-ink-gray-6" },
			working: { label: "Working", class: "bg-surface-green-2 text-ink-green-3" },
			break: { label: "On break", class: "bg-surface-amber-2 text-ink-amber-3" },
		}[attendance.state])
);

const stats = computed(() => [
	{ label: "Check-in", value: attendance.time(today.value.first_in) || "—" },
	{ label: "Worked", value: formatHours(attendance.workedSeconds) },
	{ label: "Break", value: formatHours(attendance.breakSeconds) },
	{ label: "Expected", value: formatHours(today.value.expected_seconds) },
	{ label: "Remaining", value: formatHours(attendance.remainingSeconds) },
	{
		label: "Late",
		value: today.value.late_seconds ? formatHours(today.value.late_seconds) : "—",
		class: today.value.late_seconds ? "text-ink-red-4" : "text-ink-gray-9",
		...lateHint.value,
	},
	...(overtime.value
		? [{ label: "Overtime", value: formatHours(overtime.value), class: "text-ink-blue-3" }]
		: []),
]);

// every 3rd late day of a month counts as a half day
const lateHint = computed(() => {
	const count = attendance.data.late_this_month || 0;
	const every = attendance.data.late_days_per_half_day || 3;
	if (!count) return {};
	const left = every - (count % every);
	return {
		hint: left === 1 ? `${count} late · next one is a half day` : `${count} late this month`,
		hintClass: left === 1 ? "text-ink-amber-3" : "text-ink-gray-5",
	};
});
const overtime = computed(() =>
	Math.max(0, attendance.workedSeconds - (attendance.data.overtime_after_seconds || 9 * 3600))
);
</script>
