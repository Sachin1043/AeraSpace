<template>
	<div class="mx-auto max-w-5xl px-6 py-8">
		<div class="flex items-center justify-between gap-4">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">My tasks</h1>
				<p class="text-base text-ink-gray-6">
					Everything assigned to you across projects.
				</p>
			</div>
			<div class="flex items-center gap-3">
				<label class="flex items-center gap-2 text-sm text-ink-gray-6">
					<input v-model="showDone" type="checkbox" class="rounded" /> Show done
				</label>
				<Button variant="solid" @click="showCreate = true">
					<template #prefix><LucidePlus class="size-4" /></template>
					New task
				</Button>
			</div>
		</div>

		<div v-if="tasks.loading && !tasks.data" class="flex justify-center py-10">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!visible.length"
			class="mt-6 rounded-lg border px-4 py-12 text-center text-base text-ink-gray-5"
		>
			Nothing assigned to you 🎉
		</div>
		<template v-else>
			<section v-for="group in groups" :key="group.label" class="mt-6">
				<h2
					class="mb-2 flex items-center gap-2 text-sm font-semibold"
					:class="group.class"
				>
					{{ group.label }}
					<span class="font-normal text-ink-gray-5">{{ group.tasks.length }}</span>
				</h2>
				<div class="grid gap-2 sm:grid-cols-2">
					<TaskCard
						v-for="task in group.tasks"
						:key="task.name"
						:task="task"
						show-status
						@open="chat.openTask(task.name, task.project)"
					/>
				</div>
			</section>
		</template>

		<CreateTaskDialog v-model="showCreate" @created="tasks.reload()" />
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import { dueLabel } from "@/utils/tasks";
import TaskCard from "@/components/TaskCard.vue";
import CreateTaskDialog from "@/components/CreateTaskDialog.vue";
import LucidePlus from "~icons/lucide/plus";

const chat = useChat();
const showDone = ref(false);
const showCreate = ref(false);
const tasks = createResource({
	url: "aeraspace.api.task.get_tasks",
	params: { assignee: "me" },
	auto: true,
});

const visible = computed(() =>
	(tasks.data || []).filter((t) => showDone.value || t.status !== "Done")
);

const groups = computed(() => {
	const overdue = [],
		soon = [],
		later = [],
		done = [];
	for (const task of visible.value) {
		const due = dueLabel(task);
		if (task.status === "Done") done.push(task);
		else if (due?.overdue) overdue.push(task);
		else if (due?.soon) soon.push(task);
		else later.push(task);
	}
	return [
		{ label: "Overdue", tasks: overdue, class: "text-ink-red-4" },
		{ label: "Due soon", tasks: soon, class: "text-ink-amber-3" },
		{ label: "Upcoming & no date", tasks: later, class: "text-ink-gray-8" },
		{ label: "Done", tasks: done, class: "text-ink-gray-5" },
	].filter((g) => g.tasks.length);
});

// keep the list fresh when tasks change anywhere
const stop = chat.onTaskEvent((type, payload) => {
	const mine =
		tasks.data?.some((t) => t.name === payload.name) || payload.assignee === session.user;
	if (mine) tasks.reload();
});
onBeforeUnmount(stop);
</script>
