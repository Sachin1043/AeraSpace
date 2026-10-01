<template>
	<Dialog v-model="open" :options="{ size: '4xl' }">
		<template #body>
			<div v-if="!task" class="flex h-64 items-center justify-center">
				<LoadingIndicator class="size-5" />
			</div>
			<div v-else class="flex max-h-[85vh] flex-col">
				<!-- header -->
				<div class="flex items-center gap-2 border-b px-5 py-3 text-sm text-ink-gray-6">
					<span class="font-medium text-ink-gray-8">{{ task.name }}</span>
					<span>·</span>
					<span>{{ task.project_name }}</span>
					<router-link
						v-if="task.source"
						:to="{
							name: 'Conversation',
							params: { channel: task.source.channel },
							query: task.source.thread_root
								? { thread: task.source.thread_root }
								: { message: task.source_message },
						}"
						class="ml-2 text-ink-blue-3 hover:underline"
						@click="open = false"
					>
						🔗 View original message
					</router-link>
					<div class="ml-auto flex items-center gap-1">
						<Button
							v-if="canDelete"
							variant="ghost"
							size="sm"
							title="Delete task"
							@click="remove"
							><LucideTrash2 class="size-4"
						/></Button>
						<Button variant="ghost" size="sm" @click="open = false"
							><LucideX class="size-4"
						/></Button>
					</div>
				</div>

				<div class="grid min-h-0 flex-1 grid-cols-[1fr_15rem] overflow-hidden">
					<!-- main -->
					<div class="overflow-y-auto px-5 py-4">
						<textarea
							v-model="draft.title"
							rows="1"
							:disabled="!task.can_edit"
							class="w-full resize-none border-0 bg-transparent p-0 text-xl font-semibold text-ink-gray-9 focus:ring-0"
							@blur="save('title')"
							@keydown.enter.prevent="$event.target.blur()"
						/>

						<div class="mt-3">
							<div class="mb-1 flex items-center justify-between">
								<span class="text-xs font-medium uppercase text-ink-gray-5"
									>Description</span
								>
								<button
									v-if="task.can_edit && !editingDescription"
									class="text-xs text-ink-blue-3 hover:underline"
									@click="editingDescription = true"
								>
									Edit
								</button>
							</div>
							<textarea
								v-if="editingDescription"
								v-model="draft.description"
								rows="6"
								class="w-full rounded border-outline-gray-2 text-base focus:border-outline-gray-4 focus:ring-0"
								placeholder="Add details, steps to reproduce, acceptance criteria…"
								@blur="
									save('description');
									editingDescription = false;
								"
							/>
							<div
								v-else-if="task.description"
								class="message-content rounded bg-surface-gray-1 px-3 py-2 text-base text-ink-gray-8"
								v-html="
									renderMarkdown(task.description, {
										person: chat.person,
										me: session.user,
									})
								"
							/>
							<div v-else class="text-base italic text-ink-gray-4">
								No description
							</div>
						</div>

						<!-- attachments -->
						<div class="mt-5">
							<div class="mb-1 flex items-center justify-between">
								<span class="text-xs font-medium uppercase text-ink-gray-5"
									>Attachments</span
								>
								<button
									v-if="task.can_edit"
									class="text-xs text-ink-blue-3 hover:underline"
									@click="picker.click()"
								>
									{{ uploading ? `Uploading ${uploadProgress}%…` : "Add file" }}
								</button>
								<input
									ref="picker"
									type="file"
									multiple
									class="hidden"
									@change="upload"
								/>
							</div>
							<div v-if="task.files.length" class="flex flex-wrap gap-2">
								<div
									v-for="file in task.files"
									:key="file.name"
									class="group flex w-56 items-center gap-2 rounded border px-2 py-1.5"
								>
									<img
										v-if="isImage(file)"
										:src="file.file_url"
										class="size-8 rounded object-cover"
									/>
									<span
										v-else
										class="flex size-8 items-center justify-center rounded bg-surface-gray-3 text-2xs font-semibold uppercase"
										>{{ fileExtension(file.file_name) }}</span
									>
									<a
										:href="file.file_url"
										target="_blank"
										class="min-w-0 flex-1 truncate text-sm text-ink-gray-8 hover:underline"
										>{{ file.file_name }}</a
									>
									<button
										v-if="task.can_edit"
										class="hidden text-ink-gray-5 hover:text-ink-red-4 group-hover:block"
										@click="removeFile(file)"
									>
										<LucideX class="size-3.5" />
									</button>
								</div>
							</div>
							<div v-else class="text-sm italic text-ink-gray-4">No attachments</div>
						</div>

						<!-- comments -->
						<div class="mt-6">
							<div class="mb-2 text-xs font-medium uppercase text-ink-gray-5">
								Comments ({{ task.comments.length }})
							</div>
							<div class="space-y-3">
								<div v-for="c in task.comments" :key="c.name" class="flex gap-2">
									<UserAvatar :user="c.owner" size="sm" :show-presence="false" />
									<div class="min-w-0 flex-1">
										<div class="text-sm">
											<span class="font-semibold text-ink-gray-9">{{
												chat.displayName(c.owner)
											}}</span>
											<span class="ml-2 text-xs text-ink-gray-5">{{
												dayjsLocal(c.creation).fromNow()
											}}</span>
										</div>
										<div
											class="message-content text-base text-ink-gray-8"
											v-html="
												renderMarkdown(c.content, {
													person: chat.person,
													me: session.user,
												})
											"
										/>
									</div>
								</div>
							</div>
							<div v-if="task.can_edit" class="mt-3">
								<Composer
									:channel="task.channel"
									:members="memberUsers"
									:autofocus="false"
									:allow-files="false"
									placeholder="Write a comment… (@ to mention)"
									@send="comment"
								/>
							</div>
						</div>
					</div>

					<!-- properties -->
					<div class="space-y-3 overflow-y-auto border-l bg-surface-gray-1 px-4 py-4">
						<FormControl
							:model-value="draft.status"
							type="select"
							label="Status"
							:options="STATUSES"
							:disabled="!task.can_edit"
							@update:model-value="(v) => set('status', v)"
						/>
						<FormControl
							:model-value="draft.priority"
							type="select"
							label="Priority"
							:options="PRIORITIES"
							:disabled="!task.can_edit"
							@update:model-value="(v) => set('priority', v)"
						/>
						<FormControl
							:model-value="draft.assignee"
							type="select"
							label="Assignee"
							:options="[{ label: 'Unassigned', value: '' }, ...memberOptions]"
							:disabled="!task.can_edit"
							@update:model-value="(v) => set('assignee', v)"
						/>
						<FormControl
							:model-value="draft.due_date"
							type="date"
							label="Due date"
							:disabled="!task.can_edit"
							@update:model-value="(v) => set('due_date', v)"
						/>
						<FormControl
							v-model="draft.labels"
							label="Labels"
							placeholder="comma separated"
							:disabled="!task.can_edit"
							@blur="save('labels')"
						/>
						<div class="border-t pt-3">
							<div class="mb-1.5 text-xs text-ink-gray-5">Time logged</div>
							<div class="flex items-center justify-between gap-2">
								<span class="text-base font-medium text-ink-gray-9">{{
									formatDuration(task.logged_minutes)
								}}</span>
								<Button v-if="task.can_edit" size="sm" @click="showLogTime = true">
									<template #prefix><LucideTimer class="size-3.5" /></template>
									Log time
								</Button>
							</div>
						</div>
						<div class="space-y-1 border-t pt-3 text-xs text-ink-gray-5">
							<div>
								Reporter:
								<span class="text-ink-gray-7">{{
									chat.displayName(task.reporter)
								}}</span>
							</div>
							<div>
								Created
								{{ dayjsLocal(task.creation).format("MMM D, YYYY h:mm A") }}
							</div>
							<div v-if="task.completed_on">
								Completed
								{{ dayjsLocal(task.completed_on).format("MMM D, YYYY h:mm A") }}
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
	<LogTimeDialog
		v-if="task"
		v-model="showLogTime"
		:defaults="{ project: task.project, task: task.name }"
		@saved="load"
	/>
</template>

<script setup>
import LogTimeDialog from "./LogTimeDialog.vue";
import { formatDuration } from "@/utils/duration";
import LucideTimer from "~icons/lucide/timer";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, LoadingIndicator, call, dayjsLocal } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";
import { fileExtension, isImage, renderMarkdown } from "@/utils/format";
import { encodeMentions } from "@/utils/mentions";
import { PRIORITIES, STATUSES } from "@/utils/tasks";
import UserAvatar from "./UserAvatar.vue";
import Composer from "./Composer.vue";
import LucideX from "~icons/lucide/x";
import LucideTrash2 from "~icons/lucide/trash-2";

const props = defineProps({
	taskName: { type: String, default: null },
	members: { type: Array, default: () => [] }, // [{ user, role }]
	isAdmin: Boolean,
});
const emit = defineEmits(["deleted"]);
const open = defineModel({ type: Boolean });
const chat = useChat();

const task = ref(null);
const draft = reactive({});
const editingDescription = ref(false);
const showLogTime = ref(false);
const picker = ref(null);
const uploading = ref(false);
const uploadProgress = ref(0);

const memberUsers = computed(() => props.members.map((m) => m.user));
const memberOptions = computed(() =>
	memberUsers.value.map((u) => ({ label: chat.listName(u), value: u }))
);
const canDelete = computed(
	() => task.value && (task.value.reporter === session.user || props.isAdmin)
);

function syncDraft() {
	Object.assign(draft, {
		title: task.value.title,
		description: task.value.description || "",
		status: task.value.status,
		priority: task.value.priority,
		assignee: task.value.assignee || "",
		due_date: task.value.due_date || "",
		labels: task.value.labels.join(", "),
	});
}

async function load() {
	task.value = await call("aeraspace.api.task.get_task", { task: props.taskName });
	syncDraft();
}

watch(
	() => [open.value, props.taskName],
	async ([isOpen, name]) => {
		task.value = null;
		editingDescription.value = false;
		if (isOpen && name) {
			try {
				await load();
			} catch (error) {
				showError(error);
				open.value = false;
			}
		}
	},
	{ immediate: true }
);

// live updates from teammates while the dialog is open
const stop = chat.onTaskEvent((type, payload) => {
	if (!task.value || payload.name !== task.value.name) return;
	if (type === "delete") open.value = false;
	else if (type === "update") load();
});
onBeforeUnmount(stop);

// dropdowns and date pickers save as soon as a value is picked
function set(field, value) {
	draft[field] = value ?? "";
	save(field);
}

async function save(field) {
	if (!task.value?.can_edit) return;
	const current = field === "labels" ? task.value.labels.join(", ") : task.value[field] || "";
	let value = draft[field];
	if (field === "description") value = encodeMentions(value, chat.peopleList);
	if ((value || "") === current) return;
	if (field === "title" && !value.trim()) {
		draft.title = task.value.title;
		return;
	}
	try {
		const updated = await call("aeraspace.api.task.update_task", {
			task: task.value.name,
			[field]: value || null,
		});
		Object.assign(task.value, updated);
		syncDraft();
	} catch (error) {
		showError(error);
		syncDraft();
	}
}

async function upload(event) {
	const files = [...event.target.files];
	event.target.value = "";
	uploading.value = true;
	try {
		const uploaded = [];
		for (const file of files)
			uploaded.push(
				await chat.uploadFile(task.value.channel, file, (p) => (uploadProgress.value = p))
			);
		const updated = await call("aeraspace.api.task.update_task", {
			task: task.value.name,
			files: [...task.value.files.map((f) => f.name), ...uploaded.map((f) => f.name)],
		});
		Object.assign(task.value, updated);
	} catch (error) {
		showError(error);
	} finally {
		uploading.value = false;
	}
}

async function removeFile(file) {
	const updated = await call("aeraspace.api.task.update_task", {
		task: task.value.name,
		files: task.value.files.filter((f) => f.name !== file.name).map((f) => f.name),
	});
	Object.assign(task.value, updated);
}

async function comment({ content }) {
	if (!content.trim()) return;
	try {
		const saved = await call("aeraspace.api.task.add_comment", {
			task: task.value.name,
			content: encodeMentions(content.trim(), chat.peopleList),
		});
		task.value.comments.push(saved);
	} catch (error) {
		showError(error);
	}
}

async function remove() {
	if (!window.confirm(`Delete ${task.value.name}? This cannot be undone.`)) return;
	try {
		await call("aeraspace.api.task.delete_task", { task: task.value.name });
		open.value = false;
		emit("deleted", task.value.name);
	} catch (error) {
		showError(error);
	}
}
</script>

<style scoped>
.message-content :deep(p) {
	margin: 0;
}
.message-content :deep(p + p) {
	margin-top: 0.4rem;
}
.message-content :deep(a) {
	color: var(--ink-blue-3);
	text-decoration: underline;
}
.message-content :deep(code) {
	border-radius: 4px;
	background: var(--surface-gray-3);
	padding: 0.1rem 0.3rem;
	font-size: 0.85em;
}
.message-content :deep(ul) {
	list-style: disc;
	padding-left: 1.25rem;
}
.message-content :deep(.mention) {
	border-radius: 4px;
	background: var(--surface-blue-2);
	padding: 0 0.2rem;
	color: var(--ink-blue-3);
}
</style>
