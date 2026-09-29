<template>
	<div class="flex h-full flex-col">
		<header class="flex shrink-0 items-center gap-3 border-b px-5 py-3">
			<router-link to="/projects" class="text-ink-gray-5 hover:text-ink-gray-8"
				><LucideArrowLeft class="size-4"
			/></router-link>
			<div class="min-w-0 flex-1" v-if="project">
				<div class="flex items-center gap-2">
					<span class="truncate text-lg font-semibold text-ink-gray-9">{{
						project.project_name
					}}</span>
					<span class="text-xs text-ink-gray-5">{{ project.name }}</span>
					<select
						v-if="isAdmin"
						:value="project.status"
						class="rounded border-0 bg-surface-gray-2 py-0 pl-2 pr-7 text-xs"
						@change="updateProject({ status: $event.target.value })"
					>
						<option
							v-for="s in ['Active', 'On Hold', 'Completed', 'Archived']"
							:key="s"
						>
							{{ s }}
						</option>
					</select>
					<span v-else class="rounded bg-surface-gray-2 px-1.5 text-xs">{{
						project.status
					}}</span>
				</div>
				<div v-if="project.description" class="truncate text-sm text-ink-gray-5">
					{{ project.description }}
				</div>
			</div>
			<template v-if="project">
				<div class="flex -space-x-1.5">
					<UserAvatar
						v-for="m in project.members.slice(0, 5)"
						:key="m.user"
						:user="m.user"
						size="sm"
						:show-presence="false"
						class="ring-2 ring-[color:var(--surface-white)] rounded-full"
					/>
					<span
						v-if="project.members.length > 5"
						class="flex size-6 items-center justify-center rounded-full bg-surface-gray-3 text-2xs ring-2 ring-[color:var(--surface-white)]"
						>+{{ project.members.length - 5 }}</span
					>
				</div>
				<Button
					@click="
						$router.push({
							name: 'Conversation',
							params: { channel: project.channel },
						})
					"
				>
					<template #prefix><LucideHash class="size-4" /></template>
					Channel
				</Button>
				<Button v-if="project.is_member" variant="solid" @click="openCreate('Todo')">
					<template #prefix><LucidePlus class="size-4" /></template>
					New task
				</Button>
				<Button v-else-if="canJoin" variant="solid" :loading="joining" @click="join"
					>Join project</Button
				>
			</template>
		</header>

		<!-- toolbar -->
		<div v-if="project" class="flex shrink-0 items-center gap-2 border-b px-5 py-2">
			<div class="flex rounded bg-surface-gray-2 p-0.5">
				<button
					v-for="v in ['Board', 'List']"
					:key="v"
					class="rounded px-3 py-1 text-sm"
					:class="view === v ? 'bg-surface-white shadow-sm' : 'text-ink-gray-6'"
					@click="view = v"
				>
					{{ v }}
				</button>
			</div>
			<TextInput v-model="search" size="sm" class="w-56" placeholder="Filter tasks" />
			<select
				v-model="assigneeFilter"
				class="rounded border-outline-gray-2 py-1 pl-2 pr-8 text-sm"
			>
				<option value="">Everyone</option>
				<option value="me">Assigned to me</option>
				<option value="none">Unassigned</option>
				<option v-for="m in project.members" :key="m.user" :value="m.user">
					{{ chat.listName(m.user) }}
				</option>
			</select>
			<span class="ml-auto text-sm text-ink-gray-5"
				>{{ filtered.length }} {{ filtered.length === 1 ? "task" : "tasks" }}</span
			>
		</div>

		<div v-if="!project || !tasksLoaded" class="flex flex-1 items-center justify-center">
			<LoadingIndicator class="size-5" />
		</div>

		<!-- board -->
		<div v-else-if="view === 'Board'" class="flex min-h-0 flex-1 gap-3 overflow-x-auto p-4">
			<div
				v-for="status in STATUSES"
				:key="status"
				class="flex w-72 shrink-0 flex-col rounded-lg bg-surface-gray-1"
				:class="{ 'ring-2 ring-outline-blue-1': dropStatus === status }"
				:data-status="status"
				@dragover.prevent="onDragOver($event, status)"
				@dragleave="onDragLeave($event, status)"
				@drop.prevent="onDrop(status)"
			>
				<div class="flex items-center gap-2 px-3 py-2">
					<span class="size-2 rounded-full" :class="STATUS_COLORS[status]" />
					<span class="text-sm font-medium text-ink-gray-8">{{ status }}</span>
					<span class="text-xs text-ink-gray-5">{{ columns[status].length }}</span>
					<button
						v-if="project.is_member"
						class="ml-auto rounded p-0.5 text-ink-gray-5 hover:bg-surface-gray-3"
						title="Add task"
						@click="openCreate(status)"
					>
						<LucidePlus class="size-4" />
					</button>
				</div>
				<div class="flex-1 space-y-2 overflow-y-auto px-2 pb-2">
					<template v-for="(task, index) in columns[status]" :key="task.name">
						<div
							v-if="dropStatus === status && dropIndex === index"
							class="h-1 rounded bg-blue-400"
						/>
						<TaskCard
							:task="task"
							:dragging="dragged?.name === task.name"
							:draggable="project.is_member"
							:data-task="task.name"
							@dragstart="onDragStart($event, task)"
							@dragend="onDragEnd"
							@open="openTask(task.name)"
						/>
					</template>
					<div
						v-if="dropStatus === status && dropIndex === columns[status].length"
						class="h-1 rounded bg-blue-400"
					/>
					<div
						v-if="!columns[status].length && dropStatus !== status"
						class="rounded border border-dashed py-6 text-center text-xs text-ink-gray-4"
					>
						No tasks
					</div>
				</div>
			</div>
		</div>

		<!-- list -->
		<div v-else class="min-h-0 flex-1 overflow-y-auto px-5 py-3">
			<table class="w-full text-left text-sm">
				<thead class="text-xs uppercase text-ink-gray-5">
					<tr class="border-b">
						<th class="py-2 pr-3 font-medium">ID</th>
						<th class="py-2 pr-3 font-medium">Title</th>
						<th class="py-2 pr-3 font-medium">Status</th>
						<th class="py-2 pr-3 font-medium">Priority</th>
						<th class="py-2 pr-3 font-medium">Assignee</th>
						<th class="py-2 font-medium">Due</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="task in listRows"
						:key="task.name"
						class="cursor-pointer border-b hover:bg-surface-gray-1"
						@click="openTask(task.name)"
					>
						<td class="py-2 pr-3 text-ink-gray-5">{{ task.name }}</td>
						<td
							class="py-2 pr-3 text-base text-ink-gray-9"
							:class="{ 'line-through opacity-60': task.status === 'Done' }"
						>
							{{ task.title }}
						</td>
						<td class="py-2 pr-3">
							<span class="inline-flex items-center gap-1.5"
								><span
									class="size-2 rounded-full"
									:class="STATUS_COLORS[task.status]"
								/>{{ task.status }}</span
							>
						</td>
						<td class="py-2 pr-3">
							<span
								class="rounded px-1.5 py-px text-xs"
								:class="PRIORITY_STYLES[task.priority]"
								>{{ task.priority }}</span
							>
						</td>
						<td class="py-2 pr-3">
							{{ task.assignee ? chat.displayName(task.assignee) : "—" }}
						</td>
						<td
							class="py-2"
							:class="{ 'font-medium text-ink-red-4': dueLabel(task)?.overdue }"
						>
							{{ dueLabel(task)?.text || "—" }}
						</td>
					</tr>
				</tbody>
			</table>
			<div v-if="!listRows.length" class="py-10 text-center text-base text-ink-gray-5">
				No tasks match.
			</div>
		</div>

		<CreateTaskDialog
			v-if="project"
			v-model="showCreate"
			:project="project.name"
			:default-status="createStatus"
			@created="upsert"
		/>
		<TaskDialog
			v-model="showTask"
			:task-name="route.query.task"
			:members="project?.members || []"
			:is-admin="isAdmin"
			@deleted="removeTask"
		/>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button, LoadingIndicator, TextInput, call } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";
import { PRIORITY_STYLES, STATUSES, STATUS_COLORS, dueLabel } from "@/utils/tasks";
import TaskCard from "@/components/TaskCard.vue";
import TaskDialog from "@/components/TaskDialog.vue";
import CreateTaskDialog from "@/components/CreateTaskDialog.vue";
import UserAvatar from "@/components/UserAvatar.vue";
import LucideArrowLeft from "~icons/lucide/arrow-left";
import LucidePlus from "~icons/lucide/plus";
import LucideHash from "~icons/lucide/hash";

const props = defineProps({ project: { type: String, required: true } });
const chat = useChat();
const route = useRoute();
const router = useRouter();

const projectDoc = ref(null);
const project = projectDoc;
const tasks = ref([]);
const tasksLoaded = ref(false);
const view = ref("Board");
const search = ref("");
const assigneeFilter = ref("");
const showCreate = ref(false);
const createStatus = ref("Todo");
const joining = ref(false);

const isAdmin = computed(() => projectDoc.value?.my_role === "Admin");
const canJoin = computed(() => projectDoc.value?.visibility === "Public");

const filtered = computed(() => {
	const term = search.value.trim().toLowerCase();
	return tasks.value.filter((t) => {
		if (term && !`${t.name} ${t.title} ${t.labels.join(" ")}`.toLowerCase().includes(term))
			return false;
		if (assigneeFilter.value === "me") return t.assignee === session.user;
		if (assigneeFilter.value === "none") return !t.assignee;
		if (assigneeFilter.value) return t.assignee === assigneeFilter.value;
		return true;
	});
});

const columns = computed(() => {
	const result = Object.fromEntries(STATUSES.map((s) => [s, []]));
	for (const task of filtered.value) result[task.status]?.push(task);
	for (const s of STATUSES)
		result[s].sort(
			(a, b) => a.sort_order - b.sort_order || a.creation.localeCompare(b.creation)
		);
	return result;
});

const listRows = computed(() =>
	[...filtered.value].sort(
		(a, b) =>
			STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status) || a.sort_order - b.sort_order
	)
);

async function load() {
	tasksLoaded.value = false;
	try {
		const [doc, rows] = await Promise.all([
			call("aeraspace.api.project.get_project", { project: props.project }),
			call("aeraspace.api.task.get_tasks", { project: props.project }),
		]);
		projectDoc.value = doc;
		tasks.value = rows;
		tasksLoaded.value = true;
	} catch (error) {
		showError(error);
		router.replace("/projects");
	}
}

function upsert(task) {
	if (task.project !== props.project) return;
	const index = tasks.value.findIndex((t) => t.name === task.name);
	if (index === -1) tasks.value.push(task);
	else tasks.value[index] = { ...tasks.value[index], ...task };
}

function removeTask(name) {
	tasks.value = tasks.value.filter((t) => t.name !== name);
}

function openCreate(status) {
	createStatus.value = status;
	showCreate.value = true;
}

const showTask = computed({
	get: () => !!route.query.task,
	set: (value) => {
		if (!value) {
			const { task, ...query } = route.query;
			router.replace({ query });
		}
	},
});

function openTask(name) {
	router.replace({ query: { ...route.query, task: name } });
}

async function updateProject(values) {
	try {
		projectDoc.value = await call("aeraspace.api.project.update_project", {
			project: props.project,
			...values,
		});
	} catch (error) {
		showError(error);
	}
}

async function join() {
	joining.value = true;
	try {
		await call("aeraspace.api.channel.join_channel", { channel: projectDoc.value.channel });
		await Promise.all([load(), chat.loadSidebar()]);
	} catch (error) {
		showError(error);
	} finally {
		joining.value = false;
	}
}

// ---- drag & drop ---------------------------------------------------------

const dragged = ref(null);
const dropStatus = ref(null);
const dropIndex = ref(null);

function onDragStart(event, task) {
	if (!projectDoc.value?.is_member) return event.preventDefault();
	dragged.value = task;
	event.dataTransfer.effectAllowed = "move";
	event.dataTransfer.setData("text/plain", task.name);
}

function onDragEnd() {
	dragged.value = dropStatus.value = dropIndex.value = null;
}

function onDragOver(event, status) {
	if (!dragged.value) return;
	dropStatus.value = status;
	const cards = [...event.currentTarget.querySelectorAll("[data-task]")];
	const index = cards.findIndex((card) => {
		const box = card.getBoundingClientRect();
		return event.clientY < box.top + box.height / 2;
	});
	dropIndex.value = index === -1 ? cards.length : index;
}

function onDragLeave(event, status) {
	if (!event.currentTarget.contains(event.relatedTarget) && dropStatus.value === status)
		dropStatus.value = null;
}

async function onDrop(status) {
	const task = dragged.value;
	const index = dropIndex.value ?? columns.value[status].length;
	onDragEnd();
	if (!task) return;

	const column = columns.value[status].filter((t) => t.name !== task.name);
	column.splice(index > column.length ? column.length : index, 0, task);
	const previousStatus = task.status;
	// optimistic: move locally first
	column.forEach((t, i) => upsert({ ...t, status, sort_order: i + 1 }));
	try {
		if (previousStatus !== status)
			upsert(await call("aeraspace.api.task.update_task", { task: task.name, status }));
		await call("aeraspace.api.task.reorder", {
			project: props.project,
			status,
			tasks: column.map((t) => t.name),
		});
		column.forEach((t, i) =>
			upsert({ name: t.name, project: props.project, sort_order: i + 1 })
		);
	} catch (error) {
		showError(error);
		load();
	}
}

// ---- live updates --------------------------------------------------------

const stop = chat.onTaskEvent((type, payload) => {
	if (payload.project !== props.project) return;
	if (type === "update") upsert(payload);
	else if (type === "delete") removeTask(payload.name);
	else if (type === "reorder") {
		payload.tasks.forEach((name, i) => {
			const task = tasks.value.find((t) => t.name === name);
			if (task) task.sort_order = i + 1;
		});
	}
});
onBeforeUnmount(stop);

watch(() => props.project, load, { immediate: true });
</script>
