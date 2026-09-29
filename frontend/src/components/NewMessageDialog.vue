<template>
	<Dialog v-model="open" :options="{ title: 'New message', size: 'md' }">
		<template #body-content>
			<PeoplePicker v-model="selected" />
			<TextInput
				v-if="selected.length > 1"
				v-model="groupName"
				class="mt-3"
				placeholder="Group name (optional)"
			/>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!selected.length"
				:loading="saving"
				@click="start"
			>
				{{ selected.length > 1 ? "Create group" : "Open conversation" }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, watch } from "vue";
import { Button, Dialog, TextInput } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import PeoplePicker from "./PeoplePicker.vue";

const open = defineModel({ type: Boolean });
const chat = useChat();
const selected = ref([]);
const groupName = ref("");
const saving = ref(false);

watch(open, (value) => {
	if (value) {
		selected.value = [];
		groupName.value = "";
	}
});

async function start() {
	saving.value = true;
	try {
		await chat.startConversation(selected.value, groupName.value);
		open.value = false;
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
