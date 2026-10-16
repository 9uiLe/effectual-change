import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const hook = "/candidate/hooks/scope-guard.mjs";
const { decideScopeGuard } = await import(pathToFileURL(hook).href);
const cases = [];
function check(name, run) {
  try {
    run();
    cases.push({ name, passed: true });
  } catch (error) {
    cases.push({ name, passed: false, error: String(error.message).slice(0, 500) });
  }
}
function fixture(globs = ["src/**/allowed.ts"]) {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "scope-eval-"));
  const baseline = path.join(data, "scope-baseline-eval.json");
  fs.writeFileSync(baseline, JSON.stringify({ manifestId: "m", globs, contractHash: "h" }));
  return {
    baseline,
    env: { MODEL_STRATEGY_MODE: "conductor", CLAUDE_PLUGIN_DATA: data },
    input: (file = "src/notallowed.ts") => ({
      session_id: "eval", tool_name: "Edit", tool_input: { file_path: file }
    }),
    close: () => fs.rmSync(data, { recursive: true, force: true })
  };
}
function isolated(name, run, globs) {
  check(name, () => {
    const f = fixture(globs);
    try { run(f); } finally { f.close(); }
  });
}

const paths = [
  ["src/**/allowed.ts", "src/allowed.ts", false],
  ["src/**/allowed.ts", "src/one/allowed.ts", false],
  ["src/**/allowed.ts", "src/one/two/allowed.ts", false],
  ["src/**/allowed.ts", "src/notallowed.ts", true],
  ["src/**/allowed.ts", "src/one/notallowed.ts", true],
  ["src/**/allowed.ts", "src/allowed.ts.bak", true],
  ["src/**/allowed.ts", "outside/allowed.ts", true],
  ["**/allowed.ts", "allowed.ts", false],
  ["**/allowed.ts", "one/allowed.ts", false],
  ["**/allowed.ts", "notallowed.ts", true],
  ["src/**", "src/one/notallowed.ts", false],
  ["src/*.ts", "src/one/allowed.ts", true],
  ["src/*.ts", "src/anything.ts", false],
  ["src/**/a+b[1].ts", "src/one/a+b[1].ts", false],
  ["src/**/a+b[1].ts", "src/one/ab1.ts", true]
];
for (const [glob, file, warn] of paths) {
  for (const absolute of [false, true]) {
    isolated(`${glob} | ${absolute ? "absolute" : "relative"} ${file}`, (f) => {
      const decision = decideScopeGuard(f.input(absolute ? path.resolve(file) : file), f.env);
      assert.equal(decision !== null, warn);
      if (warn) assert.match(decision.message, /SCOPE_EXPANSION/);
    }, [glob]);
  }
}
isolated("glob union allows second pattern", (f) => {
  assert.equal(decideScopeGuard(f.input("docs/index.md"), f.env), null);
}, ["src/**/allowed.ts", "docs/*.md"]);
isolated("opt-in remains required", (f) => {
  assert.equal(decideScopeGuard(f.input(), { CLAUDE_PLUGIN_DATA: f.env.CLAUDE_PLUGIN_DATA }), null);
});
isolated("missing baseline stays inactive", (f) => {
  fs.unlinkSync(f.baseline);
  assert.equal(decideScopeGuard(f.input(), f.env), null);
});
isolated("malformed baseline stays inactive", (f) => {
  fs.writeFileSync(f.baseline, "{");
  assert.equal(decideScopeGuard(f.input(), f.env), null);
});
isolated("invalid globs baseline stays inactive", (f) => {
  fs.writeFileSync(f.baseline, JSON.stringify({ globs: null }));
  assert.equal(decideScopeGuard(f.input(), f.env), null);
});
isolated("missing session stays inactive", (f) => {
  assert.equal(decideScopeGuard({ ...f.input(), session_id: undefined }, f.env), null);
});
isolated("missing path stays inactive", (f) => {
  assert.equal(decideScopeGuard({ ...f.input(), tool_input: {} }, f.env), null);
});
isolated("deduplication is per session and path", (f) => {
  assert.ok(decideScopeGuard(f.input(), f.env));
  assert.equal(decideScopeGuard(f.input(), f.env), null);
  assert.ok(decideScopeGuard(f.input("outside/other.ts"), f.env));
});
isolated("agent_id does not bypass warning", (f) => {
  assert.ok(decideScopeGuard({ ...f.input(), agent_id: "worker" }, f.env));
});
isolated("NotebookEdit still warns", (f) => {
  const input = { session_id: "eval", tool_name: "NotebookEdit", tool_input: { notebook_path: "src/notallowed.ts" } };
  assert.ok(decideScopeGuard(input, f.env));
});

function cli(input, env) {
  const result = spawnSync(process.execPath, [hook], {
    input, encoding: "utf8", timeout: 5000,
    env: { PATH: process.env.PATH, HOME: "/tmp", ...env }
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0);
  assert.equal(result.stderr, "");
  return result.stdout;
}
isolated("CLI allows zero and multiple directory levels", (f) => {
  assert.equal(cli(JSON.stringify(f.input("src/allowed.ts")), f.env), "");
  assert.equal(cli(JSON.stringify(f.input("src/one/two/allowed.ts")), f.env), "");
});
isolated("CLI warns then suppresses the same path", (f) => {
  const output = JSON.parse(cli(JSON.stringify(f.input()), f.env));
  assert.equal(output.hookSpecificOutput.hookEventName, "PreToolUse");
  assert.match(output.hookSpecificOutput.additionalContext, /SCOPE_EXPANSION/);
  assert.equal(cli(JSON.stringify(f.input()), f.env), "");
});
isolated("CLI malformed input remains fail-open", (f) => {
  assert.equal(cli("{", f.env), "");
});
console.log(JSON.stringify({ passed: cases.filter((c) => c.passed).length, total: cases.length, cases }));
process.exitCode = cases.every((c) => c.passed) ? 0 : 1;
