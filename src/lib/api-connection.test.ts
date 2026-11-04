import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("bounded session connection retries", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  async function setup() {
    vi.resetModules();
    vi.stubEnv("VITE_API_URL", "https://synthetic.onrender.com///");
    vi.stubEnv("VITE_API_BASE_URL", "/api/v1/");
    const requests: { url: string; method: string }[] = [];
    const queue: (number | Error)[] = [];
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/health")) return { status: 200 } as Response;
      requests.push({ url, method: options?.method ?? "GET" });
      const result = queue.shift() ?? 200;
      if (result instanceof Error) throw result;
      return { status: result, ok: result < 400 } as Response;
    });
    vi.stubGlobal("fetch", fetcher);
    return { connection: await import("./api-connection"), requests, queue, fetcher };
  }

  it("normalizes URLs and fires only one non-blocking initial warm-up without cookies", async () => {
    const { connection, fetcher } = await setup();
    expect(connection.apiUrl("/auth/session")).toBe("/api/v1/auth/session");
    connection.warmUp();
    connection.warmUp();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      "https://synthetic.onrender.com/health",
      expect.objectContaining({ credentials: "omit", cache: "no-store", mode: "no-cors" }),
    );
    await vi.advanceTimersByTimeAsync(0);
  });

  it("allows a direct warm-up to continue beyond the session-attempt timeout", async () => {
    const { connection, fetcher } = await setup();
    let signal: AbortSignal | null | undefined;
    fetcher.mockImplementation((_url, options) => {
      signal = options?.signal;
      return new Promise((_resolve, reject) => {
        signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    connection.warmUp();
    await vi.advanceTimersByTimeAsync(10000);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(80000);
    expect(signal?.aborted).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("waits ten seconds and retries a gateway error, then clears the waiting state", async () => {
    const { connection, requests, queue } = await setup();
    queue.push(502, 200);
    const task = connection.fetchWithRetry("/api/v1/me");
    await vi.advanceTimersByTimeAsync(0);
    expect(connection.getConnectionWaiting()).toBe(true);
    await vi.advanceTimersByTimeAsync(9999);
    expect(requests).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect((await task).status).toBe(200);
    expect(requests).toHaveLength(2);
    expect(connection.getConnectionWaiting()).toBe(false);
  });

  it.each([401, 403, 404, 422, 429, 500])("does not retry real HTTP status %i", async (status) => {
    const { connection, requests, queue } = await setup();
    queue.push(status);
    expect(
      (await connection.fetchWithRetry("/api/v1/auth/session", { method: "POST", body: "{}" }))
        .status,
    ).toBe(status);
    expect(requests).toHaveLength(1);
    expect(connection.getConnectionWaiting()).toBe(false);
  });

  it("retries network failures and preserves the session POST method", async () => {
    const { connection, queue, requests } = await setup();
    queue.push(new TypeError("network unavailable"), 504, 200);
    const task = connection.fetchWithRetry("/api/v1/auth/session", { method: "POST", body: "{}" });
    await vi.advanceTimersByTimeAsync(20000);
    expect((await task).status).toBe(200);
    expect(requests.map((x) => x.method)).toEqual(["POST", "POST", "POST"]);
  });

  it("stops after six unsuccessful attempts", async () => {
    const { connection, queue, requests } = await setup();
    queue.push(503, 503, 503, 503, 503, 503, 200);
    const task = connection.fetchWithRetry("/api/v1/me");
    await vi.advanceTimersByTimeAsync(50000);
    expect((await task).status).toBe(503);
    expect(requests).toHaveLength(6);
    expect(connection.getConnectionWaiting()).toBe(false);
  });

  it("cancels the retry wait when the caller aborts", async () => {
    const { connection, queue, requests } = await setup();
    queue.push(502, 200);
    const controller = new AbortController();
    const task = connection.fetchWithRetry("/api/v1/me", { signal: controller.signal });
    const rejection = expect(task).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await rejection;
    await vi.advanceTimersByTimeAsync(60000);
    expect(requests).toHaveLength(1);
    expect(connection.getConnectionWaiting()).toBe(false);
  });

  it("bounds an individual stalled fetch and retries it", async () => {
    const { connection, fetcher } = await setup();
    let attempts = 0;
    fetcher.mockImplementation((url, options) => {
      if (url.endsWith("/health") || attempts++ > 0)
        return Promise.resolve({ status: 200 } as Response);
      return new Promise((_resolve, reject) =>
        options?.signal?.addEventListener("abort", () =>
          reject(new DOMException("timeout", "AbortError")),
        ),
      );
    });
    const task = connection.fetchWithRetry("/api/v1/me");
    await vi.advanceTimersByTimeAsync(20000);
    expect((await task).status).toBe(200);
    expect(attempts).toBe(2);
  });

  it("does not retry non-session application mutations", async () => {
    const { queue, requests } = await setup();
    queue.push(502);
    const fetcher = vi.mocked(globalThis.fetch);
    fetcher.mockResolvedValue({
      status: 502,
      ok: false,
      json: async () => {
        throw new Error("HTML gateway page");
      },
    } as unknown as Response);
    const { api } = await import("@/features/api");
    await expect(
      api("/applications/case/submit", { method: "POST", body: "{}" }),
    ).rejects.toMatchObject({ status: 502 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
