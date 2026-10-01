<template>
	<div class="mx-auto max-w-5xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Timesheets</h1>
				<p class="text-base text-ink-gray-6">Log time against projects and tasks.</p>
			</div>
			<div class="flex items-center gap-2">
				<div class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="t in ['My week', 'Reports']"
						:key="t"
						class="rounded px-3 py-1 text-sm"
						:class="
							tab === t
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="tab = t"
					>
						{{ t }}
					</button>
				</div>
				<Button variant="solid" @click="openLog()">
					<template #prefix><LucidePlus class="size-4" /></template>
					Log time
				</Button>
			</div>
		</div>

		<!-- my week -->
		<template v-if="tab === 'My week'">
			<div class="mt-5 flex items-center gap-2">
				<Button size="sm" @click="shiftWeek(-1)"
					><LucideChevronLeft class="size-4"
				/></Button>
				<Button size="sm" @click="weekStart = startOfWeek(dayjs())">This week</Button>
				<Button size="sm" :disabled="isCurrentWeek" @click="shiftWeek(1)"
					><LucideChevronRight class="size-4"
				/></Button>
				<span class="ml-2 text-base font-medium text-ink-gray-8">
					{{ weekStart.format("D MMM") }} –
					{{ weekStart.add(6, "day").format("D MMM YYYY") }}
				</span>
				<span class="ml-auto text-base text-ink-gray-7"
					>Total <b>{{ formatDuration(weekTotal) }}</b></span
				>
			</div>

			<div class="mt-3 grid grid-cols-7 gap-2">
				<div
					v-for="day in days"
					:key="day.key"
					class="rounded-lg border px-2 py-2 text-center"
					:class="day.isToday ? 'border-outline-gray-4 bg-surface-gray-1' : ''"
				>
					<div class="text-xs text-ink-gray-5">{{ day.date.format("ddd D") }}</div>
					<div
						class="mt-0.5 text-base font-semibold"
						:class="day.minutes ? 'text-ink-gray-9' : 'text-ink-gray-4'"
					>
						{{ day.minutes ? formatDuration(day.minutes) : "—" }}
					</div>
				</div>
			</div>

			<div v-if="logs.loading && !logs.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<div
				v-else-if="!logs.data?.length"
				class="mt-5 rounded-lg border px-4 py-10 text-center text-base text-ink-gray-5"
			>
				No time logged this week. Click <b>Log time</b> to add an entry.
			</div>
			<div v-else class="mt-5 space-y-4">
				<section v-for="day in days.filter((d) => d.entries.length)" :key="day.key">
					<div class="mb-1 flex items-center justify-between text-sm">
						<span class="font-semibold text-ink-gray-8">{{
							day.date.format("dddd, D MMM")
						}}</span>
						<span class="text-ink-gray-6">{{ formatDuration(day.minutes) }}</span>
					</div>
					<div class="divide-y rounded-lg border">
						<div
							v-for="e in day.entries"
							:key="e.name"
							class="group flex items-center gap-3 px-3 py-2"
						>
							<span class="w-16 shrink-0 text-base font-medium text-ink-gray-9">{{
								formatDuration(e.minutes)
							}}</span>
							<div class="min-w-0 flex-1">
								<div class="truncate text-base text-ink-gray-8">
									{{ e.project_name
									}}<span v-if="e.task" class="text-ink-gray-5">
										· {{ e.task }} {{ e.task_title }}</span
									>
								</div>
								<div v-if="e.description" class="truncate text-sm text-ink-gray-5">
									{{ e.description }}
								</div>
							</div>
							<div class="hidden items-center gap-1 group-hover:flex">
								<Button size="sm" variant="ghost" title="Edit" @click="openLog(e)"
									><LucidePencil class="size-3.5"
								/></Button>
								<Button size="sm" variant="ghost" title="Delete" @click="remove(e)"
									><LucideTrash2 class="size-3.5"
								/></Button>
							</div>
						</div>
					</div>
				</section>
			</div>
		</template>

		<!-- reports -->
		<template v-else>
			<div class="mt-5 flex flex-wrap items-end gap-2">
				<div class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="p in presets"
						:key="p.label"
						class="rounded px-2.5 py-1 text-sm"
						:class="
							preset === p.label
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="applyPreset(p)"
					>
						{{ p.label }}
					</button>
				</div>
				<input
					v-model="range.from"
					type="date"
					class="field"
					@change="
						preset = 'Custom';
						runReport();
					"
				/>
				<span class="pb-1 text-ink-gray-5">→</span>
				<input
					v-model="range.to"
					type="date"
					class="field"
					@change="
						preset = 'Custom';
						runReport();
					"
				/>
				<select v-model="groupBy" class="field" @change="runReport">
					<option v-for="g in groupOptions" :key="g.value" :value="g.value">
						Group by {{ g.label }}
					</option>
				</select>
				<select
					v-if="report.data?.people?.length"
					v-model="filterUser"
					class="field"
					@change="runReport"
				>
					<option value="">Everyone</option>
					<option v-for="p in report.data.people" :key="p.user" :value="p.user">
						{{ chat.listName(p.user) }}
					</option>
				</select>
				<a :href="exportUrl" class="ml-auto">
					<Button
						><template #prefix><LucideDownload class="size-4" /></template>Export
						CSV</Button
					>
				</a>
			</div>

			<div v-if="report.loading && !report.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<template v-else-if="report.data">
				<div class="mt-4 text-base text-ink-gray-7">
					Total
					<b class="text-ink-gray-9">{{ formatDuration(report.data.total_minutes) }}</b>
					<span class="ml-1 text-ink-gray-5"
						>({{ (report.data.total_minutes / 60).toFixed(1) }} hours)</span
					>
				</div>
				<div
					v-if="!report.data.groups.length"
					class="mt-4 rounded-lg border px-4 py-10 text-center text-base text-ink-gray-5"
				>
					No time logged in this period.
				</div>
				<div v-else class="mt-3 divide-y rounded-lg border">
					<div v-for="g in report.data.groups" :key="g.key">
						<button
							class="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-gray-1"
							@click="toggle(g.key)"
						>
							<span class="min-w-0 flex-1 truncate text-base text-ink-gray-9">{{
								groupLabel(g)
							}}</span>
							<div
								class="hidden h-2 w-40 overflow-hidden rounded-full bg-surface-gray-2 sm:block"
							>
								<div
									class="h-full rounded-full bg-[#3b82f6]"
									:style="{
										width: `${(g.minutes / report.data.total_minutes) * 100}%`,
									}"
								/>
							</div>
							<span class="w-20 text-right text-base font-medium text-ink-gray-9">{{
								formatDuration(g.minutes)
							}}</span>
							<LucideChevronDown
								class="size-4 text-ink-gray-5 transition-transform"
								:class="{ 'rotate-180': expanded.has(g.key) }"
							/>
						</button>
						<div v-if="expanded.has(g.key)" class="bg-surface-gray-1 px-4 py-2">
							<div
								v-for="e in g.entries"
								:key="e.name"
								class="flex gap-3 py-1 text-sm"
							>
								<span class="w-24 shrink-0 text-ink-gray-5">{{
									dayjs(e.log_date).format("D MMM")
								}}</span>
								<span class="w-32 shrink-0 truncate text-ink-gray-7">{{
									chat.displayName(e.user)
								}}</span>
								<span class="min-w-0 flex-1 truncate text-ink-gray-8">
									{{ e.project_name }}<span v-if="e.task"> · {{ e.task }}</span
									><span v-if="e.description" class="text-ink-gray-5">
										— {{ e.description }}</span
									>
								</span>
								<span class="w-16 text-right text-ink-gray-8">{{
									formatDuration(e.minutes)
								}}</span>
							</div>
						</div>
					</div>
				</div>
			</template>
		</template>

		<LogTimeDialog
			v-model="showLog"
			:entry="editing"
			:defaults="{ log_date: defaultLogDate }"
			@saved="refresh"
		/>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, LoadingIndicator, call, createResource, dayjs } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { formatDuration } from "@/utils/duration";
import LogTimeDialog from "@/components/LogTimeDialog.vue";
import LucidePlus from "~icons/lucide/plus";
import LucideChevronLeft from "~icons/lucide/chevron-left";
import LucideChevronRight from "~icons/lucide/chevron-right";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucidePencil from "~icons/lucide/pencil";
import LucideTrash2 from "~icons/lucide/trash-2";
import LucideDownload from "~icons/lucide/download";

const chat = useChat();
const tab = ref("My week");
const showLog = ref(false);
const editing = ref(null);

// ---- my week --------------------------------------------------------------

// weeks start on Monday
const startOfWeek = (d) => d.subtract((d.day() + 6) % 7, "day").startOf("day");
const weekStart = ref(startOfWeek(dayjs()));
const isCurrentWeek = computed(() => weekStart.value.isSame(startOfWeek(dayjs()), "day"));
const defaultLogDate = computed(() =>
	(isCurrentWeek.value ? dayjs() : weekStart.value.add(4, "day")).format("YYYY-MM-DD")
);

const logs = createResource({ url: "aeraspace.api.timesheet.get_my_logs" });
function loadWeek() {
	logs.submit({
		from_date: weekStart.value.format("YYYY-MM-DD"),
		to_date: weekStart.value.add(6, "day").format("YYYY-MM-DD"),
	});
}
watch(weekStart, loadWeek, { immediate: true });

function shiftWeek(n) {
	weekStart.value = weekStart.value.add(n, "week");
}

const days = computed(() =>
	Array.from({ length: 7 }, (_, i) => {
		const date = weekStart.value.add(i, "day");
		const key = date.format("YYYY-MM-DD");
		const entries = (logs.data || []).filter((e) => e.log_date === key);
		return {
			key,
			date,
			entries,
			minutes: entries.reduce((s, e) => s + e.minutes, 0),
			isToday: date.isSame(dayjs(), "day"),
		};
	})
);
const weekTotal = computed(() => days.value.reduce((s, d) => s + d.minutes, 0));

function openLog(entry = null) {
	editing.value = entry;
	showLog.value = true;
}

async function remove(entry) {
	if (!window.confirm(`Delete ${formatDuration(entry.minutes)} on ${entry.project_name}?`))
		return;
	try {
		await call("aeraspace.api.timesheet.delete_log", { name: entry.name });
		refresh();
	} catch (error) {
		showError(error);
	}
}

function refresh() {
	loadWeek();
	if (tab.value === "Reports") runReport();
}

// ---- reports --------------------------------------------------------------

const presets = [
	{ label: "This week", from: () => startOfWeek(dayjs()), to: () => dayjs() },
	{
		label: "Last week",
		from: () => startOfWeek(dayjs()).subtract(1, "week"),
		to: () => startOfWeek(dayjs()).subtract(1, "day"),
	},
	{ label: "This month", from: () => dayjs().startOf("month"), to: () => dayjs() },
	{
		label: "Last month",
		from: () => dayjs().subtract(1, "month").startOf("month"),
		to: () => dayjs().subtract(1, "month").endOf("month"),
	},
];
const groupOptions = [
	{ value: "project", label: "project" },
	{ value: "employee", label: "employee" },
	{ value: "client", label: "client" },
	{ value: "task", label: "task" },
	{ value: "date", label: "day" },
];
const preset = ref("This week");
const range = reactive({
	from: presets[0].from().format("YYYY-MM-DD"),
	to: dayjs().format("YYYY-MM-DD"),
});
const groupBy = ref("project");
const filterUser = ref("");
const expanded = ref(new Set());
const report = createResource({ url: "aeraspace.api.timesheet.get_report" });

function applyPreset(p) {
	preset.value = p.label;
	range.from = p.from().format("YYYY-MM-DD");
	range.to = p.to().format("YYYY-MM-DD");
	runReport();
}

function runReport() {
	expanded.value = new Set();
	report.submit({
		from_date: range.from,
		to_date: range.to,
		group_by: groupBy.value,
		user: filterUser.value || null,
	});
}

function groupLabel(g) {
	if (groupBy.value === "employee") return chat.listName(g.key);
	if (groupBy.value === "date") return dayjs(g.key).format("dddd, D MMM YYYY");
	return g.label;
}

function toggle(key) {
	const next = new Set(expanded.value);
	next.has(key) ? next.delete(key) : next.add(key);
	expanded.value = next;
}

const exportUrl = computed(() => {
	const params = new URLSearchParams({ from_date: range.from, to_date: range.to });
	if (filterUser.value) params.set("user", filterUser.value);
	return `/api/method/aeraspace.api.timesheet.export_report?${params}`;
});

watch(tab, (t) => t === "Reports" && runReport());
</script>

<style scoped>
.field {
	border-radius: 6px;
	border: 1px solid var(--outline-gray-2);
	background: var(--surface-white);
	padding: 0.25rem 2rem 0.25rem 0.5rem;
	font-size: 0.8125rem;
}
input.field {
	padding-right: 0.5rem;
}
</style>
