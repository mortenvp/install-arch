// Run against patched fixture sources (via test-github-tray.py) or an unpacked
// real patched v19 release: node testing/test-github-tray-done.mjs /path/to/extension
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import vm from "node:vm";

const directory = process.argv[2];
assert.ok(directory, "Pass the directory containing patched v19 sources");
function method(file, name, globals = {}) {
  const source = readFileSync(join(directory, file), "utf8");
  const match = source.match(new RegExp(`^  ((?:async )?${name}\\([\\s\\S]*?^  \\})`, "m"));
  assert.ok(match, `Missing complete method ${file}:${name}`);
  return vm.runInNewContext(`({${match[1]}}).${name}`, globals);
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const requests = [];
const Soup = {
  Status: { NO_CONTENT: 204 },
  Message: { new: (verb, url) => {
    const message = { verb, url, headers: {}, get_status: () => message.status,
      request_headers: { append: (key, value) => { message.headers[key] = value; } } };
    requests.push(message);
    return message;
  } },
};
const markNotificationDone = method("githubApi.js", "markNotificationDone", {
  Soup, GLib: { PRIORITY_DEFAULT: 0 },
});

for (const base of ["https://api.github.com", "https://github.example.test/api/v3"]) {
  test(`Done sends DELETE to the configured API: ${base}`, async () => {
    const cancellable = {};
    const api = { _apiUrl: base, _httpSession: {
      async send_and_read_async(message, priority, cancel) {
        assert.equal(priority, 0);
        assert.equal(cancel, cancellable);
        message.status = 204;
      },
    } };
    await markNotificationDone.call(api, "test-token", "123/456", cancellable);
    const request = requests.at(-1);
    assert.equal(request.verb, "DELETE");
    assert.equal(request.url, `${base}/notifications/threads/123%2F456`);
    assert.equal(request.headers.Authorization, "Bearer test-token");
    assert.equal(request.headers.Accept, "application/vnd.github+json");
  });
}
for (const status of [200, 205, 401, 403, 404, 500]) {
  test(`Done rejects HTTP ${status} instead of claiming success`, async () => {
    const api = { _apiUrl: "https://api.github.com", _httpSession: {
      async send_and_read_async(message) { message.status = status; },
    } };
    await assert.rejects(markNotificationDone.call(api, "test-token", "123"), new RegExp(`HTTP ${status}`));
  });
}

function managerEnvironment(token = "test-token") {
  const response = deferred();
  const refreshes = [], badges = [], errors = [], calls = [];
  class GitHubApi {
    async markNotificationDone(...args) { calls.push(args); await response.promise; }
  }
  const markDone = method("notificationManager.js", "markDone", {
    GitHubApi, isCancelled: (error) => error.cancelled === true,
    console: { error: (...args) => errors.push(args) },
  });
  const notification = { id: "123", unread: true };
  const remaining = { id: "456", unread: true };
  const manager = {
    _settings: { get_string: (key) => key === "github-token" ? token : "" },
    _cancellable: { is_cancelled: () => false },
    _notificationRevision: 0,
    _lastNotifications: [notification, remaining], _unreadCount: 2,
    _ui: { refreshNotifications: (items) => refreshes.push(items), updateBadge: (n) => badges.push(n) },
  };
  return { manager, notification, remaining, markDone, response, refreshes, badges, errors, calls };
}

test("local state changes only after GitHub confirms Done", async () => {
  const env = managerEnvironment();
  const outcomes = [];
  const pending = env.markDone.call(env.manager, env.notification, (ok) => outcomes.push(ok));
  assert.equal(env.manager._lastNotifications.length, 2);
  assert.equal(env.notification.unread, true);
  assert.deepEqual(env.refreshes, []);
  assert.deepEqual(outcomes, []);
  assert.equal(env.calls[0][1], "123");
  env.response.resolve();
  await pending;
  assert.deepEqual(Array.from(env.manager._lastNotifications), [env.remaining]);
  assert.equal(env.notification.unread, false);
  assert.equal(env.manager._notificationRevision, 1);
  assert.deepEqual(env.badges, [1]);
  assert.deepEqual(outcomes, [true]);
});

for (const cancelled of [false, true]) {
  test(`failed request preserves the notification (cancelled=${cancelled})`, async () => {
    const env = managerEnvironment();
    let outcome;
    const pending = env.markDone.call(env.manager, env.notification, (ok) => { outcome = ok; });
    env.response.reject(Object.assign(new Error("request failed"), { cancelled }));
    await pending;
    assert.equal(outcome, false);
    assert.equal(env.manager._lastNotifications.length, 2);
    assert.equal(env.notification.unread, true);
    assert.deepEqual(env.refreshes, []);
    assert.deepEqual(env.badges, []);
    assert.equal(env.errors.length, cancelled ? 0 : 1);
  });
}

test("missing authentication does not dismiss anything", async () => {
  const env = managerEnvironment("");
  let outcome;
  await env.markDone.call(env.manager, env.notification, (ok) => { outcome = ok; });
  assert.equal(outcome, false);
  assert.deepEqual(env.calls, []);
  assert.deepEqual(env.refreshes, []);
});

test("disable during an in-flight request does not touch destroyed UI", async () => {
  const env = managerEnvironment();
  const pending = env.markDone.call(env.manager, env.notification);
  env.manager._settings = null;
  env.response.resolve();
  await pending;
  assert.deepEqual(env.refreshes, []);
  assert.deepEqual(env.badges, []);
});

class Button {
  constructor(props = {}) { this.reactive = true; Object.assign(this, props); this.handlers = {}; }
  connect(signal, callback) { this.handlers[signal] = callback; }
  set_label(label) { this.label = label; }
  set_reactive(reactive) { this.reactive = reactive; }
  emit(signal) { this.handlers[signal]?.(); }
}
const createDoneButton = method("ui.js", "_createDoneButton", { St: { Button }, _: (s) => s });
test("Done disables duplicate clicks and offers retry on failure", () => {
  const row = new Button(), markRead = new Button();
  let callback, calls = 0;
  const ui = { _onMarkNotificationDone: (_notification, cb) => { calls++; callback = cb; } };
  const button = createDoneButton.call(ui, { id: "123" }, row, markRead);
  assert.equal(button.label, "Done");
  button.emit("clicked"); button.emit("clicked");
  assert.equal(calls, 1);
  assert.equal(button.label, "Saving...");
  assert.equal(markRead.reactive, false);
  callback(false);
  assert.equal(button.label, "Retry Done");
  assert.equal(button.reactive, true);
  assert.equal(markRead.reactive, true);
  button.emit("clicked");
  assert.equal(calls, 2);
  row.emit("destroy");
  button.set_label = button.set_reactive = () => { throw new Error("Destroyed actor accessed"); };
  callback(true);
});

test("notification refresh rebuilds counts and empty state only in the main view", () => {
  const refresh = method("ui.js", "refreshNotifications");
  const calls = [];
  const ui = { _currentView: "repos", _cachedRepos: [], _cachedUsername: "test-user",
    _cachedUserInfo: {}, updateMenu: (...args) => calls.push(args) };
  const notifications = [];
  refresh.call(ui, notifications);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][3], notifications);
  ui._currentView = "issues";
  refresh.call(ui, notifications);
  assert.equal(calls.length, 1);
  assert.equal(ui._cachedNotifications, notifications);
});
