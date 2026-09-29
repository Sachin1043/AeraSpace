<template>
	<Dialog v-model="open" :options="{ title: 'Create a channel', size: 'md' }">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="form.channel_name"
					label="Name"
					placeholder="e.g. project-shopify"
				/>
				<FormControl
					v-model="form.channel_type"
					type="select"
					label="Visibility"
					:options="[
						{ label: 'Public — anyone can find and join', value: 'Public' },
						{ label: 'Private — only invited people', value: 'Private' },
						{
							label: 'Announcement — everyone can read, only admins post',
							value: 'Announcement',
						},
					]"
				/>
				<FormControl
					v-model="form.description"
					type="textarea"
					label="Description (optional)"
					placeholder="What is this channel about?"
				/>
				<div>
					<div class="mb-1.5 text-xs text-ink-gray-5">Add people (optional)</div>
					<PeoplePicker v-model="form.members" />
				</div>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!form.channel_name.trim()"
				:loading="saving"
				@click="create"
			>
				Create channel
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, Dialog, FormControl, call } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import PeoplePicker from "./PeoplePicker.vue";

const open = defineModel({ type: Boolean });
const chat = useChat();
const router = useRouter();
const saving = ref(false);
const form = reactive({ channel_name: "", channel_type: "Public", description: "", members: [] });

watch(open, (value) => {
	if (value)
		Object.assign(form, {
			channel_name: "",
			channel_type: "Public",
			description: "",
			members: [],
		});
});

async function create() {
	saving.value = true;
	try {
		const channel = await call("aeraspace.api.channel.create_channel", { ...form });
		await chat.loadSidebar();
		open.value = false;
		router.push({ name: "Conversation", params: { channel } });
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
