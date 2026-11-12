<template>
	<div
		v-if="calls.incoming"
		class="fixed right-4 top-14 z-50 w-80 rounded-xl border bg-surface-modal p-4 shadow-xl"
		role="alertdialog"
		aria-label="Incoming call"
	>
		<div class="flex items-center gap-3">
			<UserAvatar :user="calls.incoming.started_by" size="xl" :show-presence="false" />
			<div class="min-w-0 flex-1">
				<div class="truncate text-base font-semibold text-ink-gray-9">
					{{ calls.incoming.started_by_name }}
				</div>
				<div class="truncate text-sm text-ink-gray-5">
					{{ calls.incoming.quiet ? "started" : "is calling" }} ·
					{{ calls.incoming.call_type === "Video" ? "video" : "audio" }} call
					<template v-if="calls.incoming.channel_type !== 'Direct'">
						in {{ calls.callTitle(calls.incoming) }}
					</template>
				</div>
			</div>
		</div>
		<div class="mt-4 flex gap-2">
			<Button class="flex-1" theme="red" variant="subtle" @click="calls.decline()">
				<template #prefix><LucidePhoneOff class="size-4" /></template>
				{{ calls.incoming.quiet ? "Dismiss" : "Decline" }}
			</Button>
			<Button
				theme="green"
				variant="subtle"
				title="Join with audio only"
				:loading="calls.busy"
				@click="calls.join(calls.incoming, 'Audio')"
			>
				<LucidePhone class="size-4" />
			</Button>
			<Button
				class="flex-1"
				theme="green"
				variant="solid"
				:loading="calls.busy"
				@click="calls.join(calls.incoming, 'Video')"
			>
				<template #prefix><LucideVideo class="size-4" /></template>
				Join
			</Button>
		</div>
	</div>
</template>

<script setup>
import { Button } from "frappe-ui";
import { useCall } from "@/stores/call";
import UserAvatar from "./UserAvatar.vue";
import LucidePhone from "~icons/lucide/phone";
import LucidePhoneOff from "~icons/lucide/phone-off";
import LucideVideo from "~icons/lucide/video";

const calls = useCall();
</script>
