// Offline Pi lifecycle tests; only an isolated fake Python hook is executed.
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const template = readFileSync(new URL("../scripts/herdr-pi-session-hook.js", import.meta.url), "utf8");

async function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), "herdr pi hook "));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const previousTerminal = process.env.HC_TERMINAL_ID;
  process.env.HC_TERMINAL_ID = "t-test";
  t.after(() => {
    if (previousTerminal === undefined) delete process.env.HC_TERMINAL_ID;
    else process.env.HC_TERMINAL_ID = previousTerminal;
  });
  const script = join(directory, "fake_hook.py");
  const log = join(directory, "calls.jsonl");
  const response = join(directory, "response.json");
  writeFileSync(log, "");
  writeFileSync(script, `import json, sys
from pathlib import Path
root = Path(__file__).parent
assert sys.argv[1:] == ["hook", "pi"]
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(json.load(sys.stdin)) + "\\n")
response = json.loads((root / "response.json").read_text())
print(response["outcome"])
raise SystemExit(response["status"])
`);
  const reply = (outcome, status = 0) => writeFileSync(response, JSON.stringify({ outcome, status }));
  reply("saved");
  const source = template.replace("__SCRIPT__", JSON.stringify(script));
  const { default: extension } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
  const handlers = new Map();
  const pi = { on: (name, handler) => handlers.set(name, handler) };
  extension(pi);
  const state = { file: join(directory, "session.jsonl"), id: "session-test-0001", cwd: directory };
  const ctx = {
    cwd: directory,
    mode: "tui",
    sessionManager: {
      getSessionFile: () => state.file,
      getSessionId: () => state.id,
      getCwd: () => state.cwd,
    },
  };
  return {
    state, ctx, handlers, extension, reply,
    persist: () => writeFileSync(state.file, '{"type":"session"}\n'),
    emit: (name) => {
      assert.ok(handlers.has(name), `Missing ${name} handler`);
      handlers.get(name)({}, ctx);
    },
    calls: () => readFileSync(log, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse),
  };
}

test("does not label a candidate path before Pi persists its first message", async (t) => {
  const f = await fixture(t);
  f.emit("session_start");
  assert.deepEqual(f.calls(), []);
  f.persist();
  f.emit("before_provider_request");
  f.emit("agent_end");
  assert.equal(f.calls().length, 1);
});

test("records an existing session at startup, with its actual file and cwd", async (t) => {
  const f = await fixture(t);
  f.persist();
  f.emit("session_start");
  assert.deepEqual(f.calls(), [{
    hook_event_name: "SessionStart",
    session_id: f.state.id,
    transcript_path: f.state.file,
    cwd: f.state.cwd,
  }]);
  f.emit("agent_end");
  assert.equal(f.calls().length, 1);
});

test("does not cache unsuccessful hook outcomes, despite a zero exit code", async (t) => {
  const f = await fixture(t);
  f.persist();
  for (const outcome of ["agent process not found", "terminal not live", "error: hc get timed out", ""]) {
    f.reply(outcome);
    f.emit("agent_end");
  }
  assert.equal(f.calls().length, 4);
  f.reply("saved");
  f.emit("agent_end");
  f.emit("agent_end");
  assert.equal(f.calls().length, 5);
});

test("does not cache a failed subprocess", async (t) => {
  const f = await fixture(t);
  f.persist();
  f.reply("saved", 1);
  f.emit("session_start");
  f.reply("saved");
  f.emit("agent_end");
  assert.equal(f.calls().length, 2);
});

test("accepts already noted as a successful acknowledgement", async (t) => {
  const f = await fixture(t);
  f.persist();
  f.reply("already noted");
  f.emit("session_start");
  f.emit("agent_end");
  assert.equal(f.calls().length, 1);
});

test("records switched sessions but never an unpersisted or ephemeral one", async (t) => {
  const f = await fixture(t);
  f.persist();
  f.emit("session_start");
  f.state.id = "session-test-0002";
  f.state.file += ".new.jsonl";
  f.emit("session_start");
  assert.equal(f.calls().length, 1);
  f.persist();
  f.emit("agent_end");
  assert.equal(f.calls()[1].session_id, f.state.id);
  f.state.file = undefined;
  f.emit("session_start");
  f.emit("agent_end");
  assert.equal(f.calls().length, 2);
});

test("successful acknowledgements are scoped to each extension runtime", async (t) => {
  const f = await fixture(t);
  f.persist();
  f.emit("session_start");
  f.extension({ on: (name, handler) => f.handlers.set(name, handler) });
  f.emit("session_start");
  assert.equal(f.calls().length, 2);
});

test("does nothing outside Herdr", async (t) => {
  const f = await fixture(t);
  f.persist();
  delete process.env.HC_TERMINAL_ID;
  f.emit("session_start");
  f.emit("agent_end");
  assert.deepEqual(f.calls(), []);
});
