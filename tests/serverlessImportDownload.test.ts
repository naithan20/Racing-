import { afterEach, describe, expect, it, vi } from "vitest";

import { DownloadTooLargeError, downloadKaggleDataset, downloadWithCap } from "@/lib/serverlessImport/download";

function streamResponse(chunks: Uint8Array[], init: { status?: number; headers?: Record<string, string> } = {}): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
  return new Response(stream, { status: init.status ?? 200, headers: init.headers });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("downloadWithCap", () => {
  it("returns the full buffer for a response under the cap", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([Buffer.from("hello "), Buffer.from("world")]));
    const result = await downloadWithCap("https://example.com/data.csv", undefined, 1024);
    expect(result.buffer.toString("utf-8")).toBe("hello world");
    expect(result.status).toBe(200);
  });

  it("rejects up front when Content-Length declares a size over the cap", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([Buffer.from("x")], { headers: { "content-length": "10000" } }));
    await expect(downloadWithCap("https://example.com/big.csv", undefined, 100)).rejects.toThrow(DownloadTooLargeError);
  });

  it("aborts mid-stream once the received bytes exceed the cap, even with no/lying Content-Length", async () => {
    const bigChunk = Buffer.alloc(200, "a");
    vi.stubGlobal("fetch", async () => streamResponse([bigChunk, bigChunk]));
    await expect(downloadWithCap("https://example.com/big.csv", undefined, 100)).rejects.toThrow(DownloadTooLargeError);
  });
});

describe("downloadKaggleDataset", () => {
  it("sends Basic Auth when KAGGLE_USERNAME/KAGGLE_KEY are set", async () => {
    vi.stubEnv("KAGGLE_USERNAME", "alice");
    vi.stubEnv("KAGGLE_KEY", "secret123");
    let seenAuth: string | null = null;
    vi.stubGlobal("fetch", async (_url: string, init?: RequestInit) => {
      seenAuth = (init?.headers as Record<string, string>)?.Authorization ?? null;
      return streamResponse([Buffer.from("PK")], { headers: { "content-type": "application/zip" } });
    });
    await downloadKaggleDataset("someowner/some-dataset");
    expect(seenAuth).toBe(`Basic ${Buffer.from("alice:secret123").toString("base64")}`);
  });

  it("throws KaggleAuthRequiredError on a 403 response", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([], { status: 403 }));
    await expect(downloadKaggleDataset("someowner/some-dataset")).rejects.toThrow(/Kaggle requires authentication/);
  });

  it("throws KaggleAuthRequiredError when Kaggle serves an HTML login page instead of data", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([Buffer.from("<html>login</html>")], { headers: { "content-type": "text/html" } }));
    await expect(downloadKaggleDataset("someowner/some-dataset")).rejects.toThrow(/Kaggle requires authentication/);
  });

  it("throws KaggleDatasetNotFoundError on a 404", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([], { status: 404 }));
    await expect(downloadKaggleDataset("someowner/nonexistent")).rejects.toThrow(/not found/);
  });

  it("succeeds for a clean 200 zip response", async () => {
    vi.stubGlobal("fetch", async () => streamResponse([Buffer.from("PK\x03\x04...")], { headers: { "content-type": "application/zip" } }));
    const result = await downloadKaggleDataset("someowner/some-dataset");
    expect(result.status).toBe(200);
  });
});
