<template>
	<Dialog v-model="open" :options="{ title: user ? 'Edit user' : 'New user', size: 'lg' }">
		<template #body-content>
			<div class="space-y-4">
				<div class="grid grid-cols-2 gap-3">
					<FormControl v-model="form.first_name" label="First name" />
					<FormControl v-model="form.last_name" label="Last name (optional)" />
				</div>
				<FormControl
					v-model="form.email"
					label="Email (used to sign in)"
					type="email"
					:disabled="!!user"
					placeholder="name@aerele.in"
				/>
				<div v-if="!user">
					<FormControl
						v-model="form.password"
						label="Password"
						placeholder="Leave empty to generate a strong one"
					/>
					<div class="mt-1 text-xs text-ink-gray-5">
						At least 8 characters. You'll see it once after saving, to share with them.
					</div>
				</div>
				<div class="grid grid-cols-2 gap-3">
					<FormControl v-model="form.designation" label="Designation" />
					<FormControl v-model="form.department" label="Department" />
					<FormControl v-model="form.team" label="Team" />
					<FormControl v-model="form.phone" label="Phone" />
				</div>
				<FormControl
					:model-value="form.manager"
					type="select"
					label="Reporting to"
					:options="[{ label: 'No manager', value: '' }, ...managerOptions]"
					@update:model-value="(v) => (form.manager = v)"
				/>
				<label class="flex items-start gap-2 rounded-md border px-3 py-2">
					<input
						v-model="form.is_admin"
						type="checkbox"
						class="mt-0.5 rounded"
						:disabled="lockAdmin"
					/>
					<span>
						<span class="block text-base text-ink-gray-8">Admin</span>
						<span class="block text-xs text-ink-gray-5">
							Can manage users and approve password resets.
							<template v-if="lockAdmin">
								You can't remove your own admin access.</template
							>
						</span>
					</span>
				</label>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				class="w-full"
				:loading="saving"
				:disabled="!canSave"
				@click="save"
			>
				{{ user ? "Save changes" : "Create user" }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormControl, call, toast } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";

const props = defineProps({
	user: { type: Object, default: null }, // row from list_users when editing
	people: { type: Array, default: () => [] }, // all users, for the manager picker
});
const emit = defineEmits(["saved"]);
const open = defineModel({ type: Boolean });
const chat = useChat();
const saving = ref(false);
const form = reactive({});

const lockAdmin = computed(
	() => !!props.user && [session.user, "Administrator"].includes(props.user.user)
);
const managerOptions = computed(() =>
	props.people
		.filter((p) => p.enabled && p.user !== props.user?.user)
		.map((p) => ({ label: chat.listName(p.user) || p.full_name, value: p.user }))
);
const canSave = computed(() => form.first_name?.trim() && (props.user || form.email?.trim()));

watch(open, (value) => {
	if (!value) return;
	const u = props.user || {};
	Object.assign(form, {
		first_name: u.first_name || "",
		last_name: u.last_name || "",
		email: u.email || "",
		password: "",
		designation: u.designation || "",
		department: u.department || "",
		team: u.team || "",
		phone: u.phone || "",
		manager: u.manager || "",
		is_admin: !!u.is_admin,
	});
});

async function save() {
	saving.value = true;
	const values = { ...form, is_admin: form.is_admin ? 1 : 0 };
	try {
		if (props.user) {
			delete values.email;
			delete values.password;
			await call("aeraspace.api.admin_users.update_user", {
				user: props.user.user,
				...values,
			});
			toast.create({ message: "User updated", type: "success" });
			emit("saved", null);
		} else {
			const result = await call("aeraspace.api.admin_users.create_user", {
				...values,
				password: values.password || null,
			});
			emit("saved", {
				email: result.user.user,
				password: result.password || values.password,
			});
		}
		open.value = false;
		chat.loadPeople();
	} catch (error) {
		showError(error);
	} finally {
		saving.value = false;
	}
}
</script>
