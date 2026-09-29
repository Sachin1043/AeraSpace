<template>
	<div class="mx-auto max-w-3xl px-6 py-8">
		<div class="flex items-center justify-between gap-4">
			<h1 class="text-xl font-semibold text-ink-gray-9">Channels</h1>
			<Button variant="solid" @click="showCreate = true">
				<template #prefix><LucidePlus class="size-4" /></template>
				Create channel
			</Button>
		</div>
		<TextInput v-model="search" class="mt-4" placeholder="Search channels" @input="reload">
			<template #prefix><LucideSearch class="size-4 text-ink-gray-5" /></template>
		</TextInput>

		<div class="mt-4 divide-y rounded-lg border">
			<div
				v-for="channel in channels.data || []"
				:key="channel.name"
				class="flex items-center gap-3 px-4 py-3"
			>
				<component
					:is="
						channel.channel_type === 'Private'
							? LucideLock
							: channel.channel_type === 'Announcement'
							? LucideMegaphone
							: LucideHash
					"
					class="size-4 text-ink-gray-5"
				/>
				<div class="min-w-0 flex-1">
					<div class="text-base font-medium text-ink-gray-9">
						{{ channel.channel_name }}
					</div>
					<div class="truncate text-sm text-ink-gray-5">
						{{ channel.member_count }}
						{{ channel.member_count === 1 ? "member" : "members" }}
						<span v-if="channel.description"> · {{ channel.description }}</span>
					</div>
				</div>
				<Button v-if="channel.is_member" @click="openChannel(channel.name)">Open</Button>
				<Button
					v-else
					variant="subtle"
					:loading="joining === channel.name"
					@click="join(channel.name)"
					>Join</Button
				>
			</div>
			<div
				v-if="channels.data && !channels.data.length"
				class="px-4 py-10 text-center text-base text-ink-gray-5"
			>
				No channels found. Create the first one!
			</div>
		</div>

		<CreateChannelDialog v-model="showCreate" />
	</div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { Button, TextInput, call, createResource, debounce } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import CreateChannelDialog from "@/components/CreateChannelDialog.vue";
import LucideHash from "~icons/lucide/hash";
import LucideLock from "~icons/lucide/lock";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucidePlus from "~icons/lucide/plus";
import LucideSearch from "~icons/lucide/search";

const chat = useChat();
const router = useRouter();
const search = ref("");
const showCreate = ref(false);
const joining = ref(null);

const channels = createResource({
	url: "aeraspace.api.channel.browse_channels",
	makeParams: () => ({ search: search.value }),
	auto: true,
});
const reload = debounce(() => channels.reload(), 300);

function openChannel(channel) {
	router.push({ name: "Conversation", params: { channel } });
}

async function join(channel) {
	joining.value = channel;
	try {
		await call("aeraspace.api.channel.join_channel", { channel });
		await chat.loadSidebar();
		openChannel(channel);
	} catch (error) {
		showError(error);
	} finally {
		joining.value = null;
	}
}
</script>
