<template>
	<Dialog v-model="open" :options="{ title: 'My attendance', size: '4xl' }">
		<template #body-content>
			<!-- tabs -->
			<div class="mb-4 inline-flex rounded-lg bg-surface-gray-2 p-0.5">
				<button
					v-for="t in tabs"
					:key="t.value"
					class="flex items-center gap-1.5 rounded-md px-3 py-1 text-sm"
					:class="
						tab === t.value
							? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm'
							: 'text-ink-gray-6 hover:text-ink-gray-8'
					"
					@click="tab = t.value"
				>
					<component :is="t.icon" class="size-3.5" />
					{{ t.label }}
				</button>
			</div>

			<!-- last 7 days -->
			<div v-if="tab === 'week'" class="max-h-[65vh] space-y-2 overflow-y-auto">
				<div v-if="week.loading && !week.data" class="flex justify-center py-8">
					<LoadingIndicator class="size-5" />
				</div>
				<div
					v-for="day in weekDays"
					:key="day.date"
					class="rounded-lg border p-3"
					:class="{ 'border-outline-gray-3': day.date === todayDate }"
				>
					<DayHeader :day="day" :is-today="day.date === todayDate" />
					<DayAttendanceStats
						v-if="day.first_in"
						class="mt-3"
						:day="day"
						:is-today="day.date === todayDate"
					/>
				</div>
			</div>

			<!-- calendar -->
			<div v-else>
				<div class="mb-3 flex items-center gap-2">
					<Button variant="ghost" aria-label="Previous month" @click="shiftMonth(-1)">
						<LucideChevronLeft class="size-4" />
					</Button>
					<div class="w-36 text-center text-base font-semibold text-ink-gray-9">
						{{ month.format("MMMM YYYY") }}
					</div>
					<Button
						variant="ghost"
						aria-label="Next month"
						:disabled="month.isSame(dayjs(), 'month')"
						@click="shiftMonth(1)"
					>
						<LucideChevronRight class="size-4" />
					</Button>
					<LoadingIndicator v-if="monthData.loading" class="size-4" />
					<div class="ml-auto hidden gap-3 text-xs text-ink-gray-6 sm:flex">
						<span v-for="(label, i) in summary" :key="i">{{ label }}</span>
					</div>
				</div>

				<div class="grid grid-cols-7 gap-1 text-center">
					<div
						v-for="name in weekdays"
						:key="name"
						class="pb-1 text-2xs font-medium uppercase tracking-wide text-ink-gray-5"
					>
						{{ name }}
					</div>
					<div v-for="n in leadingBlanks" :key="'blank' + n" />
					<button
						v-for="day in monthDays"
						:key="day.date"
						class="flex h-16 flex-col items-start rounded-md border p-1.5 text-left transition-colors hover:bg-surface-gray-3"
						:class="[
							selected === day.date
								? 'border-outline-gray-3 bg-surface-gray-3'
								: 'border-transparent bg-surface-gray-2',
							{ 'opacity-50': day.status === 'Upcoming' },
						]"
						@click="selected = day.date"
					>
						<div class="flex w-full items-center justify-between">
							<span
								class="text-sm tabular-nums"
								:class="
									day.date === todayDate
										? 'flex size-5 items-center justify-center rounded-full bg-surface-gray-7 font-semibold text-ink-white'
										: 'text-ink-gray-8'
								"
								>{{ dayjs(day.date).date() }}</span
							>
							<span
								v-if="statusStyle(day.status).dot"
								class="size-2 rounded-full"
								:class="statusStyle(day.status).dot"
								:title="day.status"
							/>
						</div>
						<span class="mt-auto truncate text-xs tabular-nums text-ink-gray-6">
							{{ cellLabel(day) }}
						</span>
					</button>
				</div>

				<div v-if="selectedDay" class="mt-4 rounded-lg border p-3">
					<DayHeader :day="selectedDay" :is-today="selectedDay.date === todayDate" />
					<DayAttendanceStats
						v-if="selectedDay.first_in"
						class="mt-3"
						:day="selectedDay"
						:is-today="selectedDay.date === todayDate"
					/>
					<p v-else class="mt-2 text-sm text-ink-gray-5">{{ emptyText(selectedDay) }}</p>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from "vue";
import { Button, Dialog, LoadingIndicator, createResource, dayjs } from "frappe-ui";
import { useAttendance } from "@/stores/attendance";
import { formatHours } from "@/utils/clock";
import { statusStyle } from "@/utils/attendanceStatus";
import DayAttendanceStats from "./DayAttendanceStats.vue";
import LucideList from "~icons/lucide/list";
import LucideCalendar from "~icons/lucide/calendar-days";
import LucideChevronLeft from "~icons/lucide/chevron-left";
import LucideChevronRight from "~icons/lucide/chevron-right";

const open = defineModel({ type: Boolean, default: false });
const attendance = useAttendance();

const tabs = [
	{ value: "week", label: "Last 7 days", icon: LucideList },
	{ value: "calendar", label: "Calendar", icon: LucideCalendar },
];
const tab = ref("week");
const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const fmt = (d) => d.format("YYYY-MM-DD");

const week = createResource({ url: "aeraspace.api.attendance.get_history" });
const monthData = createResource({ url: "aeraspace.api.attendance.get_history" });
const month = ref(dayjs().startOf("month"));
const selected = ref(null);

const todayDate = computed(() => week.data?.today || monthData.data?.today || fmt(dayjs()));
const weekDays = computed(() => [...(week.data?.days || [])].reverse());
const monthDays = computed(() => monthData.data?.days || []);
const selectedDay = computed(() => monthDays.value.find((d) => d.date === selected.value));
// Monday-first grid
const leadingBlanks = computed(() => (month.value.day() + 6) % 7);

const summary = computed(() => {
	const days = monthDays.value;
	const count = (statuses) => days.filter((d) => statuses.includes(d.status)).length;
	const worked = days.reduce(
		(sum, d) =>
			sum + (d.date === todayDate.value ? attendance.workedSeconds : d.worked_seconds),
		0
	);
	return [
		`Present ${count(["Present", "Missed Check-out", "Work From Home"])}`,
		`Half day ${count(["Half Day"])}`,
		`Absent ${count(["Absent"])}`,
		`Late ${days.filter((d) => d.late_seconds).length}`,
		`Worked ${formatHours(worked)}`,
	];
});

function loadWeek() {
	const end = dayjs();
	week.submit({ from_date: fmt(end.subtract(6, "day")), to_date: fmt(end) });
}

function loadMonth() {
	const start = month.value;
	const end = start.endOf("month");
	monthData.submit({ from_date: fmt(start), to_date: fmt(end) });
	const today = dayjs();
	selected.value = today.isSame(start, "month") ? fmt(today) : fmt(start);
}

function shiftMonth(step) {
	month.value = month.value.add(step, "month");
	loadMonth();
}

function cellLabel(day) {
	const worked = day.date === todayDate.value ? attendance.workedSeconds : day.worked_seconds;
	if (day.first_in) return formatHours(worked);
	if (day.status === "Weekly Off") return "Off";
	if (["Holiday", "Absent", "On Leave"].includes(day.status)) return day.holiday || day.status;
	return "";
}

function emptyText(day) {
	return (
		{
			Absent: "No check-in on this day.",
			"Weekly Off": "Weekly off.",
			Holiday: `Holiday${day.holiday ? ` · ${day.holiday}` : ""}.`,
			Upcoming: "This day hasn't come yet.",
			"Not Checked In": "You haven't checked in today.",
			"Not Joined": "Before your joining date.",
			"On Leave": "On leave.",
		}[day.status] || "No check-ins."
	);
}

watch(
	open,
	(value) => {
		if (!value) return;
		loadWeek();
		loadMonth();
	},
	{ immediate: true }
);

// a day's title row: weekday, date and status badge
const DayHeader = defineComponent({
	props: { day: Object, isToday: Boolean },
	setup(props) {
		return () => {
			const date = dayjs(props.day.date);
			const style = statusStyle(props.day.status);
			return h("div", { class: "flex items-center gap-2" }, [
				h("span", { class: "text-base font-semibold text-ink-gray-9" }, [
					props.isToday ? "Today" : date.format("dddd"),
				]),
				h("span", { class: "text-sm text-ink-gray-5" }, date.format("D MMM YYYY")),
				h(
					"span",
					{
						class: `ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${style.badge}`,
					},
					props.day.holiday && !props.day.first_in
						? `${props.day.status} · ${props.day.holiday}`
						: props.day.status
				),
			]);
		};
	},
});
</script>
