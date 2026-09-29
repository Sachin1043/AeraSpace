<template>
	<Dialog v-model="open" :options="{ title: 'Add people', size: 'md' }">
		<template #body-content>
			<PeoplePicker v-model="selected" :exclude="existing" />
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!selected.length"
				:loading="saving"
				@click="add"
			>
				Add {{ selected.length || "" }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, watch } from "vue";
import { Button, Dialog, call } from "frappe-ui";
import { showError } from "@/stores/chat";
import PeoplePicker from "./PeoplePicker.vue";

const props = defineProps({
	channel: { type: String, required: true },
	existing: { type: Array, default: () => [] },
});
const emit = defineEmits(["added"]);
const open = defineModel({ type: Boolean });
const selected = ref([]);
const saving = ref(false);

watch(open, (value) => value && (selected.value = []));

async function add() {
	saving.value = true;
	try {
		await call("aeraspace.api.channel.add_members", {
			channel: props.channel,
			users: selected.value,
		});
		open.value = false;
		emit("added");
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
