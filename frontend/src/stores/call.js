import { defineStore } from "pinia";
import { computed, markRaw, reactive, ref, shallowRef } from "vue";
import { call as request, toast } from "frappe-ui";

import { useSocket } from "@/socket";
import { session } from "@/session";
import { showError, useChat } from "@/stores/chat";

const API = "aeraspace.api.call";
// public STUN server: lets two browsers on different networks find a direct route to each other
const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];
const PING_MS = 15000;
const RING_MS = 30000;

/*
 * Calls are browser to browser (WebRTC, one connection per other participant). The server keeps who is
 * in the call and passes offers/answers along. Whoever joins sends an offer to everyone already there.
 * Each connection always carries one audio and one video slot, so turning the camera on/off or sharing
 * the screen just swaps the track in the slot and never needs a new offer.
 */
export const useCall = defineStore("call", () => {
	const chat = useChat();

	const active = ref(null); // the call I'm in
	const incoming = ref(null); // a call ringing for me
	const activeCalls = reactive({}); // channel -> running call (for the "Join call" button)
	const peers = reactive({}); // user -> { stream, muted, camera, sharing, connected }
	const muted = ref(false);
	const cameraOn = ref(false);
	const sharing = ref(false);
	const expanded = ref(true);
	const busy = ref(false);
	const localVideo = shallowRef(null); // what I'm sending (camera or screen), for my own tile
	const startedAt = ref(null);

	const connections = {}; // user -> RTCPeerConnection
	let audioTrack = null;
	let cameraTrack = null;
	let screenTrack = null;
	let pingTimer = null;
	let noAnswerTimer = null;
	let ringTimer = null;
	let ringtone = null;
	let initialized = false;

	const inCall = computed(() => !!active.value);
	const others = computed(() => Object.keys(peers));

	function callTitle(c) {
		if (!c) return "";
		if (c.channel_type === "Direct") {
			const other = c.started_by === session.user ? null : c.started_by;
			const entry = chat.sidebarEntry(c.channel);
			return other ? chat.person(other).full_name : chat.channelTitle(entry) || "Call";
		}
		const entry = chat.sidebarEntry(c.channel);
		return entry ? chat.channelTitle(entry) : c.channel_name;
	}

	// ---- media ------------------------------------------------------------

	async function getMedia(withVideo) {
		if (!navigator.mediaDevices?.getUserMedia) {
			throw new Error(
				"Calls need a secure page. Open AeraSpace on https:// or http://localhost."
			);
		}
		try {
			const stream = await navigator.mediaDevices.getUserMedia({
				audio: { echoCancellation: true, noiseSuppression: true },
				video: withVideo,
			});
			audioTrack = stream.getAudioTracks()[0] || null;
			cameraTrack = stream.getVideoTracks()[0] || null;
		} catch (error) {
			if (!withVideo) throw micError(error);
			// no camera (or it was blocked): carry on with audio only
			const stream = await navigator.mediaDevices
				.getUserMedia({ audio: true })
				.catch((e) => Promise.reject(micError(e)));
			audioTrack = stream.getAudioTracks()[0];
			cameraTrack = null;
			toast.create({ message: "Camera not available, joining with audio", type: "warning" });
		}
		muted.value = false;
		cameraOn.value = !!cameraTrack;
		refreshLocalVideo();
	}

	function micError(error) {
		return new Error(
			error?.name === "NotAllowedError"
				? "Allow microphone access in your browser to join the call."
				: "No microphone found."
		);
	}

	function outgoingVideo() {
		return screenTrack || (cameraOn.value ? cameraTrack : null);
	}

	function refreshLocalVideo() {
		const track = outgoingVideo();
		localVideo.value = track ? markRaw(new MediaStream([track])) : null;
	}

	function attachLocal(pc) {
		for (const t of pc.getTransceivers()) {
			const kind = t.receiver.track?.kind;
			t.sender.replaceTrack(kind === "audio" ? audioTrack : outgoingVideo()).catch(() => {});
		}
	}

	function updateSenders() {
		refreshLocalVideo();
		for (const pc of Object.values(connections)) attachLocal(pc);
		broadcastState();
	}

	function myState() {
		return { muted: muted.value, camera: !!outgoingVideo(), sharing: sharing.value };
	}

	// ---- connections --------------------------------------------------------

	function createPeer(user) {
		dropPeer(user);
		const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
		connections[user] = pc;
		peers[user] = {
			stream: markRaw(new MediaStream()),
			muted: false,
			camera: false,
			sharing: false,
			connected: false,
		};
		pc.ontrack = (event) => {
			const stream = peers[user]?.stream;
			if (stream && !stream.getTracks().includes(event.track)) stream.addTrack(event.track);
		};
		pc.onconnectionstatechange = () => {
			if (!peers[user]) return;
			if (pc.connectionState === "connected") peers[user].connected = true;
			if (pc.connectionState === "failed") dropPeer(user);
		};
		return pc;
	}

	function dropPeer(user) {
		connections[user]?.close();
		delete connections[user];
		delete peers[user];
	}

	// wait until the connection has found its addresses, so one message carries everything
	function gathered(pc) {
		return new Promise((resolve) => {
			if (pc.iceGatheringState === "complete") return resolve();
			const check = () => {
				if (pc.iceGatheringState !== "complete") return;
				pc.removeEventListener("icegatheringstatechange", check);
				resolve();
			};
			pc.addEventListener("icegatheringstatechange", check);
			setTimeout(resolve, 2500);
		});
	}

	function send(to, data) {
		if (!active.value) return;
		return request(`${API}.signal`, {
			call: active.value.name,
			to,
			data: JSON.stringify(data),
		}).catch(() => {});
	}

	async function connectTo(user) {
		const pc = createPeer(user);
		pc.addTransceiver("audio", { direction: "sendrecv" });
		pc.addTransceiver("video", { direction: "sendrecv" });
		attachLocal(pc);
		await pc.setLocalDescription(await pc.createOffer());
		await gathered(pc);
		if (connections[user] !== pc) return;
		send(user, { type: "offer", sdp: pc.localDescription.sdp, state: myState() });
	}

	async function onOffer(from, data) {
		const mine = connections[from];
		// both sides offered at once: the one with the "smaller" email gives way
		if (mine?.signalingState === "have-local-offer" && session.user > from) return;
		const pc = createPeer(from);
		await pc.setRemoteDescription({ type: "offer", sdp: data.sdp });
		for (const t of pc.getTransceivers()) t.direction = "sendrecv";
		attachLocal(pc);
		await pc.setLocalDescription(await pc.createAnswer());
		await gathered(pc);
		if (connections[from] !== pc) return;
		applyState(from, data.state);
		send(from, { type: "answer", sdp: pc.localDescription.sdp, state: myState() });
	}

	async function onAnswer(from, data) {
		const pc = connections[from];
		if (pc?.signalingState !== "have-local-offer") return;
		await pc.setRemoteDescription({ type: "answer", sdp: data.sdp });
		applyState(from, data.state);
	}

	function applyState(user, state) {
		if (peers[user] && state) Object.assign(peers[user], state);
	}

	function broadcastState() {
		for (const user of Object.keys(connections))
			send(user, { type: "state", state: myState() });
	}

	async function onSignal({ call: name, from, data }) {
		if (active.value?.name !== name) return;
		try {
			if (data.type === "offer") await onOffer(from, data);
			else if (data.type === "answer") await onAnswer(from, data);
			else if (data.type === "state") applyState(from, data.state);
		} catch (error) {
			console.error("call signal failed", error);
		}
	}

	// ---- joining / leaving ------------------------------------------------------

	async function start(channel, callType = "Video") {
		if (busy.value) return;
		if (active.value) {
			if (active.value.channel === channel) return (expanded.value = true);
			await leave();
		}
		await enter(
			() => request(`${API}.start_call`, { channel, call_type: callType }),
			callType
		);
		// nobody picked up a one-to-one call
		if (active.value && !others.value.length && active.value.channel_type === "Direct") {
			const name = active.value.name;
			noAnswerTimer = setTimeout(() => {
				if (active.value?.name === name && !others.value.length) {
					toast.create({ message: "No answer", type: "info" });
					leave();
				}
			}, RING_MS);
		}
	}

	async function join(c, callType) {
		if (busy.value) return;
		if (active.value?.name === c.name) return (expanded.value = true);
		if (active.value) await leave();
		stopRinging();
		incoming.value = null;
		await enter(() => request(`${API}.join_call`, { call: c.name }), callType || c.call_type);
	}

	async function enter(joinRequest, callType) {
		busy.value = true;
		try {
			await getMedia(callType === "Video");
			const payload = await joinRequest();
			active.value = payload;
			activeCalls[payload.channel] = payload;
			startedAt.value = payload.started_at;
			expanded.value = callType === "Video";
			pingTimer = setInterval(ping, PING_MS);
			for (const user of payload.participants) {
				if (user !== session.user) connectTo(user);
			}
		} catch (error) {
			stopMedia();
			showError(error);
		} finally {
			busy.value = false;
		}
	}

	async function ping() {
		if (!active.value) return;
		const live = await request(`${API}.ping`, { call: active.value.name }).catch(() => null);
		if (!live) return;
		for (const user of Object.keys(peers)) if (!live.includes(user)) dropPeer(user);
	}

	function cleanup() {
		clearInterval(pingTimer);
		clearTimeout(noAnswerTimer);
		pingTimer = noAnswerTimer = null;
		for (const user of Object.keys(connections)) dropPeer(user);
		stopMedia();
		active.value = null;
	}

	function stopMedia() {
		for (const track of [audioTrack, cameraTrack, screenTrack]) track?.stop();
		audioTrack = cameraTrack = screenTrack = null;
		sharing.value = cameraOn.value = false;
		localVideo.value = null;
	}

	async function leave() {
		const current = active.value;
		cleanup();
		if (current) await request(`${API}.leave_call`, { call: current.name }).catch(() => {});
	}

	// closing the tab: tell the server without waiting for an answer
	function leaveOnUnload() {
		if (!active.value) return;
		fetch(`/api/method/${API}.leave_call`, {
			method: "POST",
			keepalive: true,
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": window.csrf_token,
			},
			body: JSON.stringify({ call: active.value.name }),
		});
	}

	async function decline() {
		const c = incoming.value;
		stopRinging();
		incoming.value = null;
		if (c && !c.quiet) await request(`${API}.decline_call`, { call: c.name }).catch(() => {});
	}

	// ---- controls ---------------------------------------------------------------

	function toggleMute() {
		if (!audioTrack) return;
		muted.value = !muted.value;
		audioTrack.enabled = !muted.value;
		broadcastState();
	}

	async function toggleCamera() {
		if (cameraOn.value) {
			cameraTrack?.stop();
			cameraTrack = null;
			cameraOn.value = false;
		} else {
			try {
				const stream = await navigator.mediaDevices.getUserMedia({ video: true });
				cameraTrack = stream.getVideoTracks()[0];
				cameraOn.value = true;
			} catch {
				return toast.create({ message: "Camera not available", type: "error" });
			}
		}
		updateSenders();
	}

	async function toggleShare() {
		if (sharing.value) return stopShare();
		try {
			const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
			screenTrack = stream.getVideoTracks()[0];
			screenTrack.onended = stopShare; // the browser's own "Stop sharing" button
			sharing.value = true;
			updateSenders();
		} catch {
			// picker closed
		}
	}

	function stopShare() {
		screenTrack?.stop();
		screenTrack = null;
		sharing.value = false;
		updateSenders();
	}

	// ---- ringing ----------------------------------------------------------------

	function startRinging() {
		stopRinging();
		try {
			const ctx = new AudioContext();
			const beep = () => {
				for (const [offset, freq] of [
					[0, 880],
					[0.25, 660],
				]) {
					const osc = ctx.createOscillator();
					const gain = ctx.createGain();
					osc.frequency.value = freq;
					gain.gain.setValueAtTime(0.08, ctx.currentTime + offset);
					gain.gain.exponentialRampToValueAtTime(
						0.0001,
						ctx.currentTime + offset + 0.22
					);
					osc.connect(gain).connect(ctx.destination);
					osc.start(ctx.currentTime + offset);
					osc.stop(ctx.currentTime + offset + 0.22);
				}
			};
			beep();
			ringtone = { ctx, timer: setInterval(beep, 2000) };
		} catch {
			ringtone = null;
		}
	}

	function stopRinging() {
		clearTimeout(ringTimer);
		if (ringtone) {
			clearInterval(ringtone.timer);
			ringtone.ctx.close();
			ringtone = null;
		}
	}

	function ring(c, quiet) {
		incoming.value = { ...c, quiet };
		if (!quiet) startRinging();
		if (
			!quiet &&
			document.visibilityState !== "visible" &&
			window.Notification?.permission === "granted"
		) {
			new Notification(`${c.started_by_name} is calling`, {
				body: c.channel_type === "Direct" ? `${c.call_type} call` : `in ${callTitle(c)}`,
				tag: `call-${c.name}`,
			});
		}
		clearTimeout(ringTimer);
		ringTimer = setTimeout(() => {
			if (incoming.value?.name === c.name) {
				stopRinging();
				incoming.value = null;
			}
		}, RING_MS);
	}

	// ---- server events ------------------------------------------------------------

	function onCallEvent({ action, call: c, ring: shouldRing, user, left }) {
		if (action === "end") {
			delete activeCalls[c.channel];
			if (incoming.value?.name === c.name) {
				stopRinging();
				incoming.value = null;
			}
			if (active.value?.name === c.name) cleanup();
			return;
		}
		activeCalls[c.channel] = c;
		if (active.value?.name === c.name) {
			active.value = { ...active.value, participants: c.participants };
			if (left) dropPeer(left);
			if (action === "declined" && c.channel_type === "Direct") {
				toast.create({
					message: `${chat.person(user).full_name} declined the call`,
					type: "info",
				});
				leave();
			}
			return;
		}
		if (action === "start" && c.started_by !== session.user && !active.value) {
			ring(c, !shouldRing);
		}
		// answered in another tab
		if (incoming.value?.name === c.name && c.participants.includes(session.user)) {
			stopRinging();
			incoming.value = null;
		}
	}

	async function loadActive(channel) {
		const c = await request(`${API}.get_active_call`, { channel }).catch(() => null);
		if (c) activeCalls[channel] = c;
		else delete activeCalls[channel];
	}

	function init() {
		if (initialized) return;
		initialized = true;
		const socket = useSocket();
		socket?.on("as_call", onCallEvent);
		socket?.on("as_call_signal", onSignal);
		window.addEventListener("pagehide", leaveOnUnload);
	}

	return {
		active,
		incoming,
		activeCalls,
		peers,
		others,
		inCall,
		muted,
		cameraOn,
		sharing,
		expanded,
		busy,
		localVideo,
		startedAt,
		callTitle,
		init,
		start,
		join,
		leave,
		decline,
		loadActive,
		toggleMute,
		toggleCamera,
		toggleShare,
	};
});
