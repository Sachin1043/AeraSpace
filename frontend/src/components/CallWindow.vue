<template>
	<div
		v-if="calls.active"
		class="fixed z-40 flex flex-col overflow-hidden rounded-xl border bg-surface-modal shadow-2xl"
		:class="calls.expanded ? 'inset-4 sm:inset-8' : 'bottom-4 right-4 w-80'"
	>
		<!-- title bar -->
		<div class="flex h-11 shrink-0 items-center gap-2 border-b px-3">
			<span class="size-2 shrink-0 animate-pulse rounded-full bg-green-500" />
			<div class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-8">
				{{ calls.callTitle(calls.active) }}
			</div>
			<span class="text-xs tabular-nums text-ink-gray-5">{{ duration }}</span>
			<button
				class="rounded p-1 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9"
				:title="calls.expanded ? 'Shrink' : 'Expand'"
				@click="calls.expanded = !calls.expanded"
			>
				<LucideMinimize2 v-if="calls.expanded" class="size-4" />
				<LucideMaximize2 v-else class="size-4" />
			</button>
		</div>

		<!-- people -->
		<div
			class="grid min-h-0 flex-1 gap-2 p-2"
			:class="calls.expanded ? 'auto-rows-fr' : 'h-40 grid-cols-2'"
			:style="
				calls.expanded ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : {}
			"
		>
			<CallTile
				v-for="user in calls.others"
				:key="user"
				:user="user"
				:stream="calls.peers[user].stream"
				:camera="calls.peers[user].camera"
				:muted="calls.peers[user].muted"
				:sharing="calls.peers[user].sharing"
				:connected="calls.peers[user].connected"
				:compact="!calls.expanded"
			/>
			<CallTile
				:user="session.user"
				self
				:stream="calls.localVideo"
				:camera="!!calls.localVideo"
				:muted="calls.muted"
				:sharing="calls.sharing"
				:compact="!calls.expanded"
			/>
		</div>
		<div v-if="!calls.others.length" class="px-3 pb-1 text-center text-xs text-ink-gray-5">
			Waiting for others to join…
		</div>

		<!-- controls -->
		<div class="flex shrink-0 items-center justify-center gap-2 border-t p-2.5">
			<button
				class="control"
				:class="{ off: calls.muted }"
				:title="calls.muted ? 'Unmute' : 'Mute'"
				@click="calls.toggleMute()"
			>
				<LucideMicOff v-if="calls.muted" class="size-5" />
				<LucideMic v-else class="size-5" />
			</button>
			<button
				class="control"
				:class="{ off: !calls.cameraOn }"
				:title="calls.cameraOn ? 'Turn camera off' : 'Turn camera on'"
				@click="calls.toggleCamera()"
			>
				<LucideVideo v-if="calls.cameraOn" class="size-5" />
				<LucideVideoOff v-else class="size-5" />
			</button>
			<button
				v-if="canShare"
				class="control"
				:class="{ on: calls.sharing }"
				:title="calls.sharing ? 'Stop sharing' : 'Share screen'"
				@click="calls.toggleShare()"
			>
				<LucideMonitorUp class="size-5" />
			</button>
			<button class="control leave" title="Leave call" @click="calls.leave()">
				<LucidePhoneOff class="size-5" />
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { dayjs } from "frappe-ui";
import { useCall } from "@/stores/call";
import { session } from "@/session";
import { formatClock } from "@/utils/clock";
import CallTile from "./CallTile.vue";
import LucideMic from "~icons/lucide/mic";
import LucideMicOff from "~icons/lucide/mic-off";
import LucideVideo from "~icons/lucide/video";
import LucideVideoOff from "~icons/lucide/video-off";
import LucideMonitorUp from "~icons/lucide/monitor-up";
import LucidePhoneOff from "~icons/lucide/phone-off";
import LucideMaximize2 from "~icons/lucide/maximize-2";
import LucideMinimize2 from "~icons/lucide/minimize-2";

const calls = useCall();
const canShare = !!navigator.mediaDevices?.getDisplayMedia;

const now = ref(Date.now());
const timer = setInterval(() => (now.value = Date.now()), 1000);
onBeforeUnmount(() => clearInterval(timer));

// server times are naive, in the site timezone
const duration = computed(() => {
	if (!calls.startedAt) return "";
	const started = dayjs.tz(calls.startedAt, window.system_timezone).valueOf();
	return formatClock((now.value - started) / 1000);
});

const columns = computed(() => {
	const count = calls.others.length + 1;
	return count <= 1 ? 1 : count <= 4 ? 2 : 3;
});
</script>

<style scoped>
.control {
	display: flex;
	height: 2.5rem;
	width: 2.5rem;
	align-items: center;
	justify-content: center;
	border-radius: 9999px;
	background-color: var(--surface-gray-2);
	color: var(--ink-gray-8);
}
.control:hover {
	background-color: var(--surface-gray-3);
}
.control.off {
	background-color: var(--surface-gray-4);
	color: var(--ink-gray-9);
}
.control.on {
	background-color: #2563eb;
	color: #fff;
}
.control.leave {
	width: 3.5rem;
	background-color: #dc2626;
	color: #fff;
}
.control.leave:hover {
	background-color: #b91c1c;
}
</style>
