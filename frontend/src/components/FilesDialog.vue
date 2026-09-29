<template>
	<Dialog v-model="open" :options="{ title: 'Files', size: 'xl' }">
		<template #body-content>
			<div v-if="files.loading" class="flex justify-center py-6">
				<LoadingIndicator class="size-5" />
			</div>
			<div
				v-else-if="!files.data?.length"
				class="py-8 text-center text-base text-ink-gray-5"
			>
				No files shared here yet. Drag files into the conversation or use the 📎 button.
			</div>
			<div v-else class="max-h-[60vh] divide-y overflow-y-auto rounded-lg border">
				<a
					v-for="file in files.data"
					:key="file.name"
					:href="file.file_url"
					target="_blank"
					class="flex items-center gap-3 px-3 py-2 hover:bg-surface-gray-1"
				>
					<img
						v-if="isImage(file)"
						:src="file.file_url"
						class="size-10 shrink-0 rounded object-cover"
						loading="lazy"
					/>
					<div
						v-else
						class="flex size-10 shrink-0 items-center justify-center rounded bg-surface-gray-3 text-2xs font-semibold uppercase text-ink-gray-7"
					>
						{{ fileExtension(file.file_name) || "file" }}
					</div>
					<div class="min-w-0 flex-1">
						<div class="truncate text-base text-ink-gray-9">{{ file.file_name }}</div>
						<div class="text-xs text-ink-gray-5">
							{{ chat.displayName(file.sender) }} ·
							{{ dayjsLocal(file.creation).format("MMM D, YYYY") }} ·
							{{ formatSize(file.file_size) }}
						</div>
					</div>
					<LucideDownload class="size-4 text-ink-gray-5" />
				</a>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { watch } from "vue";
import { Dialog, LoadingIndicator, createResource, dayjsLocal } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { fileExtension, formatSize, isImage } from "@/utils/format";
import LucideDownload from "~icons/lucide/download";

const props = defineProps({ channel: { type: String, required: true } });
const open = defineModel({ type: Boolean });
const chat = useChat();

const files = createResource({
	url: "aeraspace.api.files.get_channel_files",
	makeParams: () => ({ channel: props.channel }),
});

watch(open, (value) => value && files.reload());
</script>
