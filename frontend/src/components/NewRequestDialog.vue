<template>
	<Dialog v-model="open" :options="{ title: 'New request', size: 'lg' }">
		<template #body-content>
			<div class="space-y-4">
				<div class="grid grid-cols-3 gap-2">
					<button
						v-for="k in kinds"
						:key="k.value"
						class="flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left"
						:class="
							form.kind === k.value
								? 'border-outline-gray-3 bg-surface-gray-2'
								: 'hover:bg-surface-gray-1'
						"
						@click="form.kind = k.value"
					>
						<component :is="k.icon" class="size-4 text-ink-gray-7" />
						<span class="text-sm font-medium text-ink-gray-9">{{ k.label }}</span>
						<span class="text-xs leading-snug text-ink-gray-5">{{ k.hint }}</span>
					</button>
				</div>

				<FormControl
					v-if="form.kind === 'leave'"
					v-model="form.leave_type"
					type="select"
					label="Leave type"
					:options="leaveTypeOptions"
				/>

				<div class="grid grid-cols-2 gap-3">
					<FormControl
						v-model="form.from_date"
						type="date"
						:label="form.kind === 'correction' ? 'Day' : 'From'"
						:max="form.kind === 'correction' ? todayDate : undefined"
					/>
					<FormControl
						v-model="form.to_date"
						type="date"
						label="To"
						:min="form.from_date"
						:max="form.kind === 'correction' ? todayDate : undefined"
					/>
				</div>

				<div class="flex flex-wrap items-center gap-3">
					<FormControl v-model="form.half_day" type="checkbox" label="Half day" />
					<FormControl
						v-if="form.half_day && days > 1"
						v-model="form.half_day_date"
						type="date"
						:min="form.from_date"
						:max="form.to_date"
						class="w-44"
					/>
					<span class="ml-auto text-sm text-ink-gray-6">
						{{ days ? `${dayCount} ${dayCount === 1 ? "day" : "days"}` : "" }}
					</span>
				</div>

				<FormControl
					v-model="form.reason"
					type="textarea"
					:label="reasonLabel"
					:placeholder="reasonPlaceholder"
					:rows="3"
				/>

				<p class="text-sm text-ink-gray-5">
					Goes to <b class="text-ink-gray-8">{{ requests.options.approver_name }}</b> for
					approval.
				</p>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:disabled="!canSubmit"
				:loading="saving"
				@click="submit"
			>
				Send request
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, call, dayjs, toast } from "frappe-ui";
import { showError } from "@/stores/chat";
import { useRequests } from "@/stores/requests";
import LucidePlane from "~icons/lucide/plane";
import LucideHouse from "~icons/lucide/house";
import LucideClockAlert from "~icons/lucide/clock-alert";

const props = defineProps({
	defaults: { type: Object, default: () => ({}) }, // { kind, date }
});
const emit = defineEmits(["saved"]);
const open = defineModel({ type: Boolean, default: false });
const requests = useRequests();
const saving = ref(false);
const todayDate = dayjs().format("YYYY-MM-DD");

const kinds = [
	{ value: "leave", label: "Leave", hint: "Time off", icon: LucidePlane },
	{ value: "wfh", label: "Work from home", hint: "Working remotely", icon: LucideHouse },
	{
		value: "correction",
		label: "Correction",
		hint: "Forgot to check in/out",
		icon: LucideClockAlert,
	},
];

const form = reactive({});
function reset() {
	const date = props.defaults.date || todayDate;
	Object.assign(form, {
		kind: props.defaults.kind || "leave",
		leave_type: requests.options.leave_types[0] || "",
		from_date: date,
		to_date: date,
		half_day: false,
		half_day_date: date,
		reason: "",
	});
}
watch(open, (value) => value && reset(), { immediate: true });

// keep the range valid as dates change
watch(
	() => form.from_date,
	(from) => {
		if (!form.to_date || form.to_date < from) form.to_date = from;
		if (form.half_day_date < from) form.half_day_date = from;
	}
);

const leaveTypeOptions = computed(() =>
	requests.options.leave_types.map((t) => {
		const taken = requests.options.taken_this_year[t];
		return { label: taken ? `${t} · ${taken} taken this year` : t, value: t };
	})
);

const days = computed(() => {
	if (!form.from_date || !form.to_date || form.to_date < form.from_date) return 0;
	return dayjs(form.to_date).diff(dayjs(form.from_date), "day") + 1;
});
const dayCount = computed(() => days.value - (form.half_day ? 0.5 : 0));

const reasonLabel = computed(
	() =>
		({
			leave: "Reason",
			wfh: "Why are you working from home?",
			correction: "What should be corrected?",
		}[form.kind])
);
const reasonPlaceholder = computed(
	() =>
		({
			leave: "e.g. Family function",
			wfh: "e.g. Plumber visiting in the morning",
			correction: "e.g. Worked 9:30 – 6:30, forgot to check out",
		}[form.kind])
);

const canSubmit = computed(
	() =>
		days.value > 0 &&
		form.reason.trim() &&
		(form.kind !== "leave" || form.leave_type) &&
		(form.kind !== "correction" || form.to_date <= todayDate)
);

async function submit() {
	saving.value = true;
	try {
		const row = await call("aeraspace.api.hr_requests.apply", {
			kind: form.kind,
			from_date: form.from_date,
			to_date: form.to_date,
			reason: form.reason,
			leave_type: form.kind === "leave" ? form.leave_type : null,
			half_day: form.half_day ? 1 : 0,
			half_day_date: form.half_day
				? days.value > 1
					? form.half_day_date
					: form.from_date
				: null,
		});
		toast.create({ message: "Request sent", type: "success" });
		open.value = false;
		emit("saved", row);
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
