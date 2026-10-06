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
			You didn't check out on {{ attendance.data.missed_checkout }}. Ask HR to correct it.
		</div>

		<dl class="mt-4 grid grid-cols-3 gap-y-4 sm:grid-cols-6">
			<div v-for="stat in stats" :key="stat.label">
				<dt class="text-2xs uppercase tracking-wide text-ink-gray-5">{{ stat.label }}</dt>
				<dd class="mt-1 text-base font-medium tabular-nums" :class="stat.class">
					{{ stat.value }}
				</dd>
			</div>
		</dl>
	</section>
</template>

<script setup>
import { computed } from "vue";
import { Button } from "frappe-ui";
import { useAttendance } from "@/stores/attendance";
import { formatHours } from "@/utils/clock";
import LucideCoffee from "~icons/lucide/coffee";

const attendance = useAttendance();
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
	},
]);
</script>
