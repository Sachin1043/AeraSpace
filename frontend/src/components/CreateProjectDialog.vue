<template>
	<Dialog v-model="open" :options="{ title: 'New project', size: 'lg' }">
		<template #body-content>
			<div class="space-y-4">
				<div class="grid grid-cols-[1fr_8rem] gap-3">
					<FormControl
						v-model="form.project_name"
						label="Project name"
						placeholder="e.g. Shopify Integration"
						@input="suggestKey"
					/>
					<FormControl
						v-model="form.project_key"
						label="Key"
						placeholder="SHOP"
						@input="keyTouched = true"
					/>
				</div>
				<p class="-mt-2 text-xs text-ink-gray-5">
					Tasks will be numbered {{ (form.project_key || "KEY").toUpperCase() }}-1,
					{{ (form.project_key || "KEY").toUpperCase() }}-2 …
				</p>
				<FormControl
					v-model="form.description"
					type="textarea"
					label="Description (optional)"
				/>
				<FormControl
					v-model="form.client"
					label="Client (optional)"
					placeholder="e.g. GK Exports"
				/>
				<FormControl
					v-model="form.visibility"
					type="select"
					label="Visibility"
					:options="[
						{ label: 'Private — only project members', value: 'Private' },
						{ label: 'Public — everyone can view; members edit', value: 'Public' },
					]"
				/>
				<div>
					<div class="mb-1.5 text-xs text-ink-gray-5">Members</div>
					<PeoplePicker v-model="form.members" />
				</div>
				<p class="text-xs text-ink-gray-5">
					A #project channel is created automatically with the same members.
				</p>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!form.project_name.trim()"
				:loading="saving"
				@click="create"
			>
				Create project
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, Dialog, FormControl, call, debounce } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import PeoplePicker from "./PeoplePicker.vue";

const open = defineModel({ type: Boolean });
const emit = defineEmits(["created"]);
const chat = useChat();
const router = useRouter();
const saving = ref(false);
const keyTouched = ref(false);
const blank = () => ({
	project_name: "",
	project_key: "",
	description: "",
	visibility: "Private",
	client: "",
	members: [],
});
const form = reactive(blank());

watch(open, (value) => {
	if (value) {
		Object.assign(form, blank());
		keyTouched.value = false;
	}
});

const suggestKey = debounce(async () => {
	if (keyTouched.value || !form.project_name.trim()) return;
	form.project_key = await call("aeraspace.api.project.suggest_project_key", {
		project_name: form.project_name,
	});
}, 300);

async function create() {
	saving.value = true;
	try {
		const project = await call("aeraspace.api.project.create_project", {
			...form,
			project_key: form.project_key.toUpperCase(),
		});
		await chat.loadSidebar();
		open.value = false;
		emit("created", project);
		router.push({ name: "Project", params: { project } });
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
