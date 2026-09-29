<template>
	<div class="mx-auto max-w-6xl px-6 py-8">
		<div class="flex items-center justify-between gap-4">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Projects</h1>
				<p class="text-base text-ink-gray-6">
					Every project has its own board and #channel.
				</p>
			</div>
			<Button variant="solid" @click="showCreate = true">
				<template #prefix><LucidePlus class="size-4" /></template>
				New project
			</Button>
		</div>

		<div v-if="projects.loading && !projects.data" class="flex justify-center py-10">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!projects.data?.length"
			class="mt-8 rounded-lg border px-4 py-16 text-center"
		>
			<div class="text-lg font-medium text-ink-gray-8">No projects yet</div>
			<div class="mt-1 text-base text-ink-gray-5">
				Create one to get a task board and a project channel.
			</div>
			<Button class="mt-4" variant="solid" @click="showCreate = true">New project</Button>
		</div>
		<div v-else class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			<router-link
				v-for="p in projects.data"
				:key="p.name"
				:to="{ name: 'Project', params: { project: p.name } }"
				class="flex flex-col rounded-lg border p-4 hover:border-outline-gray-3 hover:shadow-sm"
				:class="{ 'opacity-60': ['Completed', 'Archived'].includes(p.status) }"
			>
				<div class="flex items-start justify-between gap-2">
					<div class="min-w-0">
						<div class="truncate text-base font-semibold text-ink-gray-9">
							{{ p.project_name }}
						</div>
						<div class="text-xs text-ink-gray-5">
							{{ p.name }} · {{ p.visibility }}
						</div>
					</div>
					<span
						class="shrink-0 rounded px-1.5 py-0.5 text-2xs font-medium"
						:class="statusStyles[p.status]"
						>{{ p.status }}</span
					>
				</div>
				<div class="mt-2 line-clamp-2 min-h-[2.5rem] text-sm text-ink-gray-6">
					{{ p.description || "—" }}
				</div>
				<div class="mt-3">
					<div class="flex justify-between text-xs text-ink-gray-5">
						<span>{{ p.done_tasks }} / {{ p.total_tasks }} tasks done</span>
						<span
							>{{
								p.total_tasks
									? Math.round((p.done_tasks / p.total_tasks) * 100)
									: 0
							}}%</span
						>
					</div>
					<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-gray-2">
						<div
							class="h-full rounded-full bg-green-500"
							:style="{
								width: `${
									p.total_tasks ? (p.done_tasks / p.total_tasks) * 100 : 0
								}%`,
							}"
						/>
					</div>
				</div>
				<div class="mt-3 flex items-center justify-between text-xs text-ink-gray-5">
					<span
						>{{ p.member_count }}
						{{ p.member_count === 1 ? "member" : "members" }}</span
					>
					<span v-if="!p.is_member" class="text-ink-gray-4">Viewing</span>
					<UserAvatar
						v-else-if="p.lead"
						:user="p.lead"
						size="xs"
						:show-presence="false"
					/>
				</div>
			</router-link>
		</div>

		<CreateProjectDialog v-model="showCreate" />
	</div>
</template>

<script setup>
import { ref } from "vue";
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import CreateProjectDialog from "@/components/CreateProjectDialog.vue";
import UserAvatar from "@/components/UserAvatar.vue";
import LucidePlus from "~icons/lucide/plus";

const showCreate = ref(false);
const projects = createResource({ url: "aeraspace.api.project.get_projects", auto: true });
const statusStyles = {
	Active: "bg-surface-green-2 text-ink-green-3",
	"On Hold": "bg-surface-amber-1 text-ink-amber-3",
	Completed: "bg-surface-blue-1 text-ink-blue-3",
	Archived: "bg-surface-gray-2 text-ink-gray-6",
};
</script>
