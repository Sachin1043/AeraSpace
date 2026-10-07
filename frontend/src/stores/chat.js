import { defineStore } from "pinia";
import { computed, reactive, ref, watch } from "vue";
import { call, dayjs, toast } from "frappe-ui";

import router from "@/router";
import { session } from "@/session";
import { useSocket } from "@/socket";
import { encodeMentions, decodeMentions } from "@/utils/mentions";
import { plainText } from "@/utils/format";
import { projectOf } from "@/utils/tasks";

const API = "aeraspace.api";
const HEARTBEAT_MS = 30 * 1000;
const PRESENCE_REFRESH_MS = 60 * 1000;
const IDLE_AFTER_MS = 10 * 60 * 1000;
const TYPING_SEND_EVERY_MS = 3000;
const TYPING_SHOW_FOR_MS = 5000;

export const STATUS_LABELS = {
	online: "Available",
	away: "Away",
	busy: "Busy",
	dnd: "Do not disturb",
	invisible: "Invisible",
	offline: "Offline",
};

// profile availability value -> presence status shown to people
const AVAILABILITY_STATUS = { Away: "away", Busy: "busy", "Do Not Disturb": "dnd" };

export function showError(error) {
	toast.create({
		message: error?.messages?.[0] || error?.message || "Something went wrong",
		type: "error",
	});
}

// typing indicators are shown per conversation or per thread
const typingKey = (channel, threadRoot) => (threadRoot ? `thread:${threadRoot}` : channel);

export const useChat = defineStore("chat", () => {
	const people = ref({});
	const presence = ref({});
	const sidebar = ref([]);
	const sidebarLoaded = ref(false);
	const conversations = reactive({}); // channel -> { messages, hasMore, loading, loaded }
	const threads = reactive({}); // root -> { root, replies, isFollowing, loaded }
	const typing = reactive({}); // typingKey -> { user: timeout }
	const bookmarks = ref(new Set());
	const activeChannel = ref(null);
	const activeThread = ref(null);
	const readMarks = reactive({}); // channel -> { user: last_read_at } for read receipts
	const pendingResets = ref(0); // admins: forgotten-password requests waiting for approval

	async function loadPendingResets() {
		if (!session.isAdmin) return;
		pendingResets.value = await call(`${API}.admin_users.pending_reset_count`).catch(() => 0);
	}

	function setReadMarks(channel, members) {
		readMarks[channel] = Object.fromEntries(
			(members || []).map((m) => [m.user, m.last_read_at])
		);
	}
	const unreadNotifications = ref(0);
	const profileUser = ref(null); // whose profile panel is open
	const notificationPermission = ref(
		typeof Notification === "undefined" ? "unsupported" : Notification.permission
	);

	let initialized = false;
	let lastActivity = Date.now();
	let lastTypingSent = {};
	let markReadTimer = null;

	// ---- people & presence -------------------------------------------------

	const peopleList = computed(() => Object.values(people.value));

	function person(user) {
		return people.value[user] || { user, full_name: user };
	}

	// who-did-it labels: "You" for the current user, their name for everyone else
	function displayName(user) {
		return user === session.user ? "You" : person(user).full_name;
	}

	// lists of people: keep the name but mark yourself
	function listName(user) {
		return user === session.user ? `${person(user).full_name} (you)` : person(user).full_name;
	}

	// the one status people see: a custom status if set, otherwise the availability
	function statusLabel(user) {
		const status = statusOf(user);
		const p = people.value[user];
		const custom = [p?.status_emoji, p?.status_text].filter(Boolean).join(" ");
		if (custom && !["offline", "invisible"].includes(status)) return custom;
		return STATUS_LABELS[status];
	}

	function viewProfile(user) {
		profileUser.value = user;
	}

	async function uploadProfilePhoto(file) {
		const form = new FormData();
		form.append("file", file, file.name);
		const response = await fetch(`/api/method/${API}.directory.upload_profile_photo`, {
			method: "POST",
			headers: { Accept: "application/json", "X-Frappe-CSRF-Token": window.csrf_token },
			body: form,
		});
		const body = await response.json().catch(() => ({}));
		if (!response.ok) {
			let message = "Upload failed";
			try {
				message = JSON.parse(JSON.parse(body._server_messages)[0]).message;
			} catch (e) {
				// no server message: keep the generic one
			}
			throw new Error(message);
		}
		window.user_image = body.message;
		await loadPeople();
		return body.message;
	}

	async function removeProfilePhoto() {
		await call(`${API}.directory.remove_profile_photo`);
		window.user_image = null;
		await loadPeople();
	}

	function statusOf(user) {
		const availability = people.value[user]?.availability;
		// you always see your own chosen status; the server hides "Invisible" from everyone else
		if (user === session.user && availability === "Invisible") return "invisible";
		const state = presence.value[user] || "offline";
		if (state === "offline") return "offline";
		return AVAILABILITY_STATUS[availability] || state;
	}

	// choosing any status replaces the previous one (default statuses clear the custom message)
	async function setStatus({ availability, emoji = "", text = "" }) {
		await updateMyProfile({ availability, status_emoji: emoji, status_text: text });
	}

	async function updateMyProfile(values) {
		const me = people.value[session.user];
		const previous = me ? { ...me } : null;
		if (me) Object.assign(me, values); // optimistic
		try {
			await call(`${API}.directory.update_my_profile`, values);
		} catch (error) {
			if (previous) people.value[session.user] = previous;
			showError(error);
		}
	}

	async function loadPeople() {
		const rows = await call(`${API}.directory.get_people`);
		people.value = Object.fromEntries(rows.map((row) => [row.user, row]));
	}

	async function loadPresence() {
		presence.value = await call(`${API}.presence.get_presence`);
	}

	function currentState() {
		return Date.now() - lastActivity > IDLE_AFTER_MS ? "away" : "online";
	}

	function heartbeat() {
		const state = currentState();
		presence.value[session.user] = state;
		call(`${API}.presence.heartbeat`, { state }).catch(() => {});
	}

	function trackActivity() {
		const markActive = () => {
			const wasIdle = currentState() === "away";
			lastActivity = Date.now();
			if (wasIdle) heartbeat();
		};
		for (const event of ["mousemove", "keydown", "click", "focus"]) {
			window.addEventListener(event, markActive, { passive: true });
		}
	}

	// ---- sidebar ----------------------------------------------------------

	const NAMED = ["Public", "Private", "Announcement"];
	const channels = computed(() =>
		sidebar.value
			.filter((c) => NAMED.includes(c.channel_type))
			.sort((a, b) => a.channel_name.localeCompare(b.channel_name))
	);
	const directMessages = computed(() =>
		sidebar.value.filter((c) => ["Direct", "Group"].includes(c.channel_type))
	);

	async function loadSidebar() {
		sidebar.value = await call(`${API}.chat.get_sidebar`);
		sidebarLoaded.value = true;
	}

	function sidebarEntry(channel) {
		return sidebar.value.find((c) => c.name === channel);
	}

	function channelTitle(channel) {
		if (!channel) return "";
		if (NAMED.includes(channel.channel_type)) return channel.channel_name;
		if (channel.channel_type === "Group" && channel.channel_name) return channel.channel_name;

		const others = (channel.members || []).filter((u) => u !== session.user);
		if (!others.length) return `${person(session.user).full_name} (you)`;
		return others.map((u) => person(u).full_name).join(", ");
	}

	function dmPartner(channel) {
		if (channel?.channel_type !== "Direct") return null;
		return (channel.members || []).find((u) => u !== session.user) || session.user;
	}

	function notifyLevel(channel) {
		if (!channel) return "Mentions";
		if (channel.notify && channel.notify !== "Default") return channel.notify;
		return ["Direct", "Group"].includes(channel.channel_type) ? "All" : "Mentions";
	}

	function isMuted(channel) {
		return notifyLevel(channel) === "Nothing";
	}

	async function setChannelNotify(channel, level) {
		try {
			await call(`${API}.notifications.set_channel_notify`, { channel, level });
			const entry = sidebarEntry(channel);
			if (entry) entry.notify = level;
			toast.create({
				message: `Notifications: ${level === "Default" ? "default" : level.toLowerCase()}`,
				type: "success",
			});
		} catch (error) {
			showError(error);
		}
	}

	// ---- messages ---------------------------------------------------------

	function conversation(channel) {
		if (!conversations[channel]) {
			conversations[channel] = {
				messages: [],
				hasMore: false,
				loading: false,
				loaded: false,
			};
		}
		return conversations[channel];
	}

	function thread(root) {
		if (!threads[root])
			threads[root] = { root: null, replies: [], isFollowing: false, loaded: false };
		return threads[root];
	}

	async function loadMessages(channel) {
		const convo = conversation(channel);
		convo.loading = true;
		try {
			const page = await call(`${API}.chat.get_messages`, { channel });
			convo.messages = page.messages;
			convo.hasMore = page.has_more;
			convo.loaded = true;
		} finally {
			convo.loading = false;
		}
	}

	async function loadOlder(channel) {
		const convo = conversation(channel);
		if (convo.loading || !convo.hasMore || !convo.messages.length) return false;
		convo.loading = true;
		try {
			const page = await call(`${API}.chat.get_messages`, {
				channel,
				before: convo.messages[0].creation,
			});
			convo.messages.unshift(...page.messages);
			convo.hasMore = page.has_more;
			return page.messages.length > 0;
		} finally {
			convo.loading = false;
		}
	}

	async function loadThread(root) {
		const data = await call(`${API}.chat.get_thread`, { thread_root: root });
		Object.assign(thread(root), {
			root: data.root,
			replies: data.replies,
			isFollowing: data.is_following,
			loaded: true,
		});
	}

	function listFor(message) {
		if (message.thread_root) {
			const t = threads[message.thread_root];
			return t?.loaded ? t.replies : null;
		}
		const convo = conversations[message.channel];
		return convo?.loaded ? convo.messages : null;
	}

	function upsertMessage(message) {
		// keep an open thread's root in sync (reply counts, reactions, edits)
		if (threads[message.name]?.loaded) threads[message.name].root = message;

		const list = listFor(message);
		if (!list) return;
		const index = list.findIndex(
			(m) =>
				m.name === message.name || (message.client_id && m.client_id === message.client_id)
		);
		if (index === -1) list.push(message);
		else list[index] = { ...list[index], ...message, pending: false, failed: false };
	}

	async function send(channel, content, { files = [], threadRoot = null, replyTo = null } = {}) {
		content = encodeMentions((content || "").trim(), peopleList.value);
		if (!content && !files.length) return;
		const clientId = `${session.user}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
		const pending = {
			name: clientId,
			client_id: clientId,
			channel,
			sender: session.user,
			message_type: "Text",
			content,
			files,
			thread_root: threadRoot,
			reply_to: replyTo
				? { name: replyTo.name, sender: replyTo.sender, content: replyTo.content }
				: null,
			reply_count: 0,
			reactions: {},
			creation: dayjs().tz(window.system_timezone).format("YYYY-MM-DD HH:mm:ss.SSS000"),
			pending: true,
		};
		listFor(pending)?.push(pending);
		delete lastTypingSent[typingKey(channel, threadRoot)];

		try {
			const saved = await call(`${API}.chat.send_message`, {
				channel,
				content,
				client_id: clientId,
				files: files.map((f) => f.name),
				thread_root: threadRoot,
				reply_to: replyTo?.name,
			});
			upsertMessage(saved);
		} catch (error) {
			const list = listFor(pending);
			const index = list?.findIndex((m) => m.client_id === clientId) ?? -1;
			if (index !== -1) list[index] = { ...list[index], pending: false, failed: true };
			showError(error);
		}
	}

	async function act(method, args) {
		try {
			const updated = await call(`${API}.chat.${method}`, args);
			if (updated?.name) upsertMessage(updated);
			return updated;
		} catch (error) {
			showError(error);
		}
	}

	const editMessage = (message, content) =>
		act("edit_message", {
			message: message.name,
			content: encodeMentions(content, peopleList.value),
		});
	const editableText = (message) => decodeMentions(message.content, person);
	const deleteMessage = (message) => act("delete_message", { message: message.name });
	const toggleReaction = (message, emoji) =>
		act("toggle_reaction", { message: message.name, emoji });
	const togglePin = (message) => act("toggle_pin", { message: message.name });

	async function toggleBookmark(message) {
		try {
			const saved = await call(`${API}.chat.toggle_bookmark`, { message: message.name });
			const next = new Set(bookmarks.value);
			saved ? next.add(message.name) : next.delete(message.name);
			bookmarks.value = next;
			toast.create({
				message: saved ? "Saved for later" : "Removed from saved items",
				type: "success",
			});
		} catch (error) {
			showError(error);
		}
	}

	async function toggleFollow(root) {
		try {
			thread(root).isFollowing = await call(`${API}.chat.toggle_follow`, {
				thread_root: root,
			});
		} catch (error) {
			showError(error);
		}
	}

	async function uploadFile(channel, file, onProgress) {
		// XHR (not fetch) so the composer can show upload progress
		return new Promise((resolve, reject) => {
			const form = new FormData();
			form.append("file", file, file.name);
			form.append("channel", channel);
			const xhr = new XMLHttpRequest();
			xhr.open("POST", `/api/method/${API}.files.upload`);
			xhr.setRequestHeader("Accept", "application/json");
			xhr.setRequestHeader("X-Frappe-CSRF-Token", window.csrf_token);
			xhr.upload.onprogress = (e) =>
				e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
			xhr.onload = () => {
				let body = {};
				try {
					body = JSON.parse(xhr.responseText);
				} catch (e) {
					// not JSON (e.g. a proxy error page): the status check below handles it
				}
				if (xhr.status === 200) return resolve(body.message);
				let message = "Upload failed";
				try {
					message = JSON.parse(JSON.parse(body._server_messages)[0]).message;
				} catch (e) {
					// no server message: keep the generic one
				}
				reject(new Error(message));
			};
			xhr.onerror = () => reject(new Error("Upload failed"));
			xhr.send(form);
		});
	}

	function markRead(channel) {
		const entry = sidebarEntry(channel);
		if (!entry) return;
		entry.unread = 0;
		clearTimeout(markReadTimer);
		markReadTimer = setTimeout(
			() => call(`${API}.chat.mark_read`, { channel }).catch(() => {}),
			500
		);
	}

	function isViewing(channel) {
		return activeChannel.value === channel && document.visibilityState === "visible";
	}

	// ---- typing -----------------------------------------------------------

	function notifyTyping(channel, threadRoot = null) {
		const key = typingKey(channel, threadRoot);
		const now = Date.now();
		if (now - (lastTypingSent[key] || 0) < TYPING_SEND_EVERY_MS) return;
		lastTypingSent[key] = now;
		call(`${API}.chat.typing`, { channel, thread_root: threadRoot }).catch(() => {});
	}

	function typingUsers(channel, threadRoot = null) {
		return Object.keys(typing[typingKey(channel, threadRoot)] || {});
	}

	function setTyping(key, user, isTyping) {
		typing[key] = typing[key] || {};
		clearTimeout(typing[key][user]);
		if (isTyping) {
			typing[key][user] = setTimeout(() => setTyping(key, user, false), TYPING_SHOW_FOR_MS);
		} else {
			delete typing[key][user];
		}
	}

	// ---- conversations ----------------------------------------------------

	async function openDirect(user) {
		try {
			const channel = await call(`${API}.chat.get_or_create_dm`, { user });
			await loadSidebar();
			router.push({ name: "Conversation", params: { channel } });
		} catch (error) {
			showError(error);
		}
	}

	async function startConversation(users, channelName) {
		const channel = await call(`${API}.chat.create_group`, {
			users,
			channel_name: channelName,
		});
		await loadSidebar();
		router.push({ name: "Conversation", params: { channel } });
	}

	// ---- tasks (pages subscribe to live board updates) ----------------------

	const taskListeners = new Set();
	function onTaskEvent(listener) {
		taskListeners.add(listener);
		return () => taskListeners.delete(listener);
	}
	const emitTask = (type) => (payload) =>
		taskListeners.forEach((listener) => listener(type, payload));

	// tasks made in Desk (TASK-2026-00001) don't carry their project in the name, so pass it when known
	function openTask(task, project) {
		router.push({
			name: "Project",
			params: { project: project || projectOf(task) },
			query: { task },
		});
	}

	// ---- notifications ----------------------------------------------------

	async function loadUnreadNotifications() {
		unreadNotifications.value = await call(`${API}.notifications.get_unread_count`);
	}

	async function markNotificationsRead(names = null) {
		unreadNotifications.value = await call(`${API}.notifications.mark_notifications_read`, {
			names,
		});
	}

	async function enableDesktopNotifications() {
		if (typeof Notification === "undefined") return;
		notificationPermission.value = await Notification.requestPermission();
	}

	function notificationTitle(n) {
		if (n.notification_type === "Reminder") return `⏰ ${n.preview}`;
		if (n.notification_type === "Password Reset") return `🔑 ${n.preview}`;
		const from = person(n.from_user).full_name;
		const entry = sidebarEntry(n.channel);
		const where =
			entry && ["Direct"].includes(entry.channel_type)
				? ""
				: entry
				? ` in ${
						entry.channel_type === "Group"
							? channelTitle(entry)
							: "#" + entry.channel_name
				  }`
				: "";
		if (n.notification_type === "Mention") return `${from} mentioned you${where}`;
		if (n.notification_type === "Thread Reply") return `${from} replied to a thread${where}`;
		if (n.notification_type === "Invite")
			return `${from} ${n.preview}${where.replace(" in ", " ")}`;
		if (["Assignment", "Task Update"].includes(n.notification_type))
			return `${from} ${plainText(n.preview, person)}`;
		return `${from}${where}`;
	}

	function notificationRoute(n) {
		if (n.notification_type === "Reminder") return { name: "EOD" };
		if (n.notification_type === "Password Reset")
			return { name: "AdminUsers", query: { tab: "requests" } };
		if (n.task)
			return {
				name: "Project",
				params: { project: n.project || projectOf(n.task) },
				query: { task: n.task },
			};
		if (!n.channel) return { name: "Activity" };
		const query = n.thread_root
			? { thread: n.thread_root }
			: n.message
			? { message: n.message }
			: {};
		return { name: "Conversation", params: { channel: n.channel }, query };
	}

	function onNotify(n) {
		if (n.name) unreadNotifications.value += 1;

		// already looking at it? stay quiet
		const lookingAt = n.thread_root
			? activeThread.value === n.thread_root
			: activeChannel.value === n.channel;
		if (lookingAt && document.visibilityState === "visible") return;
		if (statusOf(session.user) === "dnd") return;

		const title = notificationTitle(n);
		const body = ["Invite", "Assignment", "Task Update"].includes(n.notification_type)
			? ""
			: plainText(n.preview, person);
		if (document.visibilityState === "visible") {
			if (n.notification_type !== "Message")
				toast.create({
					message: `<b>${title}</b>${body ? ": " + body.slice(0, 80) : ""}`,
					type: "info",
				});
			return;
		}
		if (notificationPermission.value === "granted") {
			const popup = new Notification(title, {
				body,
				tag: n.message || n.channel,
				icon: "/assets/aeraspace/frontend/favicon.svg",
			});
			popup.onclick = () => {
				window.focus();
				router.push(notificationRoute(n));
				if (n.name) markNotificationsRead([n.name]);
				popup.close();
			};
		}
	}

	// total unread shown in the browser tab title
	const totalUnread = computed(
		() =>
			sidebar.value.reduce((sum, c) => sum + (isMuted(c) ? 0 : c.unread || 0), 0) +
			unreadNotifications.value
	);
	watch(
		totalUnread,
		(count) => (document.title = count ? `(${count}) AeraSpace` : "AeraSpace"),
		{ immediate: true }
	);

	// ---- realtime ---------------------------------------------------------

	function onMessage(message) {
		upsertMessage(message);
		setTyping(typingKey(message.channel, message.thread_root), message.sender, false);
		if (message.thread_root) return; // thread replies don't touch the channel list or unread counts

		const entry = sidebarEntry(message.channel);
		if (!entry) return; // open channel we haven't joined
		entry.last_message_at = message.creation;
		entry.last_message_preview = plainText(message.content, person) || "📎 File";
		sidebar.value = [entry, ...sidebar.value.filter((c) => c !== entry)];

		if (message.sender === session.user) return;
		if (isViewing(message.channel)) markRead(message.channel);
		else entry.unread = (entry.unread || 0) + 1;
	}

	function bindSocket() {
		const socket = useSocket();
		if (!socket) return;
		socket.on("as_message_new", onMessage);
		socket.on("as_message_update", upsertMessage);
		socket.on("as_sidebar_update", () => loadSidebar());
		socket.on(
			"as_typing",
			({ channel, thread_root, user }) =>
				user !== session.user && setTyping(typingKey(channel, thread_root), user, true)
		);
		socket.on(
			"as_presence",
			({ user, state }) => user !== session.user && (presence.value[user] = state)
		);
		socket.on("as_profile_update", () => loadPeople());
		socket.on("as_reset_requests", () => loadPendingResets());
		socket.on("as_read", ({ channel, user, last_read_at }) => {
			if (readMarks[channel]) readMarks[channel][user] = last_read_at;
		});
		socket.on("as_notify", onNotify);
		socket.on("as_task_update", emitTask("update"));
		socket.on("as_task_delete", emitTask("delete"));
		socket.on("as_task_reorder", emitTask("reorder"));
		// after a dropped connection, catch up on anything we missed
		socket.io.on("reconnect", () => {
			loadSidebar();
			loadPresence();
			loadUnreadNotifications();
			if (activeChannel.value) loadMessages(activeChannel.value);
			if (activeThread.value) loadThread(activeThread.value);
		});
	}

	async function init() {
		if (initialized) return;
		initialized = true;
		bindSocket();
		trackActivity();
		heartbeat();
		setInterval(heartbeat, HEARTBEAT_MS);
		setInterval(loadPresence, PRESENCE_REFRESH_MS);
		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState === "visible" && activeChannel.value)
				markRead(activeChannel.value);
		});
		const [, , , saved] = await Promise.all([
			loadPeople(),
			loadPresence(),
			loadSidebar(),
			call(`${API}.chat.get_bookmarked_ids`),
			loadUnreadNotifications(),
			loadPendingResets(),
		]);
		bookmarks.value = new Set(saved);
	}

	return {
		people,
		peopleList,
		presence,
		sidebar,
		sidebarLoaded,
		channels,
		directMessages,
		bookmarks,
		activeChannel,
		activeThread,
		readMarks,
		pendingResets,
		loadPendingResets,
		setReadMarks,
		unreadNotifications,
		notificationPermission,
		totalUnread,
		init,
		person,
		displayName,
		listName,
		statusOf,
		statusLabel,
		setStatus,
		profileUser,
		viewProfile,
		uploadProfilePhoto,
		removeProfilePhoto,
		loadPeople,
		loadSidebar,
		sidebarEntry,
		channelTitle,
		dmPartner,
		conversation,
		thread,
		loadMessages,
		loadOlder,
		loadThread,
		send,
		editMessage,
		deleteMessage,
		toggleReaction,
		togglePin,
		toggleBookmark,
		toggleFollow,
		uploadFile,
		markRead,
		notifyTyping,
		typingUsers,
		openDirect,
		startConversation,
		editableText,
		notifyLevel,
		isMuted,
		setChannelNotify,
		loadUnreadNotifications,
		markNotificationsRead,
		enableDesktopNotifications,
		notificationTitle,
		notificationRoute,
		onTaskEvent,
		openTask,
	};
});
