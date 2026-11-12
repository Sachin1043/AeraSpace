<template>
	<div class="mx-auto max-w-4xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Requests</h1>
				<p class="text-base text-ink-gray-6">
					Leave, work from home and attendance corrections.
				</p>
			</div>
			<div class="flex items-center gap-2">
				<div
					v-if="requests.options.can_approve"
					class="flex rounded-md bg-surface-gray-2 p-0.5"
				>
					<button
						v-for="t in tabs"
						:key="t.value"
						class="flex items-center gap-1.5 rounded px-3 py-1 text-sm"
						:class="
							tab === t.value
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="setTab(t.value)"
					>
						{{ t.label }}
						<span
							v-if="t.value === 'approvals' && requests.options.pending_approvals"
							class="rounded-full bg-surface-red-5 px-1.5 text-xs font-medium text-white"
						>
							{{ requests.options.pending_approvals }}
						</span>
					</button>
				</div>
				<Button variant="solid" :disabled="!requests.options.enabled" @click="openNew()">
					<template #prefix><LucidePlus class="size-4" /></template>
					New request
				</Button>
			</div>
		</div>

		<!-- mine -->
		<template v-if="tab === 'mine'">
			<div
				v-if="Object.keys(requests.options.taken_this_year).length"
				class="mt-5 flex flex-wrap gap-2"
			>
				<span
					v-for="(days, type) in requests.options.taken_this_year"
					:key="type"
					class="rounded-md bg-surface-gray-2 px-2.5 py-1 text-sm text-ink-gray-7"
				>
					{{ type }}: <b class="font-medium text-ink-gray-9">{{ days }}</b> taken this
					year
				</span>
			</div>
			<div v-if="mine.loading && !mine.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<div
				v-else-if="!mine.data?.length"
				class="mt-6 rounded-lg border border-dashed py-12 text-center text-base text-ink-gray-5"
			>
				No requests yet. Use <b>New request</b> to apply for leave, work from home or fix a
				missed check-in.
			</div>
			<div v-else class="mt-5 space-y-2">
				<RequestCard
					v-for="row in mine.data"
					:key="row.name"
					:row="row"
					:busy="busy[row.name]"
					@cancel="cancel"
				/>
			</div>
		</template>

		<!-- approvals -->
		<template v-else>
			<div v-if="approvals.loading && !approvals.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<template v-else>
				<h2 class="mt-6 text-base font-semibold text-ink-gray-9">Waiting for you</h2>
				<div
					v-if="!approvals.data?.pending.length"
					class="mt-2 rounded-lg border border-dashed py-8 text-center text-base text-ink-gray-5"
				>
					Nothing to approve. 🎉
				</div>
				<div v-else class="mt-2 space-y-2">
					<RequestCard
						v-for="row in approvals.data.pending"
						:key="row.name"
						:row="row"
						show-person
						:busy="busy[row.name]"
						@approve="decide(row, 1)"
						@reject="startReject"
					/>
				</div>
				<template v-if="approvals.data?.decided.length">
					<h2 class="mt-8 text-base font-semibold text-ink-gray-9">Decided recently</h2>
					<div class="mt-2 space-y-2">
						<RequestCard
							v-for="row in approvals.data.decided"
							:key="row.name"
							:row="row"
							show-person
						/>
					</div>
				</template>
			</template>
		</template>

		<NewRequestDialog v-model="showNew" :defaults="newDefaults" @saved="refresh" />

		<Dialog v-model="showReject" :options="{ title: 'Reject request', size: 'md' }">
			<template #body-content>
				<p class="mb-3 text-base text-ink-gray-7">
					{{ rejecting?.full_name }} · {{ rejecting?.title }}
				</p>
				<FormControl
					v-model="rejectNote"
					type="textarea"
					label="Reason (shown to them)"
					placeholder="e.g. Release week, can we move it to next Monday?"
					:rows="3"
				/>
			</template>
			<template #actions>
				<Button
					variant="solid"
					theme="red"
					class="w-full"
					:loading="busy[rejecting?.name] === 'reject'"
					@click="confirmReject"
				>
					Reject
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	Button,
	Dialog,
	FormControl,
	LoadingIndicator,
	call,
	createResource,
	toast,
} from "frappe-ui";
import { showError } from "@/stores/chat";
import { useRequests } from "@/stores/requests";
import RequestCard from "@/components/RequestCard.vue";
import NewRequestDialog from "@/components/NewRequestDialog.vue";
import LucidePlus from "~icons/lucide/plus";

const API = "aeraspace.api.hr_requests";
const route = useRoute();
const router = useRouter();
const requests = useRequests();

const tabs = [
	{ value: "mine", label: "My requests" },
	{ value: "approvals", label: "Approvals" },
];
const tab = ref(route.query.tab === "approvals" ? "approvals" : "mine");
const busy = reactive({});
const showNew = ref(false);
const newDefaults = ref({});
const showReject = ref(false);
const rejecting = ref(null);
const rejectNote = ref("");

const mine = createResource({ url: `${API}.get_my_requests` });
const approvals = createResource({ url: `${API}.get_approvals` });

function refresh() {
	mine.reload();
	if (requests.options.can_approve) approvals.reload();
	requests.load();
}

function setTab(value) {
	tab.value = value;
	router.replace({ query: value === "approvals" ? { tab: value } : {} });
}

function openNew(defaults = {}) {
	newDefaults.value = defaults;
	showNew.value = true;
}

async function run(row, action, method, args) {
	busy[row.name] = action;
	try {
		await call(`${API}.${method}`, { kind: row.kind, name: row.name, ...args });
		refresh();
		return true;
	} catch (error) {
		showError(error);
		return false;
	} finally {
		delete busy[row.name];
	}
}

async function decide(row, approve, note = null) {
	const ok = await run(row, approve ? "approve" : "reject", "decide", { approve, note });
	if (ok) toast.create({ message: approve ? "Approved" : "Rejected", type: "success" });
	return ok;
}

function startReject(row) {
	rejecting.value = row;
	rejectNote.value = "";
	showReject.value = true;
}

async function confirmReject() {
	if (await decide(rejecting.value, 0, rejectNote.value)) showReject.value = false;
}

async function cancel(row) {
	if (!window.confirm(`Cancel this ${row.title.toLowerCase()} request?`)) return;
	if (await run(row, "cancel", "cancel"))
		toast.create({ message: "Cancelled", type: "success" });
}

// other tabs / the approver acting elsewhere
watch(() => requests.version, refresh);

onMounted(() => {
	refresh();
	// /requests?new=correction&date=2026-11-10 (from the attendance card)
	if (route.query.new) {
		openNew({ kind: route.query.new, date: route.query.date });
		router.replace({ query: {} });
	}
});
</script>
