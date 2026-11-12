import { ref } from "vue";

// one shared clock that ticks every second, for live durations
export const now = ref(Date.now());
setInterval(() => (now.value = Date.now()), 1000);
