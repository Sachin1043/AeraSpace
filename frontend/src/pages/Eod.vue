<template>
	<div class="mx-auto max-w-4xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">EOD updates</h1>
				<p class="text-base text-ink-gray-6">
					What you did today, what's next, and what's blocking you.
				</p>
			</div>
			<div class="flex items-center gap-2">
				<div v-if="data?.has_team" class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="t in ['Mine', 'Team']"
						:key="t"
						class="rounded px-3 py-1 text-sm"
						:class="
							tab === t
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="tab = t"
					>
						{{ t === "Mine" ? "My update" : "Team" }}
					</button>
				</div>
				<input
					v-model="date"
					type="date"
					:max="todayStr"
					class="rounded-md border-outline-gray-2 bg-surface-white py-1 text-sm"
				/>
			</div>
		</div>

		<!-- my update -->
		<template v-if="tab === 'Mine'">
			<div v-if="!data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<template v-else>
				<div
					class="mt-5 flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm"
					:class="
						data.update
							? 'bg-surface-green-2 text-ink-green-3'
							: 'bg-surface-amber-1 text-ink-amber-3'
					"
				>
					<LucideCircleCheck v-if="data.update" class="size-4" />
					<LucideClock v-else class="size-4" />
					<span v-if="data.update"
						>Submitted {{ dayjsLocal(data.update.modified).format("h:mm A") }} — you
						can still edit it.</span
					>
					<span v-else>Not submitted yet. Reminder at {{ reminderLabel }}.</span>
				</div>

				<div class="mt-5 grid gap-4 md:grid-cols-2">
					<section v-for="s in sections" :key="s.field" class="rounded-lg border p-3">
						<div class="mb-2 flex items-center justify-between">
							<span class="text-sm font-semibold text-ink-gray-8"
								>{{ s.icon }} {{ s.label }}</span
							>
						</div>
						<textarea
							v-model="form[s.field]"
							rows="5"
							class="w-full resize-y rounded border-outline-gray-2 bg-surface-white text-base focus:border-outline-gray-4 focus:ring-0"
							:placeholder="s.placeholder"
						/>
						<div
							v-if="suggestionsFor(s.field).length"
							class="mt-2 flex flex-wrap gap-1"
						>
							<button
								v-for="item in suggestionsFor(s.field)"
								:key="item.key"
								class="rounded-full border px-2 py-0.5 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
								:title="`Add to ${s.label}`"
								@click="append(s.field, item.text)"
							>
								+ {{ item.label }}
							</button>
						</div>
					</section>
				</div>

				<div class="mt-4 flex flex-wrap items-center justify-between gap-3">
					<div class="text-sm text-ink-gray-6">
						<template v-if="data.time_logs.length">
							⏱ Logged {{ formatDuration(totalLogged) }} today
							<span class="text-ink-gray-5">
								({{
									data.time_logs
										.map(
											(l) =>
												`${l.project_name}${
													l.task_title ? " · " + l.task_title : ""
												} ${formatDuration(l.minutes)}`
										)
										.join(", ")
								}})
							</span>
						</template>
						<router-link
							v-else
							to="/timesheets"
							class="text-ink-blue-3 hover:underline"
							>⏱ No time logged for this day — log time</router-link
						>
					</div>
					<div class="flex items-center gap-3">
						<label class="flex items-center gap-2 text-sm text-ink-gray-6">
							<input v-model="postToChannel" type="checkbox" class="rounded" /> Post
							to EOD channel
						</label>
						<Button
							variant="solid"
							:loading="saving"
							:disabled="!hasContent"
							@click="save"
						>
							{{ data.update ? "Update" : "Submit update" }}
						</Button>
					</div>
				</div>

				<!-- my recent updates -->
				<h2 class="mt-10 text-base font-semibold text-ink-gray-9">My recent updates</h2>
				<div
					v-if="!history.data?.length"
					class="mt-3 rounded-lg border px-4 py-6 text-center text-sm text-ink-gray-5"
				>
					No updates yet.
				</div>
				<div v-else class="mt-3 space-y-2">
					<UpdateCard
						v-for="u in history.data"
						:key="u.name"
						:update="u"
						@click="date = u.update_date"
					/>
				</div>
			</template>
		</template>

		<!-- team -->
		<template v-else>
			<div v-if="!team.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<template v-else>
				<div class="mt-5 grid grid-cols-3 gap-3">
					<div class="rounded-lg border px-4 py-3">
						<div class="text-2xl font-semibold text-ink-green-3">
							{{ team.data.counts.submitted }}
						</div>
						<div class="text-sm text-ink-gray-6">✅ Submitted</div>
					</div>
					<div class="rounded-lg border px-4 py-3">
						<div class="text-2xl font-semibold text-ink-amber-3">
							{{ team.data.counts.pending }}
						</div>
						<div class="text-sm text-ink-gray-6">⏳ Pending</div>
					</div>
					<div class="rounded-lg border px-4 py-3">
						<div class="text-2xl font-semibold text-ink-red-4">
							{{ team.data.counts.missed }}
						</div>
						<div class="text-sm text-ink-gray-6">❌ Missed</div>
					</div>
				</div>
				<p v-if="!team.data.working_day" class="mt-3 text-sm text-ink-gray-5">
					This is not a working day.
				</p>

				<div class="mt-5 divide-y rounded-lg border">
					<div v-for="row in team.data.rows" :key="row.user">
						<button
							class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-gray-1"
							@click="toggle(row.user)"
						>
							<UserAvatar :user="row.user" size="md" />
							<span class="min-w-0 flex-1 truncate text-base text-ink-gray-9">{{
								chat.listName(row.user)
							}}</span>
							<span
								class="rounded px-2 py-0.5 text-xs font-medium"
								:class="stateStyles[row.state]"
								>{{ stateLabels[row.state] }}</span
							>
							<LucideChevronDown
								v-if="row.update"
								class="size-4 text-ink-gray-5 transition-transform"
								:class="{ 'rotate-180': expanded.has(row.user) }"
							/>
						</button>
						<div v-if="row.update && expanded.has(row.user)" class="px-4 pb-4 pl-14">
							<UpdateCard :update="row.update" flat />
						</div>
					</div>
				</div>
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import {
	Button,
	LoadingIndicator,
	call,
	createResource,
	dayjs,
	dayjsLocal,
	toast,
} from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { formatDuration } from "@/utils/duration";
import UserAvatar from "@/components/UserAvatar.vue";
import UpdateCard from "@/components/UpdateCard.vue";
import LucideCircleCheck from "~icons/lucide/circle-check";
import LucideClock from "~icons/lucide/clock";
import LucideChevronDown from "~icons/lucide/chevron-down";

const chat = useChat();
const todayStr = dayjs().format("YYYY-MM-DD");
const date = ref(todayStr);
const tab = ref("Mine");
const data = ref(null);
const saving = ref(false);
const postToChannel = ref(true);
const expanded = ref(new Set());

const sections = [
	{
		field: "completed",
		label: "Completed",
		icon: "✅",
		placeholder: "- Fixed Shopify inventory sync\n- Added test cases",
	},
	{
		field: "in_progress",
		label: "In progress",
		icon: "🔄",
		placeholder: "- Unicommerce invoice issue",
	},
	{
		field: "blockers",
		label: "Blockers",
		icon: "⛔",
		placeholder: "- Waiting for API credentials",
	},
	{
		field: "tomorrow",
		label: "Tomorrow",
		icon: "📅",
		placeholder: "- Complete integration testing",
	},
];
const form = reactive({ completed: "", in_progress: "", blockers: "", tomorrow: "" });
const hasContent = computed(() => sections.some((s) => form[s.field].trim()));
const totalLogged = computed(() =>
	(data.value?.time_logs || []).reduce((sum, l) => sum + l.minutes, 0)
);
const reminderLabel = computed(() =>
	dayjs(`2000-01-01 ${data.value?.reminder_time || "18:30:00"}`).format("h:mm A")
);

const stateLabels = {
	submitted: "✅ Submitted",
	pending: "⏳ Pending",
	missed: "❌ Missed",
	off: "Day off",
};
const stateStyles = {
	submitted: "bg-surface-green-2 text-ink-green-3",
	pending: "bg-surface-amber-1 text-ink-amber-3",
	missed: "bg-surface-red-2 text-ink-red-4",
	off: "bg-surface-gray-2 text-ink-gray-6",
};

const history = createResource({ url: "aeraspace.api.eod.get_history", auto: true });
const team = createResource({ url: "aeraspace.api.eod.get_team_report" });

// suggestions from tasks, not already written in the box
function suggestionsFor(field) {
	const s = data.value?.suggestions;
	if (!s) return [];
	const items =
		field === "completed"
			? s.completed.map((t) => ({
					key: t.name,
					label: t.name,
					text: `${t.name}: ${t.title}`,
			  }))
			: field === "in_progress"
			? s.in_progress.map((t) => ({
					key: t.name,
					label: `${t.name} (${t.status})`,
					text: `${t.name}: ${t.title} (${t.status})`,
			  }))
			: [];
	return items.filter((item) => !form[field].includes(item.key));
}

function append(field, text) {
	const current = form[field].trimEnd();
	form[field] = `${current}${current ? "\n" : ""}- ${text}`;
}

async function load() {
	data.value = null;
	try {
		data.value = await call("aeraspace.api.eod.get_my_update", { date: date.value });
		for (const s of sections) form[s.field] = data.value.update?.[s.field] || "";
	} catch (error) {
		showError(error);
	}
}

async function save() {
	saving.value = true;
	try {
		await call("aeraspace.api.eod.save_update", {
			date: date.value,
			...form,
			post_to_channel: postToChannel.value ? 1 : 0,
		});
		toast.create({ message: "EOD update saved", type: "success" });
		await load();
		history.reload();
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}

function toggle(user) {
	const next = new Set(expanded.value);
	next.has(user) ? next.delete(user) : next.add(user);
	expanded.value = next;
}

watch(date, () => (tab.value === "Mine" ? load() : team.submit({ date: date.value })), {
	immediate: true,
});
watch(tab, (t) => t === "Team" && team.submit({ date: date.value }));
</script>
