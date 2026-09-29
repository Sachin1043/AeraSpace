<template>
	<Dialog v-model="open" :options="{ title: 'Pinned messages', size: 'xl' }">
		<template #body-content>
			<div v-if="pinned.loading" class="flex justify-center py-6">
				<LoadingIndicator class="size-5" />
			</div>
			<div
				v-else-if="!pinned.data?.length"
				class="py-8 text-center text-base text-ink-gray-5"
			>
				Nothing pinned yet. Use “Pin to channel” from a message's menu.
			</div>
			<div v-else class="max-h-[60vh] space-y-2 overflow-y-auto">
				<button
					v-for="message in pinned.data"
					:key="message.name"
					class="block w-full rounded-lg border p-3 text-left hover:bg-surface-gray-1"
					@click="jump(message)"
				>
					<div class="flex items-baseline gap-2">
						<span class="text-sm font-semibold text-ink-gray-9">{{
							chat.displayName(message.sender)
						}}</span>
						<span class="text-xs text-ink-gray-5">{{
							dayjsLocal(message.creation).format("MMM D, h:mm A")
						}}</span>
					</div>
					<div class="mt-0.5 line-clamp-3 text-base text-ink-gray-8">
						{{ plainText(message.content, chat.person) || "📎 File" }}
					</div>
					<div class="mt-1 text-xs text-ink-gray-5">
						Pinned by {{ chat.displayName(message.pinned_by) }}
					</div>
				</button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { watch } from "vue";
import { Dialog, LoadingIndicator, createResource, dayjsLocal } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { plainText } from "@/utils/format";

const props = defineProps({ channel: { type: String, required: true } });
const emit = defineEmits(["jump"]);
const open = defineModel({ type: Boolean });
const chat = useChat();

const pinned = createResource({
	url: "aeraspace.api.chat.get_pinned",
	makeParams: () => ({ channel: props.channel }),
});

watch(open, (value) => value && pinned.reload());

function jump(message) {
	open.value = false;
	emit("jump", message);
}
</script>
