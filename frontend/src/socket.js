import { initSocket } from "frappe-ui";

let socket = null;

export function initRealtime() {
	if (!socket) {
		socket = initSocket({ port: window.socketio_port });
	}
	return socket;
}

export function useSocket() {
	return socket;
}
