<template>
	<Dialog
		v-model="open"
		:options="{ title: meeting ? 'Edit meeting' : 'Schedule a meeting', size: 'lg' }"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="form.title"
					label="Title"
					placeholder="e.g. Sprint planning"
				/>

				<div class="grid grid-cols-3 gap-3">
					<FormControl v-model="form.date" type="date" label="Date" :min="todayDate" />
					<FormControl v-model="form.time" type="time" label="Time" />
					<FormControl
						v-model="form.duration"
						type="select"
						label="Duration"
						:options="durations"
					/>
				</div>

				<div>
					<div class="mb-1.5 text-xs text-ink-gray-5">Type</div>
					<div class="inline-flex rounded-md bg-surface-gray-2 p-0.5">
						<button
							v-for="t in ['Video', 'Audio']"
							:key="t"
							class="flex items-center gap-1.5 rounded px-3 py-1 text-sm"
							:class="
								form.call_type === t
									? 'bg-surface-white text-ink-gray-9 shadow-sm'
									: 'text-ink-gray-6'
							"
							@click="form.call_type = t"
						>
							<LucideVideo v-if="t === 'Video'" class="size-3.5" />
							<LucidePhone v-else class="size-3.5" />
							{{ t }}
						</button>
					</div>
				</div>

				<template v-if="!meeting">
					<div>
						<div class="mb-1.5 flex items-center gap-3 text-xs text-ink-gray-5">
							Invite
							<div class="inline-flex rounded-md bg-surface-gray-2 p-0.5">
								<button
									v-for="w in where"
									:key="w.value"
									class="rounded px-2.5 py-0.5 text-xs"
									:class="
										form.where === w.value
											? 'bg-surface-white text-ink-gray-9 shadow-sm'
											: 'text-ink-gray-6'
									"
									@click="form.where = w.value"
								>
									{{ w.label }}
								</button>
							</div>
						</div>
						<PeoplePicker v-if="form.where === 'people'" v-model="form.users" />
						<template v-else>
							<FormControl
								v-model="form.channel"
								type="select"
								:options="channelOptions"
							/>
							<p class="mt-1 text-xs text-ink-gray-5">
								Everyone in the channel is invited and the meeting happens there.
							</p>
						</template>
					</div>
				</template>

				<FormControl
					v-model="form.agenda"
					type="textarea"
					label="Agenda (optional)"
					placeholder="What will you cover?"
					:rows="3"
				/>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!canSave"
				:loading="saving"
				@click="save"
			>
				{{ meeting ? "Save changes" : "Schedule" }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, call, dayjs, toast } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { fromSite, toSite } from "@/utils/siteTime";
import PeoplePicker from "./PeoplePicker.vue";
import LucideVideo from "~icons/lucide/video";
import LucidePhone from "~icons/lucide/phone";

const props = defineProps({
	meeting: { type: Object, default: null }, // edit this one
	defaults: { type: Object, default: () => ({}) }, // { users, channel }
});
const emit = defineEmits(["saved"]);
const open = defineModel({ type: Boolean, default: false });
const chat = useChat();
const saving = ref(false);
const todayDate = dayjs().format("YYYY-MM-DD");

const durations = [15, 30, 45, 60, 90, 120].map((m) => ({
	label: m < 60 ? `${m} min` : `${m / 60} h`.replace(".5 h", "½ h"),
	value: m,
}));
const where = [
	{ value: "people", label: "People" },
	{ value: "channel", label: "A channel" },
];
const channelOptions = computed(() => [
	{ label: "Pick a channel", value: "" },
	...chat.channels.map((c) => ({ label: `#${c.channel_name}`, value: c.name })),
]);

const form = reactive({});
function reset() {
	const m = props.meeting;
	// next half hour, at least 15 minutes away
	const next = dayjs().add(15, "minute");
	const start = m ? fromSite(m.starts_at) : next.minute(next.minute() < 30 ? 30 : 60).second(0);
	Object.assign(form, {
		title: m?.title || "",
		date: start.format("YYYY-MM-DD"),
		time: start.format("HH:mm"),
		duration: m?.duration || 30,
		call_type: m?.call_type || "Video",
		agenda: m?.agenda || "",
		where: props.defaults.channel ? "channel" : "people",
		users: [...(props.defaults.users || [])],
		channel: props.defaults.channel || "",
	});
}
watch(open, (value) => value && reset(), { immediate: true });

const canSave = computed(
	() =>
		form.title?.trim() &&
		form.date &&
		form.time &&
		(props.meeting || (form.where === "people" ? form.users.length : form.channel))
);

async function save() {
	saving.value = true;
	const values = {
		title: form.title,
		starts_at: toSite(form.date, form.time),
		duration: Number(form.duration),
		call_type: form.call_type,
		agenda: form.agenda,
	};
	try {
		const saved = props.meeting
			? await call("aeraspace.api.meeting.update", { name: props.meeting.name, ...values })
			: await call("aeraspace.api.meeting.schedule", {
					...values,
					users: form.where === "people" ? form.users : null,
					channel: form.where === "channel" ? form.channel : null,
			  });
		toast.create({
			message: props.meeting ? "Meeting updated" : "Meeting scheduled",
			type: "success",
		});
		open.value = false;
		emit("saved", saved);
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
