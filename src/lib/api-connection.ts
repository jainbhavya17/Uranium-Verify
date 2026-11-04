// Direct origin is for public wake-up requests. Keep cookie-authenticated
// requests under the same-origin Vercel/Vite proxy (see VITE_API_BASE_URL).
const normalize = (value: string) => value.trim().replace(/\/+$/, "");
export const API_URL = normalize(import.meta.env.VITE_API_URL ?? "");
export const API_BASE_URL = normalize(import.meta.env.VITE_API_BASE_URL ?? "/api/v1");
export const apiUrl = (path: string) => `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;

const GATEWAY_ERRORS = new Set([502, 503, 504]);
const ATTEMPT_TIMEOUT = 10000;
const WARM_UP_TIMEOUT = 90000;
const listeners = new Set<() => void>();
const retrying = new Set<symbol>();
export const getConnectionWaiting = () => retrying.size > 0;
export function subscribeConnectionWaiting(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
function notify() {
  listeners.forEach((listener) => listener());
}

let warmRequest: Promise<void> | undefined;
let firstLoadWarmed = false;
function wakeBackend() {
  if (typeof window === "undefined" || warmRequest) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), WARM_UP_TIMEOUT);
  warmRequest = fetch(`${API_URL}/health`, {
    method: "GET",
    // This public request only triggers startup; its opaque response is ignored.
    // Preview origins need not read Render's response to initiate the request.
    mode: "no-cors",
    credentials: "omit",
    cache: "no-store",
    signal: controller.signal,
  })
    .then(() => undefined)
    .catch(() => undefined)
    .finally(() => {
      clearTimeout(timer);
      warmRequest = undefined;
    });
}

export function warmUp() {
  if (typeof window === "undefined" || firstLoadWarmed) return;
  firstLoadWarmed = true;
  wakeBackend();
}

function wait(delay: number, signal?: AbortSignal | null) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const cleanup = () => signal?.removeEventListener("abort", abort);
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, delay);
    const abort = () => {
      clearTimeout(timer);
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
  });
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  tries = 6,
  delay = 10000,
): Promise<Response> {
  if (!Number.isInteger(tries) || tries < 1 || !Number.isFinite(delay) || delay < 0)
    throw new RangeError("Invalid retry settings");
  const token = Symbol("session-request");
  try {
    for (let attempt = 0; attempt < tries; attempt++) {
      if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
      const controller = new AbortController();
      const abort = () => controller.abort();
      options.signal?.addEventListener("abort", abort, { once: true });
      const timer = setTimeout(abort, ATTEMPT_TIMEOUT);
      try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        // Never retry 401, 403, validation, rate-limit or other real API errors.
        if (!GATEWAY_ERRORS.has(response.status) || attempt === tries - 1) return response;
        await response.body?.cancel().catch(() => undefined);
      } catch (error) {
        if (options.signal?.aborted || attempt === tries - 1) throw error;
      } finally {
        clearTimeout(timer);
        options.signal?.removeEventListener("abort", abort);
      }
      if (!retrying.has(token)) {
        retrying.add(token);
        notify();
        // A user can return to an already-open tab after the backend goes idle.
        // Retry-triggered wake-up is per request, not a recurring keepalive.
        wakeBackend();
      }
      await wait(delay, options.signal);
    }
    throw new Error("Retry limit reached");
  } finally {
    if (retrying.delete(token)) notify();
  }
}
