<template>
	<Teleport to="body">
		<Transition name="fade">
			<div v-if="user" class="fixed inset-0 z-40 bg-black/30" @click="close" />
		</Transition>
		<Transition name="slide">
			<aside
				v-if="user && info"
				class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[34rem] flex-col border-l bg-surface-white shadow-2xl"
				@keydown.esc="close"
			>
				<!-- title bar -->
				<div class="flex h-12 shrink-0 items-center justify-between border-b px-5">
					<span class="text-base font-semibold text-ink-gray-9">{{
						isMe ? "My profile" : info.full_name
					}}</span>
					<button
						class="rounded p-1 text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
						@click="close"
					>
						<LucideX class="size-5" />
					</button>
				</div>

				<div class="flex-1 overflow-y-auto">
					<!-- identity -->
					<div class="flex items-start gap-5 bg-surface-gray-1 px-5 py-5">
						<div class="group relative size-28 shrink-0">
							<img
								v-if="info.user_image"
								:src="info.user_image"
								class="size-28 rounded-lg object-cover"
								:alt="info.full_name"
							/>
							<div
								v-else
								class="flex size-28 items-center justify-center rounded-lg bg-surface-gray-3 text-4xl font-semibold text-ink-gray-6"
							>
								{{ initials }}
							</div>
							<PresenceDot
								:status="chat.statusOf(user)"
								size="xl"
								:border="3"
								border-color="surface-gray-1"
								class="absolute -bottom-1 -right-1"
							/>
							<button
								v-if="isMe"
								class="absolute inset-0 hidden items-center justify-center rounded-lg bg-black/50 text-sm font-medium text-white group-hover:flex"
								@click="photoInput.click()"
							>
								{{ uploading ? "Uploading…" : "Change photo" }}
							</button>
							<input
								ref="photoInput"
								type="file"
								accept="image/png,image/jpeg,image/webp,image/gif"
								class="hidden"
								@change="uploadPhoto"
							/>
						</div>

						<div class="min-w-0 flex-1">
							<div class="truncate text-xl font-semibold text-ink-gray-9">
								{{ info.full_name }}
							</div>
							<button
								v-if="info.email"
								class="mt-0.5 flex max-w-full items-center gap-1.5 text-sm text-ink-gray-6 hover:text-ink-gray-8"
								title="Copy email"
								@click="copy(info.email)"
							>
								<span class="truncate">{{ info.email }}</span>
								<LucideCopy class="size-3.5 shrink-0" />
							</button>
							<div class="mt-2 flex items-center gap-1.5 text-sm text-ink-gray-7">
								<PresenceDot :status="chat.statusOf(user)" size="sm" />
								{{ chat.statusLabel(user) }}
							</div>

							<div class="mt-3 flex flex-wrap gap-2">
								<Button v-if="!isMe" variant="solid" @click="message">
									<template #prefix
										><LucideMessageCircle class="size-4"
									/></template>
									Message
								</Button>
								<template v-if="isMe">
									<Button v-if="!editing" @click="startEdit">
										<template #prefix
											><LucidePencil class="size-4"
										/></template>
										Edit profile
									</Button>
									<Button :loading="uploading" @click="photoInput.click()">
										<template #prefix
											><LucideCamera class="size-4"
										/></template>
										{{ info.user_image ? "Change photo" : "Upload photo" }}
									</Button>
									<Button
										v-if="info.user_image"
										variant="ghost"
										@click="removePhoto"
										>Remove photo</Button
									>
								</template>
							</div>
						</div>
					</div>

					<!-- details -->
					<div v-if="!editing" class="px-5 pb-6">
						<section v-for="section in sections" :key="section.title" class="mt-5">
							<h3 class="mb-2 text-sm font-semibold text-ink-gray-8">
								{{ section.title }}
							</h3>
							<dl class="divide-y rounded-lg border">
								<div
									v-for="row in section.rows"
									:key="row.label"
									class="grid grid-cols-[9rem_1fr] gap-3 px-3 py-2.5 text-base"
								>
									<dt class="text-ink-gray-5">{{ row.label }}</dt>
									<dd class="min-w-0 break-words text-ink-gray-8">
										<button
											v-if="row.user"
											class="text-ink-blue-3 hover:underline"
											@click="chat.viewProfile(row.user)"
										>
											{{ row.value }}
										</button>
										<template v-else>{{ row.value || "—" }}</template>
									</dd>
								</div>
							</dl>
						</section>
					</div>

					<!-- edit my profile -->
					<div v-else class="space-y-4 px-5 py-5">
						<div class="grid grid-cols-2 gap-3">
							<FormControl v-model="form.designation" label="Designation" />
							<FormControl v-model="form.department" label="Department" />
							<FormControl v-model="form.team" label="Team" />
							<FormControl v-model="form.phone" label="Phone" />
						</div>
						<FormControl
							v-model="form.skills"
							type="textarea"
							label="Skills"
							placeholder="Frappe, Vue, Shopify"
						/>

						<div class="rounded-lg border p-3">
							<div class="mb-2 text-sm font-medium text-ink-gray-8">Status</div>
							<div class="mb-3 flex flex-wrap gap-1.5">
								<Button
									v-for="preset in statusPresets"
									:key="preset.text"
									size="sm"
									@click="applyPreset(preset)"
								>
									{{ preset.emoji }} {{ preset.text }}
								</Button>
							</div>
							<div class="grid grid-cols-[4rem_1fr] gap-2">
								<FormControl v-model="form.status_emoji" placeholder="🙂" />
								<FormControl
									v-model="form.status_text"
									placeholder="What's your status?"
								/>
							</div>
							<FormControl
								v-model="form.availability"
								class="mt-3"
								type="select"
								label="Availability"
								:options="AVAILABILITY_OPTIONS"
							/>
						</div>

						<div class="flex justify-end gap-2">
							<Button @click="clearStatus">Clear status</Button>
							<Button @click="editing = false">Cancel</Button>
							<Button variant="solid" :loading="saving" @click="save">Save</Button>
						</div>
					</div>
				</div>
			</aside>
		</Transition>
	</Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Button, FormControl, call, dayjs, toast } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";
import PresenceDot from "./PresenceDot.vue";
import { AVAILABILITY_OPTIONS } from "@/utils/status";
import LucideX from "~icons/lucide/x";
import LucideCopy from "~icons/lucide/copy";
import LucideMessageCircle from "~icons/lucide/message-circle";
import LucidePencil from "~icons/lucide/pencil";
import LucideCamera from "~icons/lucide/camera";

const chat = useChat();
const user = computed(() => chat.profileUser);
const info = computed(() => user.value && chat.person(user.value));
const isMe = computed(() => user.value === session.user);
const initials = computed(() =>
	(info.value?.full_name || "?")
		.split(/\s+/)
		.slice(0, 2)
		.map((w) => w[0]?.toUpperCase())
		.join("")
);

const editing = ref(false);
const saving = ref(false);
const uploading = ref(false);
const photoInput = ref(null);
const now = ref(dayjs());
let clock = null;

function close() {
	chat.profileUser = null;
}

watch(user, () => (editing.value = false));

function localTime(tz) {
	const zone = tz || window.system_timezone;
	try {
		return `${now.value.tz(zone).format("hh:mm A")} (${zone})`;
	} catch (e) {
		return "—";
	}
}

const sections = computed(() => {
	const p = info.value;
	if (!p) return [];
	return [
		{
			title: "Contact",
			rows: [
				{ label: "Display name", value: p.full_name },
				{ label: "Email", value: p.email || p.user },
				{ label: "Phone", value: p.phone },
			],
		},
		{
			title: "Work",
			rows: [
				{ label: "Designation", value: p.designation },
				{ label: "Department", value: p.department },
				{ label: "Team", value: p.team },
				{
					label: "Reporting to",
					value: p.manager ? chat.displayName(p.manager) : null,
					user: p.manager,
				},
				{ label: "Skills", value: p.skills },
			],
		},
		{
			title: "Status",
			rows: [{ label: "Current status", value: chat.statusLabel(user.value) }],
		},
		{
			title: "Location",
			rows: [{ label: "Local time", value: localTime(p.time_zone) }],
		},
	];
});

// ---- my profile -------------------------------------------------------------

const statusPresets = [
	{ emoji: "🏠", text: "Working from home" },
	{ emoji: "🍴", text: "Lunch" },
	{ emoji: "📅", text: "In a meeting" },
	{ emoji: "💻", text: "Focus time" },
	{ emoji: "🚆", text: "Travelling" },
	{ emoji: "🏖️", text: "On leave" },
];
const editable = [
	"designation",
	"department",
	"team",
	"phone",
	"skills",
	"availability",
	"status_emoji",
	"status_text",
];
const form = reactive({});

function startEdit() {
	for (const key of editable)
		form[key] = info.value?.[key] || (key === "availability" ? "Auto" : "");
	editing.value = true;
}

function applyPreset(preset) {
	form.status_emoji = preset.emoji;
	form.status_text = preset.text;
}

function clearStatus() {
	form.status_emoji = "";
	form.status_text = "";
	form.availability = "Auto";
}

async function save() {
	saving.value = true;
	try {
		await call("aeraspace.api.directory.update_my_profile", { ...form });
		await chat.loadPeople();
		toast.create({ message: "Profile updated", type: "success" });
		editing.value = false;
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}

async function uploadPhoto(event) {
	const file = event.target.files[0];
	event.target.value = "";
	if (!file) return;
	uploading.value = true;
	try {
		await chat.uploadProfilePhoto(file);
		toast.create({ message: "Profile photo updated", type: "success" });
	} catch (error) {
		showError(error);
	} finally {
		uploading.value = false;
	}
}

async function removePhoto() {
	try {
		await chat.removeProfilePhoto();
	} catch (error) {
		showError(error);
	}
}

function copy(text) {
	navigator.clipboard?.writeText(text);
	toast.create({ message: "Copied", type: "success" });
}

function message() {
	const target = user.value;
	close();
	chat.openDirect(target);
}

function onKey(event) {
	if (event.key === "Escape" && user.value) close();
}

onMounted(() => {
	clock = setInterval(() => (now.value = dayjs()), 30 * 1000);
	window.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
	clearInterval(clock);
	window.removeEventListener("keydown", onKey);
});
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
.slide-enter-active,
.slide-leave-active {
	transition: transform 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
	transform: translateX(100%);
}
</style>
