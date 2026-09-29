<template>
	<div class="mx-auto max-w-4xl px-6 py-8">
		<h1 class="text-xl font-semibold text-ink-gray-9">Search</h1>

		<div
			class="mt-4 flex items-center gap-2 rounded-lg border px-3 focus-within:border-outline-gray-4 focus-within:shadow-sm"
		>
			<LucideSearch class="size-4 shrink-0 text-ink-gray-5" />
			<input
				ref="box"
				v-model="query"
				class="w-full border-0 bg-transparent py-2.5 text-base focus:ring-0"
				placeholder="Search messages, files, tasks, people and channels — e.g. shopify from:sachin in:#engineering"
				@input="runSoon"
			/>
			<button
				v-if="query"
				class="text-ink-gray-5 hover:text-ink-gray-8"
				@click="
					query = '';
					run();
				"
			>
				<LucideX class="size-4" />
			</button>
		</div>

		<!-- filter builders -->
		<div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
			<select v-model="from" class="filter-select" @change="applyFilters">
				<option value="">From: anyone</option>
				<option v-for="p in chat.peopleList" :key="p.user" :value="p.user">
					From: {{ p.full_name }}
				</option>
			</select>
			<select v-model="inChannel" class="filter-select" @change="applyFilters">
				<option value="">In: anywhere</option>
				<option v-for="c in chat.channels" :key="c.name" :value="'#' + c.channel_name">
					In: #{{ c.channel_name }}
				</option>
			</select>
			<select v-model="type" class="filter-select" @change="applyFilters">
				<option value="">Any type</option>
				<option value="has:file">Has files</option>
				<option
					v-for="t in ['image', 'pdf', 'doc', 'sheet', 'slides', 'code', 'archive']"
					:key="t"
					:value="'type:' + t"
				>
					Files: {{ t }}
				</option>
			</select>
			<label class="flex items-center gap-1 text-ink-gray-6"
				>After
				<input v-model="after" type="date" class="filter-select" @change="applyFilters"
			/></label>
			<label class="flex items-center gap-1 text-ink-gray-6"
				>Before
				<input v-model="before" type="date" class="filter-select" @change="applyFilters"
			/></label>
		</div>

		<div v-if="!query.trim()" class="mt-10 text-center text-base text-ink-gray-5">
			Type to search. Filters: <code>from:</code> <code>in:#channel</code>
			<code>in:@person</code> <code>before:</code> <code>after:</code> <code>type:pdf</code>
			<code>has:file</code>
		</div>
		<div v-else-if="loading && !results" class="flex justify-center py-10">
			<LoadingIndicator class="size-5" />
		</div>
		<template v-else-if="results">
			<div class="mt-5 flex gap-1 border-b">
				<button
					v-for="tab in tabs"
					:key="tab.key"
					class="-mb-px border-b-2 px-3 py-1.5 text-sm"
					:class="
						scope === tab.key
							? 'border-ink-gray-9 font-medium text-ink-gray-9'
							: 'border-transparent text-ink-gray-6 hover:text-ink-gray-8'
					"
					@click="scope = tab.key"
				>
					{{ tab.label }} <span class="text-ink-gray-5">{{ tab.count }}</span>
				</button>
			</div>

			<div v-if="!totalCount" class="py-10 text-center text-base text-ink-gray-5">
				No results for “{{ query }}”.
			</div>

			<!-- people -->
			<section v-if="show('people') && results.people.length" class="mt-4">
				<h2 v-if="scope === 'all'" class="section-title">People</h2>
				<div class="grid gap-2 sm:grid-cols-2">
					<button
						v-for="p in results.people"
						:key="p.user"
						class="result-card flex items-center gap-3"
						@click="chat.viewProfile(p.user)"
					>
						<UserAvatar :user="p.user" size="lg" />
						<div class="min-w-0">
							<div class="truncate text-base font-medium text-ink-gray-9">
								{{ p.full_name }}
							</div>
							<div class="truncate text-sm text-ink-gray-5">
								{{ [p.designation, p.department].filter(Boolean).join(" · ") }}
							</div>
						</div>
					</button>
				</div>
			</section>

			<!-- channels -->
			<section v-if="show('channels') && results.channels.length" class="mt-4">
				<h2 v-if="scope === 'all'" class="section-title">Channels</h2>
				<div class="grid gap-2 sm:grid-cols-3">
					<router-link
						v-for="c in results.channels"
						:key="c.name"
						:to="{ name: 'Conversation', params: { channel: c.name } }"
						class="result-card text-base font-medium text-ink-gray-9"
					>
						#{{ c.channel_name }}
					</router-link>
				</div>
			</section>

			<!-- tasks -->
			<section v-if="show('tasks') && results.tasks?.length" class="mt-4">
				<h2 v-if="scope === 'all'" class="section-title">Tasks</h2>
				<div class="divide-y rounded-lg border">
					<button
						v-for="t in results.tasks"
						:key="t.name"
						class="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-gray-1"
						@click="chat.openTask(t.name)"
					>
						<span class="w-20 shrink-0 text-xs text-ink-gray-5">{{ t.name }}</span>
						<span
							class="min-w-0 flex-1 truncate text-base text-ink-gray-9"
							:class="{ 'line-through opacity-60': t.status === 'Done' }"
							v-html="highlight(t.title)"
						/>
						<span class="text-xs text-ink-gray-5">{{ t.project_name }}</span>
						<span class="flex items-center gap-1 text-xs text-ink-gray-6"
							><span
								class="size-2 rounded-full"
								:class="STATUS_COLORS[t.status]"
							/>{{ t.status }}</span
						>
					</button>
				</div>
			</section>

			<!-- messages -->
			<section v-if="show('messages') && results.messages.length" class="mt-4">
				<h2 v-if="scope === 'all'" class="section-title">Messages</h2>
				<div class="space-y-2">
					<button
						v-for="m in results.messages"
						:key="m.name"
						class="result-card block w-full text-left"
						@click="openMessage(m)"
					>
						<div class="flex items-baseline gap-2 text-xs text-ink-gray-5">
							<span class="font-medium text-ink-gray-7">{{ where(m) }}</span>
							<span v-if="m.thread_root">· in thread</span>
							<span
								>· {{ dayjsLocal(m.creation).format("MMM D, YYYY h:mm A") }}</span
							>
						</div>
						<div class="mt-1 flex gap-2">
							<UserAvatar :user="m.sender" size="sm" :show-presence="false" />
							<div class="min-w-0">
								<div class="text-sm font-semibold text-ink-gray-9">
									{{ chat.displayName(m.sender) }}
								</div>
								<div
									class="line-clamp-3 text-base text-ink-gray-8"
									v-html="highlight(plainText(m.content, chat.person))"
								/>
							</div>
						</div>
					</button>
				</div>
			</section>

			<!-- files -->
			<section v-if="show('files') && results.files.length" class="mt-4">
				<h2 v-if="scope === 'all'" class="section-title">Files</h2>
				<div class="divide-y rounded-lg border">
					<div
						v-for="f in results.files"
						:key="f.name + f.message"
						class="flex items-center gap-3 px-3 py-2 hover:bg-surface-gray-1"
					>
						<img
							v-if="isImage(f)"
							:src="f.file_url"
							class="size-10 shrink-0 rounded object-cover"
							loading="lazy"
						/>
						<div
							v-else
							class="flex size-10 shrink-0 items-center justify-center rounded bg-surface-gray-3 text-2xs font-semibold uppercase text-ink-gray-7"
						>
							{{ fileExtension(f.file_name) || "file" }}
						</div>
						<button class="min-w-0 flex-1 text-left" @click="openMessage(f)">
							<div
								class="truncate text-base text-ink-gray-9"
								v-html="highlight(f.file_name)"
							/>
							<div class="text-xs text-ink-gray-5">
								{{ chat.displayName(f.sender) }} · {{ where(f) }} ·
								{{ dayjsLocal(f.creation).format("MMM D, YYYY") }} ·
								{{ formatSize(f.file_size) }}
							</div>
						</button>
						<a
							:href="f.file_url"
							target="_blank"
							class="rounded p-1.5 text-ink-gray-5 hover:bg-surface-gray-2"
							><LucideDownload class="size-4"
						/></a>
					</div>
				</div>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { LoadingIndicator, call, dayjsLocal, debounce } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { fileExtension, formatSize, isImage, plainText } from "@/utils/format";
import UserAvatar from "@/components/UserAvatar.vue";
import { STATUS_COLORS } from "@/utils/tasks";
import LucideSearch from "~icons/lucide/search";
import LucideX from "~icons/lucide/x";
import LucideDownload from "~icons/lucide/download";

const chat = useChat();
const route = useRoute();
const router = useRouter();
const box = ref(null);
const query = ref(route.query.q || "");
const results = ref(null);
const loading = ref(false);
const scope = ref("all");
const from = ref("");
const inChannel = ref("");
const type = ref("");
const after = ref("");
const before = ref("");

const FILTER_TOKEN = /(^|\s)(from|in|before|after|type|has):\S+/gi;

function applyFilters() {
	const base = query.value.replace(FILTER_TOKEN, " ").replace(/\s+/g, " ").trim();
	const tokens = [
		from.value && `from:${from.value}`,
		inChannel.value && `in:${inChannel.value}`,
		type.value,
		after.value && `after:${after.value}`,
		before.value && `before:${before.value}`,
	].filter(Boolean);
	query.value = [base, ...tokens].filter(Boolean).join(" ");
	run();
}

async function run() {
	const q = query.value.trim();
	router.replace({ query: q ? { q } : {} });
	if (!q) {
		results.value = null;
		return;
	}
	loading.value = true;
	try {
		const data = await call("aeraspace.api.search.search", { query: q });
		if (q === query.value.trim()) results.value = data; // ignore stale responses
	} catch (error) {
		showError(error);
	} finally {
		loading.value = false;
	}
}
const runSoon = debounce(run, 300);

const tabs = computed(() => {
	const r = results.value || { messages: [], files: [], people: [], channels: [], tasks: [] };
	return [
		{ key: "all", label: "All", count: "" },
		{ key: "messages", label: "Messages", count: r.messages.length },
		{ key: "files", label: "Files", count: r.files.length },
		{ key: "people", label: "People", count: r.people.length },
		{ key: "channels", label: "Channels", count: r.channels.length },
		{ key: "tasks", label: "Tasks", count: r.tasks?.length || 0 },
	];
});
const totalCount = computed(() => tabs.value.slice(1).reduce((sum, t) => sum + t.count, 0));
const show = (section) => scope.value === "all" || scope.value === section;

function escapeHtml(text) {
	return text.replace(
		/[&<>"']/g,
		(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
	);
}

function highlight(text) {
	let html = escapeHtml(text || "");
	for (const term of results.value?.terms || []) {
		const safe = escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
		html = html.replace(
			new RegExp(`(${safe})`, "gi"),
			'<mark class="rounded bg-surface-amber-2 px-0.5">$1</mark>'
		);
	}
	return html;
}

function where(item) {
	if (["Public", "Private", "Announcement"].includes(item.channel_type))
		return `#${item.channel_name}`;
	const entry = chat.sidebarEntry(item.channel);
	return entry ? chat.channelTitle(entry) : "Direct message";
}

function openMessage(item) {
	const query = item.thread_root
		? { thread: item.thread_root }
		: { message: item.message || item.name };
	router.push({ name: "Conversation", params: { channel: item.channel }, query });
}

// keep the filter dropdowns in step with filters typed by hand
function tokenValue(name) {
	const match = query.value.match(new RegExp(`(?:^|\\s)${name}:(\\S+)`, "i"));
	return match ? match[1] : "";
}

watch(
	query,
	() => {
		const fromValue = tokenValue("from").toLowerCase();
		const person =
			fromValue &&
			chat.peopleList.find(
				(p) =>
					p.user.toLowerCase() === fromValue ||
					p.full_name.toLowerCase().includes(fromValue)
			);
		from.value = person ? person.user : "";
		const inValue = tokenValue("in");
		inChannel.value = chat.channels.some((c) => "#" + c.channel_name === inValue)
			? inValue
			: "";
		const typeValue = tokenValue("type");
		type.value = typeValue
			? `type:${typeValue}`
			: tokenValue("has")
			? `has:${tokenValue("has")}`
			: "";
		after.value = tokenValue("after");
		before.value = tokenValue("before");
	},
	{ immediate: true }
);

watch(
	() => route.query.q,
	(q) => {
		if ((q || "") !== query.value.trim()) {
			query.value = q || "";
			run();
		}
	}
);

onMounted(() => {
	box.value?.focus();
	if (query.value) run();
});
</script>

<style scoped>
.filter-select {
	border-radius: 6px;
	border: 1px solid var(--outline-gray-2, #e5e7eb);
	background: transparent;
	padding: 0.2rem 1.8rem 0.2rem 0.5rem;
	font-size: 0.8125rem;
}
.section-title {
	margin-bottom: 0.5rem;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ink-gray-7, #374151);
}
.result-card {
	border-radius: 8px;
	border: 1px solid var(--outline-gray-2, #e5e7eb);
	padding: 0.75rem;
}
.result-card:hover {
	background: var(--surface-gray-1, #f9fafb);
}
</style>
