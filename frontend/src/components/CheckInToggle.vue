<template>
	<!-- like Cliq's work toggle: on = checked in; the coffee button takes a break -->
	<div v-if="attendance.enabled" class="flex items-center gap-2 border-b px-4 py-2.5">
		<div class="min-w-0 flex-1">
			<div class="text-sm font-medium" :class="labelClass">{{ label }}</div>
			<div class="truncate text-2xs text-ink-gray-5">{{ hint }}</div>
		</div>
		<Tooltip
			v-if="attendance.state !== 'out'"
			:text="onBreak ? 'End break' : 'Take a break'"
			placement="bottom"
		>
			<button
				class="rounded p-1 hover:bg-surface-gray-3 disabled:opacity-60"
				:class="onBreak ? 'text-ink-amber-3' : 'text-ink-gray-5 hover:text-ink-gray-8'"
				:aria-label="onBreak ? 'End break' : 'Take a break'"
				:aria-pressed="onBreak"
				:disabled="attendance.busy"
				@click="onBreak ? attendance.endBreak() : attendance.startBreak()"
			>
				<LucideCoffee class="size-4" />
			</button>
		</Tooltip>
		<button
			role="switch"
			:aria-checked="on"
			:aria-label="on ? 'Check out' : 'Check in'"
			:title="on ? 'Check out' : 'Check in'"
			:disabled="attendance.busy"
			class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:opacity-60"
			:class="on ? (onBreak ? 'bg-[#f5a623]' : 'bg-[#2ecc71]') : 'bg-surface-gray-4'"
			@click="toggle"
		>
			<span
				class="inline-block size-4 rounded-full bg-white shadow transition-transform"
				:class="on ? 'translate-x-[18px]' : 'translate-x-0.5'"
			/>
		</button>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Tooltip } from "frappe-ui";
import { useAttendance } from "@/stores/attendance";
import LucideCoffee from "~icons/lucide/coffee";

const attendance = useAttendance();
const on = computed(() => attendance.state !== "out");
const onBreak = computed(() => attendance.state === "break");

const label = computed(
	() => ({ out: "Check-in", working: "Checked in", break: "On break" }[attendance.state])
);
const labelClass = computed(
	() =>
		({ out: "text-ink-gray-7", working: "text-ink-green-3", break: "text-ink-amber-3" }[
			attendance.state
		])
);
const hint = computed(() => {
	if (attendance.state === "out") {
		const missed = attendance.data.missed_checkout;
		return missed ? `No check-out on ${missed}` : "You're checked out";
	}
	return `Since ${attendance.sinceTime}`;
});

function toggle() {
	if (!on.value) return attendance.checkIn();
	if (window.confirm("Check out now?")) attendance.checkOut();
}
</script>
