<template>
	<AuthCard :title="titles[step]" :subtitle="subtitles[step]">
		<!-- 1. ask -->
		<form v-if="step === 'ask'" class="space-y-4" @submit.prevent="ask">
			<FormControl
				v-model="email"
				label="Your email"
				type="email"
				placeholder="you@aerele.in"
			/>
			<div v-if="error" class="rounded-md bg-surface-red-2 px-3 py-2 text-sm text-ink-red-4">
				{{ error }}
			</div>
			<Button
				variant="solid"
				class="w-full"
				type="submit"
				:loading="loading"
				:disabled="!email.trim()"
			>
				Ask an admin to reset it
			</Button>
		</form>

		<!-- 2. waiting -->
		<div v-else-if="step === 'waiting'" class="space-y-4 text-center">
			<LoadingIndicator class="mx-auto size-6" />
			<p class="text-base text-ink-gray-7">
				Your request was sent. When an admin approves it, this page will let you choose a
				new password.
			</p>
			<p class="text-sm text-ink-gray-5">
				Keep this tab open, or come back here later on this browser.
			</p>
			<Button class="w-full" @click="reset">Start over</Button>
		</div>

		<!-- 3. set new password -->
		<form v-else-if="step === 'approved'" class="space-y-4" @submit.prevent="complete">
			<FormControl
				v-model="newPassword"
				label="New password"
				:type="showPassword ? 'text' : 'password'"
				autocomplete="new-password"
			/>
			<FormControl
				v-model="confirmPassword"
				label="Confirm new password"
				:type="showPassword ? 'text' : 'password'"
				autocomplete="new-password"
			/>
			<label class="flex items-center gap-1.5 text-xs text-ink-gray-6">
				<input v-model="showPassword" type="checkbox" class="rounded" /> Show password
			</label>
			<p class="text-xs text-ink-gray-5">
				At least 8 characters. Mix letters, numbers and a symbol.
			</p>
			<div v-if="error" class="rounded-md bg-surface-red-2 px-3 py-2 text-sm text-ink-red-4">
				{{ error }}
			</div>
			<Button
				variant="solid"
				class="w-full"
				type="submit"
				:loading="loading"
				:disabled="!canSave"
			>
				Set new password
			</Button>
		</form>

		<!-- 4. finished / refused -->
		<div v-else class="space-y-4 text-center">
			<p class="text-base text-ink-gray-7">{{ endMessages[step] }}</p>
			<Button
				v-if="step === 'done'"
				variant="solid"
				class="w-full"
				@click="$router.push({ name: 'Login', query: { email: doneEmail } })"
			>
				Sign in
			</Button>
			<Button v-else class="w-full" @click="reset">Send a new request</Button>
		</div>

		<template #footer>
			<router-link :to="{ name: 'Login' }" class="text-ink-blue-3 hover:underline"
				>Back to sign in</router-link
			>
		</template>
	</AuthCard>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { Button, FormControl, LoadingIndicator, call } from "frappe-ui";
import AuthCard from "@/components/AuthCard.vue";

const STORAGE_KEY = "aeraspace-password-reset";
const POLL_MS = 15 * 1000;

const route = useRoute();
const step = ref("ask"); // ask | waiting | approved | done | rejected | expired
const email = ref(route.query.email || "");
const newPassword = ref("");
const confirmPassword = ref("");
const showPassword = ref(false);
const loading = ref(false);
const error = ref("");
const doneEmail = ref("");
let pending = null; // { request, claim_key }
let timer = null;

const titles = {
	ask: "Forgot your password?",
	waiting: "Waiting for approval",
	approved: "Choose a new password",
	done: "Password changed",
	rejected: "Request declined",
	expired: "Request expired",
};
const subtitles = {
	ask: "An admin approves the reset, then you set a new password here.",
	waiting: "",
	approved: "An admin approved your request.",
	done: "",
	rejected: "",
	expired: "",
};
const endMessages = {
	done: "Your password was changed. Sign in with your new password.",
	rejected: "An admin declined this request. Please contact them directly.",
	expired: "This request expired or was replaced by a newer one. You can send a new request.",
};

const canSave = computed(
	() => newPassword.value.length >= 8 && newPassword.value === confirmPassword.value
);

function remember(value) {
	try {
		value
			? localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
			: localStorage.removeItem(STORAGE_KEY);
	} catch (e) {
		// storage unavailable: the request still works while this tab stays open
	}
}

function recall() {
	try {
		return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
	} catch (e) {
		return null;
	}
}

async function ask() {
	loading.value = true;
	error.value = "";
	try {
		const result = await call("aeraspace.api.password_reset.request_reset", {
			email: email.value.trim(),
		});
		pending = { request: result.request, claim_key: result.claim_key };
		remember(pending);
		step.value = "waiting";
		poll();
	} catch (e) {
		error.value = e?.messages?.[0] || "Couldn't send the request. Please try again.";
	} finally {
		loading.value = false;
	}
}

async function check() {
	if (!pending) return;
	try {
		const { status } = await call("aeraspace.api.password_reset.get_status", pending);
		if (status === "approved") step.value = "approved";
		else if (status === "rejected") step.value = "rejected";
		else if (status === "expired" || status === "completed") step.value = "expired";
		if (status !== "pending") {
			clearInterval(timer);
			if (status !== "approved") remember(null);
		}
	} catch (e) {
		// temporary network issue: keep polling
	}
}

function poll() {
	clearInterval(timer);
	check();
	timer = setInterval(check, POLL_MS);
}

async function complete() {
	loading.value = true;
	error.value = "";
	try {
		const result = await call("aeraspace.api.password_reset.complete_reset", {
			...pending,
			new_password: newPassword.value,
		});
		doneEmail.value = result.email;
		remember(null);
		step.value = "done";
	} catch (e) {
		error.value = e?.messages?.[0] || "Couldn't change the password.";
	} finally {
		loading.value = false;
	}
}

function reset() {
	clearInterval(timer);
	remember(null);
	pending = null;
	step.value = "ask";
	error.value = "";
}

onMounted(() => {
	pending = recall();
	if (pending) {
		step.value = "waiting";
		poll();
	}
});
onBeforeUnmount(() => clearInterval(timer));
</script>
