const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { webcrypto, createHash } = require("node:crypto");
const { runInNewContext } = require("node:vm");

const source = readFileSync("auth_component/index.html", "utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const defaults = {
  storage_key: "test-login", ttl_seconds: 600,
  authorize_url: "https://accounts.spotify.com/authorize?client_id=test",
};

function frame(storage = new Map(), blocked = false) {
  const messages = [];
  let listener;
  const content = { replaceChildren() {} };
  const parent = { postMessage(message) { messages.push(message); } };
  const origin = "http://127.0.0.1:8501";
  const sessionStorage = {
    getItem(key) { if (blocked) throw Error("blocked"); return storage.get(key) ?? null; },
    setItem(key, value) { storage.set(key, value); },
    removeItem(key) { storage.delete(key); },
  };
  runInNewContext(source, {
    document: { getElementById() { return content; }, createElement() { return {}; } },
    window: { parent, location: { origin }, addEventListener(_, fn) { listener = fn; } },
    sessionStorage, crypto: webcrypto, TextEncoder, URL, Date, Uint8Array,
    btoa: value => Buffer.from(value, "binary").toString("base64"),
  });
  return {
    messages, storage,
    async render(args, sender = parent, from = origin) {
      listener({ source: sender, origin: from, data: { type: "streamlit:render", args: { ...defaults, ...args } } });
      await new Promise(resolve => setTimeout(resolve, 25));
    },
    lastValue() { return messages.filter(m => m.type === "streamlit:setComponentValue").at(-1)?.value; },
  };
}

test("login prepares S256 state once, without browser tokens", async () => {
  const browser = frame();
  await browser.render({ action: "login" });
  const pending = JSON.parse(browser.storage.get("test-login"));
  const result = browser.lastValue();
  const url = new URL(result.authorize_url);
  assert.equal(result.status, "login_ready");
  assert.match(pending.state, /^[A-Za-z0-9_-]{43}$/);
  assert.match(pending.verifier, /^[A-Za-z0-9_-]{86}$/);
  assert.equal(url.searchParams.get("state"), pending.state);
  assert.equal(url.searchParams.get("code_challenge"),
    createHash("sha256").update(pending.verifier).digest("base64url"));
  assert.equal(url.searchParams.get("code_challenge_method"), "S256");
  assert.deepEqual(Object.keys(pending).sort(), ["created_at", "state", "verifier"]);
  const count = browser.messages.filter(m => m.type === "streamlit:setComponentValue").length;
  await browser.render({ action: "login" });
  assert.equal(browser.messages.filter(m => m.type === "streamlit:setComponentValue").length, count);
});

test("same-tab redirect consumes once, rerenders work, replay in a new frame fails", async () => {
  const storage = new Map();
  const login = frame(storage);
  await login.render({ action: "login" });
  const pending = JSON.parse(storage.get("test-login"));
  const callback = frame(storage); // new WebSocket/iframe after redirect
  await callback.render({ action: "consume", callback_state: pending.state });
  assert.equal(callback.lastValue().pending.verifier, pending.verifier);
  assert.equal(storage.size, 0);
  await callback.render({ action: "consume", callback_state: pending.state });
  assert.equal(callback.lastValue().status, "ready");
  const replay = frame(storage);
  await replay.render({ action: "consume", callback_state: pending.state });
  assert.equal(replay.lastValue().status, "missing");
});

test("different tabs and unmatched callbacks never get another tab's verifier", async () => {
  const alice = frame(), bob = frame();
  await alice.render({ action: "login" });
  const pending = JSON.parse(alice.storage.get("test-login"));
  await bob.render({ action: "consume", callback_state: pending.state });
  assert.equal(bob.lastValue().pending, null);
  await alice.render({ action: "consume", callback_state: "foreign" });
  assert.equal(alice.lastValue().pending, null);
  assert.equal(alice.storage.size, 1);
});

test("expired pending login cannot be consumed", async () => {
  const storage = new Map([["test-login", JSON.stringify({
    state: "old", verifier: "old", created_at: Date.now() / 1000 - 601,
  })]]);
  const browser = frame(storage);
  await browser.render({ action: "consume", callback_state: "old" });
  assert.equal(browser.lastValue().status, "missing");
  assert.equal(storage.size, 0);
});

test("storage errors fail closed and logout deletes the pending handshake", async () => {
  const blocked = frame(new Map(), true);
  await blocked.render({ action: "login" });
  assert.equal(blocked.lastValue().status, "unavailable");
  assert.equal(blocked.lastValue().pending, null);
  const browser = frame();
  await browser.render({ action: "login" });
  await browser.render({ action: "clear" });
  assert.equal(browser.lastValue().status, "cleared");
  assert.equal(browser.storage.size, 0);
});

test("messages from other frames or origins are ignored", async () => {
  const browser = frame();
  await browser.render({ action: "login" }, {}, "https://evil.example");
  assert.equal(browser.storage.size, 0);
  assert.equal(browser.lastValue(), undefined);
});
