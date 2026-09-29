<template>
	<Dialog v-model="open" :options="{ title: 'New task', size: 'xl' }">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-if="!project"
					v-model="form.project"
					type="select"
					label="Project"
					:options="[{ label: 'Select a project', value: '' }, ...projectOptions]"
				/>
				<FormControl
					v-model="form.title"
					label="Title"
					placeholder="What needs to be done?"
				/>
				<FormControl
					v-model="form.description"
					type="textarea"
					label="Description"
					:rows="4"
				/>
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
					<FormControl
						v-model="form.status"
						type="select"
						label="Status"
						:options="STATUSES"
					/>
					<FormControl
						v-model="form.priority"
						type="select"
						label="Priority"
						:options="PRIORITIES"
					/>
					<FormControl
						v-model="form.assignee"
						type="select"
						label="Assignee"
						:options="[{ label: 'Unassigned', value: '' }, ...memberOptions]"
					/>
					<FormControl v-model="form.due_date" type="date" label="Due date" />
				</div>
				<FormControl
					v-model="form.labels"
					label="Labels"
					placeholder="bug, shopify, urgent-fix"
				/>
				<div
					v-if="sourceMessage"
					class="rounded border-l-2 border-outline-gray-3 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-6"
				>
					🔗 Linked to a message by {{ chat.displayName(sourceMessage.sender) }}
				</div>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!form.title.trim() || !activeProject"
				:loading="saving"
				@click="create"
			>
				Create task
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, call, createResource, toast } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { PRIORITIES, STATUSES } from "@/utils/tasks";
import { plainText } from "@/utils/format";

const props = defineProps({
	project: { type: String, default: null }, // fixed project (board) or null to choose
	defaultProject: { type: String, default: null },
	defaultStatus: { type: String, default: "Todo" },
	sourceMessage: { type: Object, default: null },
});
const emit = defineEmits(["created"]);
const open = defineModel({ type: Boolean });
const chat = useChat();
const saving = ref(false);
const form = reactive({});

const projects = createResource({ url: "aeraspace.api.project.get_projects" });
const projectOptions = computed(() =>
	(projects.data || [])
		.filter((p) => p.is_member && p.status !== "Archived")
		.map((p) => ({ label: `${p.project_name} (${p.name})`, value: p.name }))
);
const activeProject = computed(() => props.project || form.project);

const members = createResource({ url: "aeraspace.api.project.get_project" });
const memberOptions = computed(() =>
	(members.data?.members || []).map((m) => ({ label: chat.listName(m.user), value: m.user }))
);
watch(activeProject, (project) => project && members.submit({ project }), { immediate: true });

watch(open, (value) => {
	if (!value) return;
	const text = plainText(props.sourceMessage?.content || "", chat.person).trim();
	const firstLine = text.split("\n")[0].slice(0, 120);
	Object.assign(form, {
		project: props.defaultProject || "",
		title: firstLine,
		description: text && text !== firstLine ? text : "",
		status: props.defaultStatus,
		priority: "Medium",
		assignee: "",
		due_date: "",
		labels: "",
	});
	if (!props.project) projects.fetch();
});

async function create() {
	saving.value = true;
	try {
		const task = await call("aeraspace.api.task.create_task", {
			...form,
			project: activeProject.value,
			assignee: form.assignee || null,
			due_date: form.due_date || null,
			source_message: props.sourceMessage?.name || null,
		});
		toast.create({ message: `Created ${task.name}`, type: "success" });
		open.value = false;
		emit("created", task);
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
