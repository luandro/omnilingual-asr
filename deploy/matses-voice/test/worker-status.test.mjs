// Tests for the Worker's /status response shaping: stage fields pass through,
// delayTime is forwarded only when it is a finite nonnegative number, terminal
// and COMPLETED mappings stay unchanged. Runpod responses are stubbed by
// replacing global fetch; no network, D1 or R2 needed.
import test from "node:test";
import assert from "node:assert/strict";
import worker from "../worker/src/worker.js";

const MODEL = "omniASR_LLM_7B_v2";

async function statusCall(upstreamBody, upstreamStatus = 200) {
  const realFetch = globalThis.fetch;
  // Raw JSON strings are passed through so tests can express values that
  // JSON.stringify would flatten (e.g. 1e999 parses to Infinity).
  const payload = typeof upstreamBody === "string" ? upstreamBody : JSON.stringify(upstreamBody);
  globalThis.fetch = async () =>
    new Response(payload, {
      status: upstreamStatus,
      headers: { "Content-Type": "application/json" },
    });
  try {
    const request = new Request("https://matses-asr-proxy.test/status/mcf/abcdef12-3456", {
      headers: { Origin: "https://matses-voz.surge.sh" },
    });
    const env = { RUNPOD_API_KEY: "test-key" };
    const res = await worker.fetch(request, env);
    return { httpStatus: res.status, body: await res.json() };
  } finally {
    globalThis.fetch = realFetch;
  }
}

test("IN_QUEUE passes through with delayTime", async () => {
  const { body } = await statusCall({ status: "IN_QUEUE", delayTime: 1234 });
  assert.equal(body.status, "IN_QUEUE");
  assert.equal(body.delayTime, 1234);
});

test("missing delayTime is omitted, not defaulted", async () => {
  const { body } = await statusCall({ status: "IN_QUEUE" });
  assert.equal(body.status, "IN_QUEUE");
  assert.equal("delayTime" in body, false);
});

test("zero delayTime is preserved", async () => {
  const { body } = await statusCall({ status: "IN_PROGRESS", delayTime: 0 });
  assert.equal(body.delayTime, 0);
});

test("negative delayTime is dropped", async () => {
  const { body } = await statusCall({ status: "IN_PROGRESS", delayTime: -5 });
  assert.equal("delayTime" in body, false);
});

test("non-number delayTime values are dropped", async () => {
  // NaN/Infinity are omitted here: JSON.stringify flattens them to null, which
  // would duplicate the null case; nonfinite JSON is covered by the test below.
  for (const bad of ["1200", null, undefined, {}]) {
    const { body } = await statusCall({ status: "IN_PROGRESS", delayTime: bad });
    assert.equal("delayTime" in body, false, "expected no delayTime for " + String(bad));
  }
});

test("nonfinite delayTime arriving as JSON text is dropped", async () => {
  // JSON.parse("1e999") yields Infinity — the realistic way a nonfinite value
  // can survive transport (JSON text itself cannot express NaN).
  const { body } = await statusCall('{"status":"IN_PROGRESS","delayTime":1e999}');
  assert.equal(body.status, "IN_PROGRESS");
  assert.equal("delayTime" in body, false);
});

test("COMPLETED maps to status + text after model check", async () => {
  const { body } = await statusCall({
    status: "COMPLETED",
    output: { model: MODEL, text: "hello" },
  });
  assert.deepEqual(body, { status: "COMPLETED", text: "hello" });
});

test("COMPLETED with wrong model identity becomes FAILED", async () => {
  const { body } = await statusCall({
    status: "COMPLETED",
    output: { model: "some_other_model", text: "hello" },
  });
  assert.equal(body.status, "FAILED");
  assert.equal(body.error, "Model identity mismatch");
});

test("terminal status keeps its error", async () => {
  const { body } = await statusCall({ status: "FAILED", error: "boom" });
  assert.deepEqual(body, { status: "FAILED", error: "boom" });
});

test("terminal status without error uses the status as message", async () => {
  for (const status of ["CANCELLED", "TIMED_OUT"]) {
    const { body } = await statusCall({ status });
    assert.deepEqual(body, { status, error: status });
  }
});

test("upstream non-OK becomes 502", async () => {
  const { httpStatus, body } = await statusCall({}, 500);
  assert.equal(httpStatus, 502);
  assert.equal(body.error, "Upstream error 500");
});
