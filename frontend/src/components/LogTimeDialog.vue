<template>
	<Dialog
		v-model="open"
		:options="{ title: entry ? 'Edit time entry' : 'Log time', size: 'md' }"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					:model-value="form.project"
					type="select"
					label="Project"
					:options="[{ label: 'Select a project', value: '' }, ...projectOptions]"
					@update:model-value="
						(v) => {
							form.project = v;
							form.task = '';
						}
					"
				/>
				<FormControl
					:model-value="form.task"
					type="select"
					label="Task (optional)"
					:options="[{ label: 'No specific task', value: '' }, ...taskOptions]"
					@update:model-value="(v) => (form.task = v)"
				/>
				<div class="grid grid-cols-2 gap-3">
					<div>
						<FormControl
							v-model="form.duration"
							label="Duration"
							placeholder="e.g. 3h 20m, 1.5, 2:30"
						/>
						<div
							class="mt-1 text-xs"
							:class="minutes ? 'text-ink-gray-5' : 'text-ink-red-4'"
						>
							{{
								form.duration
									? minutes
										? `= ${formatDuration(minutes)}`
										: "Try 3h 20m, 90m or 1.5"
									: ""
							}}
						</div>
					</div>
					<FormControl v-model="form.log_date" type="date" label="Date" />
				</div>
				<FormControl
					v-model="form.description"
					type="textarea"
					label="What did you work on?"
					:rows="3"
				/>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!form.project || !minutes"
				:loading="saving"
				@click="save"
			>
				{{ entry ? "Save" : "Log time" }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, call, createResource, dayjs, toast } from "frappe-ui";
import { showError } from "@/stores/chat";
import { formatDuration, parseDuration } from "@/utils/duration";

const props = defineProps({
	entry: { type: Object, default: null }, // edit an existing entry
	defaults: { type: Object, default: () => ({}) }, // { project, task, log_date }
});
const emit = defineEmits(["saved"]);
const open = defineModel({ type: Boolean });
const saving = ref(false);
const form = reactive({});

const projects = createResource({ url: "aeraspace.api.project.get_projects" });
const projectOptions = computed(() =>
	(projects.data || [])
		.filter((p) => p.is_member && p.status !== "Archived")
		.map((p) => ({ label: `${p.project_name} (${p.name})`, value: p.name }))
);
const tasks = createResource({ url: "aeraspace.api.task.get_tasks" });
const taskOptions = computed(() =>
	(tasks.data || []).map((t) => ({ label: `${t.name} · ${t.title}`, value: t.name }))
);
watch(
	() => form.project,
	(project) => project && tasks.submit({ project, include_done: 1 })
);

const minutes = computed(() => parseDuration(form.duration));

watch(open, (value) => {
	if (!value) return;
	projects.fetch();
	const source = props.entry || props.defaults;
	Object.assign(form, {
		project: source.project || "",
		task: source.task || "",
		duration: props.entry ? formatDuration(props.entry.minutes) : "",
		log_date: source.log_date || dayjs().format("YYYY-MM-DD"),
		description: props.entry?.description || "",
	});
});

async function save() {
	saving.value = true;
	const values = {
		project: form.project,
		task: form.task || null,
		minutes: minutes.value,
		log_date: form.log_date,
		description: form.description,
	};
	try {
		const saved = props.entry
			? await call("aeraspace.api.timesheet.update_log", {
					name: props.entry.name,
					...values,
			  })
			: await call("aeraspace.api.timesheet.log_time", values);
		toast.create({ message: `Logged ${formatDuration(saved.minutes)}`, type: "success" });
		open.value = false;
		emit("saved", saved);
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
