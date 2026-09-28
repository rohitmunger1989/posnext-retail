const scanSuccessAudio =
	typeof Audio !== "undefined"
		? new Audio(`${import.meta.env.BASE_URL}sounds/scan-success.ogg`)
		: null;

const scanErrorAudio =
	typeof Audio !== "undefined"
		? new Audio(`${import.meta.env.BASE_URL}sounds/scan-error.ogg`)
		: null;

if (scanSuccessAudio) scanSuccessAudio.preload = "auto";
if (scanErrorAudio) scanErrorAudio.preload = "auto";

function normalizedVolume(value, fallback) {
	const number = Number(value);
	const safe = Number.isFinite(number) ? number : fallback;
	return Math.min(1, Math.max(0, safe / 100));
}

function stopAudio(audio) {
	if (!audio) return;

	try {
		audio.pause();
		audio.currentTime = 0;
	} catch {
		// Audio feedback must never interrupt POS operation.
	}
}

export function playScanSuccess({
	enabled = true,
	soundEnabled = true,
	volume = 70,
} = {}) {
	if (!enabled || !soundEnabled || !scanSuccessAudio) return;

	try {
		stopAudio(scanErrorAudio);
		stopAudio(scanSuccessAudio);

		scanSuccessAudio.volume = normalizedVolume(volume, 70);
		scanSuccessAudio.play().catch(() => {});
	} catch {
		// Audio feedback must never interrupt POS operation.
	}
}

export function playScanError({
	enabled = true,
	soundEnabled = true,
	volume = 100,
} = {}) {
	if (!enabled || !soundEnabled || !scanErrorAudio) return;

	try {
		stopAudio(scanSuccessAudio);
		stopAudio(scanErrorAudio);

		scanErrorAudio.volume = normalizedVolume(volume, 100);
		scanErrorAudio.play().catch(() => {});
	} catch {
		// Audio feedback must never interrupt POS operation.
	}
}
