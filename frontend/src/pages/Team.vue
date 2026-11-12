<template>
	<div class="mx-auto max-w-6xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Team</h1>
				<p class="text-base text-ink-gray-6">
					{{ dayjs().format("dddd, D MMMM") }}
					<template v-if="data?.holiday"> · {{ data.holiday }}</template>
				</p>
			</div>
			<div class="flex items-center gap-2">
				<FormControl v-model="search" placeholder="Search people" class="w-56">
					<template #prefix><LucideSearch class="size-4 text-ink-gray-5" /></template>
				</FormControl>
				<Button :loading="team.loading" aria-label="Refresh" @click="team.reload()">
					<LucideRefreshCw class="size-4" />
				</Button>
			</div>
		</div>

		<div v-if="!data" class="flex justify-center py-16">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!data.allowed"
			class="mt-6 rounded-lg border border-dashed py-12 text-center text-base text-ink-gray-5"
		>
			Nobody reports to you yet. Set yourself as someone's manager in their profile.
		</div>
		<template v-else>
			<!-- summary -->
			<div class="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
				<button
					v-for="tile in tiles"
					:key="tile.key"
					class="rounded-lg border p-3 text-left transition-colors"
					:class="
						filter === tile.key
							? 'border-outline-gray-3 bg-surface-gray-2'
							: 'hover:bg-surface-gray-1'
					"
					@click="filter = filter === tile.key ? 'all' : tile.key"
				>
					<div class="flex items-center gap-1.5 text-xs text-ink-gray-6">
						<span class="size-2 rounded-full" :class="tile.dot" />
						{{ tile.label }}
					</div>
					<div class="mt-1 text-xl font-semibold tabular-nums text-ink-gray-9">
						{{ tile.value }}
					</div>
				</button>
			</div>

			<!-- people -->
			<div class="mt-5 overflow-x-auto rounded-lg border">
				<table class="w-full min-w-[820px] text-left text-sm">
					<thead
						class="border-b bg-surface-gray-1 text-xs uppercase tracking-wide text-ink-gray-5"
					>
						<tr>
							<th class="px-3 py-2 font-medium">Person</th>
							<th class="px-3 py-2 font-medium">Status</th>
							<th class="px-3 py-2 font-medium">Check-in</th>
							<th class="px-3 py-2 font-medium">Worked</th>
							<th class="px-3 py-2 font-medium">Break</th>
							<th class="px-3 py-2 font-medium">Late</th>
							<th class="px-3 py-2 font-medium">Time logged</th>
							<th class="px-3 py-2 font-medium">EOD</th>
							<th class="px-3 py-2" />
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in visibleRows"
							:key="row.user"
							class="cursor-pointer border-b last:border-b-0 hover:bg-surface-gray-1"
							@click="openHistory(row)"
						>
							<td class="px-3 py-2">
								<div class="flex items-center gap-2.5">
									<UserAvatar :user="row.user" size="lg" />
									<div class="min-w-0">
										<div class="truncate font-medium text-ink-gray-9">
											{{ row.full_name }}
										</div>
										<div class="truncate text-xs text-ink-gray-5">
											{{ row.designation || row.user }}
										</div>
									</div>
								</div>
							</td>
							<td class="px-3 py-2">
								<span
									class="whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium"
									:class="STATUS[row.status].badge"
								>
									{{ statusLabel(row) }}
								</span>
							</td>
							<td class="px-3 py-2 tabular-nums text-ink-gray-8">
								{{ attendance.time(row.today.first_in) || "—" }}
							</td>
							<td class="px-3 py-2 tabular-nums">
								<template v-if="row.today.first_in">
									<span class="font-medium text-ink-gray-9">
										{{ formatHours(totals(row).worked) }}
									</span>
									<div
										class="mt-1 h-1 w-20 overflow-hidden rounded bg-surface-gray-3"
									>
										<div
											class="h-full rounded"
											:class="
												progress(row) >= 100
													? 'bg-green-500'
													: 'bg-blue-500'
											"
											:style="{ width: `${progress(row)}%` }"
										/>
									</div>
								</template>
								<span v-else class="text-ink-gray-5">—</span>
							</td>
							<td class="px-3 py-2 tabular-nums text-ink-gray-8">
								{{ row.today.first_in ? formatHours(totals(row).breaks) : "—" }}
							</td>
							<td
								class="px-3 py-2 tabular-nums"
								:class="
									row.today.late_seconds ? 'text-ink-red-4' : 'text-ink-gray-5'
								"
							>
								{{
									row.today.late_seconds
										? formatHours(row.today.late_seconds)
										: "—"
								}}
							</td>
							<td class="px-3 py-2 tabular-nums text-ink-gray-8">
								{{
									row.logged_minutes ? formatHours(row.logged_minutes * 60) : "—"
								}}
							</td>
							<td class="px-3 py-2">
								<LucideCircleCheck
									v-if="row.eod"
									class="size-4 text-ink-green-3"
								/>
								<span v-else class="text-ink-gray-5">—</span>
							</td>
							<td class="px-3 py-2 text-right">
								<LucideCalendarDays class="ml-auto size-4 text-ink-gray-5" />
							</td>
						</tr>
						<tr v-if="!visibleRows.length">
							<td colspan="9" class="px-3 py-8 text-center text-ink-gray-5">
								No one matches.
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-xs text-ink-gray-5">
				Click a person to see their attendance history. Updates live as people check in and
				out.
			</p>
		</template>

		<AttendanceHistory
			v-if="historyFor"
			v-model="showHistory"
			:user="historyFor.user"
			:full-name="historyFor.full_name"
		/>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Button, FormControl, LoadingIndicator, createResource, dayjs } from "frappe-ui";
import { useSocket } from "@/socket";
import { useAttendance } from "@/stores/attendance";
import { formatHours } from "@/utils/clock";
import { runningTotals } from "@/utils/attendanceStatus";
import { now } from "@/utils/now";
import UserAvatar from "@/components/UserAvatar.vue";
import AttendanceHistory from "@/components/AttendanceHistory.vue";
import LucideSearch from "~icons/lucide/search";
import LucideRefreshCw from "~icons/lucide/refresh-cw";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideCalendarDays from "~icons/lucide/calendar-days";

const STATUS = {
	working: {
		label: "Working",
		badge: "bg-surface-green-2 text-ink-green-3",
		dot: "bg-green-500",
	},
	break: {
		label: "On break",
		badge: "bg-surface-amber-2 text-ink-amber-3",
		dot: "bg-amber-500",
	},
	checked_out: {
		label: "Checked out",
		badge: "bg-surface-gray-2 text-ink-gray-7",
		dot: "bg-gray-500",
	},
	wfh: {
		label: "Work from home",
		badge: "bg-surface-blue-2 text-ink-blue-3",
		dot: "bg-violet-500",
	},
	not_in: {
		label: "Not checked in",
		badge: "bg-surface-red-2 text-ink-red-4",
		dot: "bg-red-500",
	},
	leave: { label: "On leave", badge: "bg-surface-blue-2 text-ink-blue-3", dot: "bg-blue-500" },
	off: { label: "Holiday", badge: "bg-surface-gray-2 text-ink-gray-6", dot: "bg-gray-400" },
};

const attendance = useAttendance();
const team = createResource({ url: "aeraspace.api.team_dashboard.get_today", auto: true });
const data = computed(() => team.data);
const search = ref("");
const filter = ref("all");
const historyFor = ref(null);
const showHistory = ref(false);

const tiles = computed(() => {
	const c = data.value?.counts || {};
	return [
		{ key: "all", label: "Team", value: data.value?.total || 0, dot: "bg-gray-400" },
		{ key: "working", label: "Working", value: c.working, dot: STATUS.working.dot },
		{ key: "break", label: "On break", value: c.break, dot: STATUS.break.dot },
		{
			key: "checked_out",
			label: "Checked out",
			value: c.checked_out,
			dot: STATUS.checked_out.dot,
		},
		{ key: "not_in", label: "Not checked in", value: c.not_in, dot: STATUS.not_in.dot },
		{
			key: "away",
			label: "Leave / WFH",
			value: (c.leave || 0) + (c.wfh || 0),
			dot: STATUS.leave.dot,
		},
		{ key: "late", label: "Late today", value: c.late, dot: "bg-red-400" },
	];
});

const visibleRows = computed(() => {
	const q = search.value.trim().toLowerCase();
	return (data.value?.rows || []).filter((row) => {
		if (
			q &&
			!`${row.full_name} ${row.designation || ""} ${row.user}`.toLowerCase().includes(q)
		)
			return false;
		if (filter.value === "all") return true;
		if (filter.value === "away") return ["leave", "wfh"].includes(row.status);
		if (filter.value === "late") return !!row.today.late_seconds;
		return row.status === filter.value;
	});
});

function totals(row) {
	return runningTotals(row.today, now.value);
}

function progress(row) {
	const expected = row.today.expected_seconds || data.value.expected_seconds;
	return Math.min(100, Math.round((totals(row).worked / expected) * 100));
}

function statusLabel(row) {
	const since = row.today.since ? attendance.time(row.today.since) : "";
	if (row.status === "working") return since ? `Working since ${since}` : "Working";
	if (row.status === "break") return since ? `On break since ${since}` : "On break";
	if (row.status === "checked_out") return `Checked out ${attendance.time(row.today.last_out)}`;
	return STATUS[row.status].label;
}

function openHistory(row) {
	historyFor.value = row;
	showHistory.value = true;
}

// live: someone checked in/out, took a break; plus a slow refresh for anything else
let reloadTimer = null;
function reloadSoon() {
	clearTimeout(reloadTimer);
	reloadTimer = setTimeout(() => team.reload(), 500);
}
const poll = setInterval(() => team.reload(), 120000);
onMounted(() => useSocket()?.on("as_team_attendance", reloadSoon));
onBeforeUnmount(() => {
	clearInterval(poll);
	clearTimeout(reloadTimer);
	useSocket()?.off("as_team_attendance", reloadSoon);
});
</script>
