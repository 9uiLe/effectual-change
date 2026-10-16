import { expect, test } from "bun:test";
import { chmod, link, lstat, mkdir, mkdtemp, open, readFile, readdir, readlink, rm, stat, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readRecording } from "/oracle/src/recording/reader.ts";

// Trusted test code imports only the frozen reader; candidate code runs in child processes.
const target = process.env.HAMIO_RECOVER_ENTRY ?? "/candidate/src/cli.ts";
const command = (args: string[]) => process.env.HAMIO_TEST_BINARY ? [process.env.HAMIO_TEST_BINARY, ...args] : [process.execPath, "--no-env-file", "--no-install", target, ...args];
const header = { recordingVersion: 1, protocolVersion: 2, kind: "header" };
const line = (value: unknown) => `${JSON.stringify(value)}\n`;
const event = (seq: number, type: string, body: Record<string, unknown> = {}) => ({ protocolVersion: 2, runId: "recovery-trial", seq, type, ...body });
const start = event(0, "run.started", { title: "復旧対象 🧪" });
const succeeded = { kind: "succeeded", data: { kind: "none" } };
const finish = event(1, "run.finished", { result: succeeded });
const trailer = (status: string, count: number) => ({ recordingVersion: 1, kind: "trailer", status, eventCount: count, lastSeq: count ? count - 1 : null });
const recording = (events: unknown[], status?: string) => line(header) + events.map(line).join("") + (status ? line(trailer(status, events.length)) : "");
type Fixture = { name: string; input: string | Uint8Array; events: unknown[]; status?: "complete" | "partial" | "invalid"; headerError?: boolean };
const fixtures: Fixture[] = [
  { name: "complete successful Run", input: recording([start, finish], "complete"), events: [start, finish], status: "complete" },
  { name: "header only", input: line(header), events: [], status: "partial" },
  { name: "zero-event partial trailer", input: recording([], "partial"), events: [], status: "partial" },
  { name: "running Run without trailer", input: recording([start]), events: [start], status: "partial" },
  { name: "finished Run without trailer", input: recording([start, finish]), events: [start, finish], status: "partial" },
  { name: "finished Run explicitly partial", input: recording([start, finish], "partial"), events: [start, finish], status: "partial" },
  { name: "unfinished final Event", input: recording([start]) + JSON.stringify(finish), events: [start], status: "partial" },
  { name: "unfinished final trailer", input: recording([start, finish]) + JSON.stringify(trailer("complete", 2)), events: [start, finish], status: "partial" },
  { name: "incomplete UTF-8 tail", input: Buffer.concat([Buffer.from(recording([start])), Buffer.from([0xe3, 0x81])]), events: [start], status: "partial" },
  { name: "corruption before later valid Event", input: recording([start]) + 'NEVER_COPY_REJECTED_BYTES\n' + line(finish), events: [start], status: "invalid" },
  { name: "empty frame stops recovery", input: recording([start]) + "\n" + line(finish), events: [start], status: "invalid" },
  { name: "CRLF Event stops recovery", input: recording([start]) + JSON.stringify(finish) + "\r\n", events: [start], status: "invalid" },
  { name: "malformed UTF-8 frame", input: Buffer.concat([Buffer.from(recording([start])), Buffer.from([0xff, 10]), Buffer.from(line(finish))]), events: [start], status: "invalid" },
  { name: "sequence gap", input: recording([start, { ...finish, seq: 2 }]), events: [start], status: "invalid" },
  { name: "duplicate sequence", input: recording([start, { ...finish, seq: 0 }]), events: [start], status: "invalid" },
  { name: "foreign Run ownership", input: recording([start, { ...finish, runId: "other" }]), events: [start], status: "invalid" },
  { name: "unknown Event field", input: recording([start, { ...finish, raw: "NEVER_COPY_REJECTED_BYTES" }]), events: [start], status: "invalid" },
  { name: "unknown Event protocol", input: recording([start, { ...finish, protocolVersion: 3 }]), events: [start], status: "invalid" },
  { name: "invalid first transition after valid header", input: recording([finish]), events: [], status: "invalid" },
  { name: "second start rejected", input: recording([start, { ...start, seq: 1 }]), events: [start], status: "invalid" },
  { name: "Events after finished Run rejected", input: recording([start, finish, { ...start, seq: 2 }]), events: [start, finish], status: "invalid" },
  { name: "mismatched trailer count", input: recording([start, finish]) + line({ ...trailer("complete", 2), eventCount: 1 }), events: [start, finish], status: "invalid" },
  { name: "mismatched trailer seq", input: recording([start, finish]) + line({ ...trailer("complete", 2), lastSeq: 3 }), events: [start, finish], status: "invalid" },
  { name: "complete trailer for running Run", input: recording([start], "complete"), events: [start], status: "invalid" },
  { name: "duplicate trailer", input: recording([start, finish], "complete") + line(trailer("complete", 2)), events: [start, finish], status: "invalid" },
  { name: "byte after valid trailer", input: recording([start, finish], "complete") + "x", events: [start, finish], status: "invalid" },
  { name: "oversize Event frame", input: recording([start]) + JSON.stringify({ ...finish, padding: "x".repeat(65536) }) + "\n", events: [start], status: "invalid" },
  { name: "empty input", input: "", events: [], headerError: true },
  { name: "incomplete header", input: JSON.stringify(header), events: [], headerError: true },
  { name: "unknown recording version", input: line({ ...header, recordingVersion: 2 }), events: [], headerError: true },
  { name: "unknown header protocol", input: line({ ...header, protocolVersion: 3 }), events: [], headerError: true },
  { name: "unknown header field", input: line({ ...header, raw: "NEVER_COPY_REJECTED_BYTES" }), events: [], headerError: true },
  { name: "header CRLF", input: JSON.stringify(header) + "\r\n", events: [], headerError: true },
  { name: "invalid header JSON", input: "NEVER_COPY_REJECTED_BYTES\n", events: [], headerError: true },
];
for (const result of [{ kind: "failed", failure: { code: "BUILD_FAILED", message: "ビルド失敗", details: { kind: "none" } } }, { kind: "cancelled", reason: "利用側が停止" }]) {
  const end = event(1, "run.finished", { result });
  fixtures.push({ name: `complete ${result.kind} Run`, input: recording([start, end], "complete"), events: [start, end], status: "complete" });
}
const structuredEvents = [start, event(1, "task-group.declared", { groupId: "group", label: "Group" }), event(2, "task.declared", { taskId: "task", label: "Task", placement: { kind: "group", groupId: "group" } }), event(3, "task.started", { taskId: "task" }), event(4, "task.progressed", { taskId: "task", progress: { kind: "indeterminate" } }), event(5, "task.finished", { taskId: "task", result: succeeded }), event(6, "run.finished", { result: succeeded })];
fixtures.push({ name: "Task hierarchy and intermediate Event history", input: recording(structuredEvents, "complete"), events: structuredEvents, status: "complete" });

async function workspace<T>(body: (directory: string) => Promise<T>): Promise<T> {
  const directory = await mkdtemp(join(tmpdir(), "recover-grade-"));
  try { return await body(directory); } finally { await rm(directory, { recursive: true, force: true }); }
}
function launch(args: string[]) {
  return Bun.spawn(command(args), { cwd: "/candidate", stdin: "ignore", stdout: "pipe", stderr: "pipe", timeout: 30000 });
}
async function collect(child: ReturnType<typeof launch>) {
  const [code, stdout, stderr] = await Promise.all([child.exited, new Response(child.stdout).text(), new Response(child.stderr).text()]);
  expect(stdout.trim().split("\n").length).toBe(1);
  expect(stdout + stderr).not.toContain("NEVER_COPY_REJECTED_BYTES");
  return { code, response: JSON.parse(stdout), stderr };
}
const cli = (args: string[]) => collect(launch(args));
const recoverArgs = (input: string, output: string) => ["presentation", "recover", "--input", input, "--output", output];
async function absent(path: string) { expect(await lstat(path).then(() => false, () => true)).toBe(true); }
async function noTemps(directory: string, expected: string[]) { expect((await readdir(directory)).sort()).toEqual(expected.sort()); }
async function checkOutput(input: string, output: string, actual: Awaited<ReturnType<typeof cli>>, fixture: Fixture) {
  const oracle = await readRecording(input);
  expect(oracle.kind).toBe(fixture.headerError ? "invalid" : fixture.status!);
  if (fixture.headerError) {
    expect(actual.code).toBe(2);
    expect(actual.response.status).toBe("error");
    expect(actual.response.error.code).toBe((oracle as any).issue.code);
    await absent(output);
    return;
  }
  expect(oracle.eventCount).toBe(fixture.events.length);
  const expectedStatus = oracle.kind === "complete" ? "complete" : "partial";
  const prefix = oracle.kind === "invalid" ? oracle.acceptedPrefix : oracle.state;
  const metadata = { recordingVersion: 1, eventCount: oracle.eventCount, lastRecordedSeq: oracle.lastSeq };
  expect(actual.code).toBe(0);
  expect(actual.response).toMatchObject({ protocolVersion: 2, status: "ok", runId: prefix.run.kind === "none" ? null : prefix.run.value.id, runState: prefix.run.kind === "none" ? null : prefix.run.value.state.kind, sourceRecording: { ...metadata, status: oracle.kind }, recording: { ...metadata, status: expectedStatus } });
  if (oracle.kind === "invalid") expect(actual.response.sourceRecording.issue).toEqual({ line: oracle.line, code: oracle.issue.code });
  const raw = await readFile(output, "utf8");
  expect(raw.endsWith("\n")).toBe(true);
  const frames = raw.trimEnd().split("\n").map((value) => JSON.parse(value));
  expect(frames[0]).toEqual(header);
  expect(frames.slice(1, -1)).toEqual(fixture.events);
  expect(frames.at(-1)).toEqual(trailer(expectedStatus, fixture.events.length));
  expect(raw).not.toContain("NEVER_COPY_REJECTED_BYTES");
  expect((await stat(output)).mode & 0o777).toBe(0o600);
  const replay = await readRecording(output);
  expect(replay.kind).toBe(expectedStatus);
  expect((replay as any).state).toEqual(prefix);
}

for (const fixture of fixtures) test(`recover: ${fixture.name}`, () => workspace(async (directory) => {
  const input = join(directory, "input.ndjson"); const output = join(directory, "output.ndjson");
  await writeFile(input, fixture.input);
  const before = await readFile(input);
  await checkOutput(input, output, await cli(recoverArgs(input, output)), fixture);
  expect(await readFile(input)).toEqual(before);
  await noTemps(directory, fixture.headerError ? ["input.ndjson"] : ["input.ndjson", "output.ndjson"]);
}));

for (const flags of [[], ["--input", "a"], ["--output", "b"], ["--input", "-", "--output", "b"], ["--input", "a", "--output", "-"], ["--input", "a", "--input", "a", "--output", "b"], ["--input", "a", "--output", "b", "--output", "b"], ["--input", "a", "--output", "b", "--unknown"]]) test(`arguments: ${JSON.stringify(flags)}`, async () => {
  const actual = await cli(["presentation", "recover", ...flags]);
  expect(actual.code).toBe(2); expect(actual.response.error.code).toBe("INVALID_ARGUMENT");
});

for (const collision of ["same path", "existing file", "symlink", "dangling symlink", "hardlink", "directory"] as const) test(`nonclobber: ${collision}`, () => workspace(async (directory) => {
  const input = join(directory, "input"); let output = join(directory, "output");
  const content = recording([start, finish], "complete"); await writeFile(input, content);
  if (collision === "same path") output = input;
  if (collision === "existing file") await writeFile(output, "KEEP_EXISTING");
  if (collision === "symlink") await symlink(input, output);
  if (collision === "dangling symlink") await symlink(join(directory, "not-created"), output);
  if (collision === "hardlink") await link(input, output);
  if (collision === "directory") await mkdir(output);
  const before = await lstat(output); const names = await readdir(directory);
  const actual = await cli(recoverArgs(input, output));
  expect(actual.code).toBe(2); expect(actual.response.error.code).toBe("INVALID_ARGUMENT");
  expect(await readFile(input, "utf8")).toBe(content);
  expect((await lstat(output)).ino).toBe(before.ino);
  if (collision === "existing file") expect(await readFile(output, "utf8")).toBe("KEEP_EXISTING");
  await noTemps(directory, names);
}));

for (const failure of ["missing input", "unreadable input", "missing directory", "unwritable directory"]) test(`I/O: ${failure}`, () => workspace(async (directory) => {
  const input = join(directory, "input"); let output = join(directory, "output");
  if (failure !== "missing input") await writeFile(input, recording([start, finish], "complete"));
  if (failure === "unreadable input") await chmod(input, 0);
  if (failure === "missing directory") output = join(directory, "absent", "output");
  if (failure === "unwritable directory") { await mkdir(join(directory, "locked")); await chmod(join(directory, "locked"), 0o500); output = join(directory, "locked", "output"); }
  try { const actual = await cli(recoverArgs(input, output)); expect(actual.code).toBe(7); expect(actual.response.error.code).toBe("IO_ERROR"); await absent(output); }
  finally { if (failure === "unreadable input") await chmod(input, 0o600); if (failure === "unwritable directory") await chmod(join(directory, "locked"), 0o700); }
}));

test("interface: help and capabilities retain existing fields", async () => {
  const cap = await cli(["presentation", "capabilities"]);
  expect(cap.code).toBe(0); expect(cap.response).toMatchObject({ protocolVersion: 2, modes: ["static", "live"], recordingVersion: 1, recording: { live: true, report: "html", recover: true } });
  const child = launch(["presentation", "--help"]); const text = await new Response(child.stdout).text(); await new Response(child.stderr).text(); expect(await child.exited).toBe(0); expect(text).toContain("recover");
});

test("nonclobber: competing recoveries publish exactly one complete file", () => workspace(async (directory) => {
  const input = join(directory, "input"); const output = join(directory, "output"); const fixture = fixtures[0]!;
  await writeFile(input, fixture.input);
  const actual = await Promise.all([cli(recoverArgs(input, output)), cli(recoverArgs(input, output))]);
  expect(actual.map((value) => value.code).sort()).toEqual([0, 2]);
  await checkOutput(input, output, actual.find((value) => value.code === 0)!, fixture);
  await noTemps(directory, ["input", "output"]);
}));

async function largeInput(directory: string) {
  const input = join(directory, "input"); const events = structuredEvents.slice(0, 4);
  const file = await open(input, "wx");
  try {
    await file.write(line(header) + events.map(line).join(""));
    for (let index = 0; index < 20000; index++) {
      const progress = event(index + 4, "task.progressed", { taskId: "task", progress: { kind: "indeterminate" } }); events.push(progress);
      const encoded = JSON.stringify(progress); await file.write(encoded + " ".repeat(20479 - Buffer.byteLength(encoded)) + "\n");
    }
    events.push(event(20004, "task.finished", { taskId: "task", result: succeeded }), event(20005, "run.finished", { result: succeeded }));
    await file.write(events.slice(-2).map(line).join("") + line(trailer("complete", events.length)));
  } finally { await file.close(); }
  return { input, events };
}

test("lifetime: signal during regular-file streaming leaves no final or temporary output", () => workspace(async (directory) => {
  const { input } = await largeInput(directory); const output = join(directory, "output");
  const child = launch(recoverArgs(input, output));
  try {
    let opened = false;
    for (let attempt = 0; attempt < 500; attempt++) {
      const fds = await readdir(`/proc/${child.pid}/fd`).catch(() => []);
      const names = await Promise.all(fds.map((fd) => readlink(`/proc/${child.pid}/fd/${fd}`).catch(() => "")));
      if (names.includes(input)) { opened = true; break; }
      if (child.exitCode !== null) break;
      await Bun.sleep(10);
    }
    expect(opened).toBe(true); await absent(output);
    child.kill("SIGTERM"); const actual = await collect(child);
    expect(actual.code).toBe(130); expect(actual.response.error.code).toBe("INTERRUPTED");
    await absent(output); await noTemps(directory, ["input"]);
  } finally { child.kill(); }
}), 35000);

test("resources: 390 MiB valid input preserves intermediate Events without whole-file buffering", () => workspace(async (directory) => {
  const { input, events } = await largeInput(directory); const output = join(directory, "output");
  const before = (await stat(input)).size;
  await checkOutput(input, output, await cli(recoverArgs(input, output)), { name: "large", input: "", events, status: "complete" });
  expect((await stat(input)).size).toBe(before); expect((await stat(output)).size).toBeLessThan(10 * 1024 * 1024);
}), 60000);

test("compatibility: existing live and report agree with recovered Run state", () => workspace(async (directory) => {
  const input = join(directory, "input"); const output = join(directory, "output"); const report = join(directory, "report.html");
  await writeFile(input, recording([start, finish]));
  const recovered = await cli(recoverArgs(input, output)); expect(recovered.code).toBe(0);
  const result = await cli(["presentation", "report", "--input", output, "--output", report]);
  expect(result.code).toBe(0); expect(result.response).toMatchObject({ runState: "succeeded", recording: { status: "partial", eventCount: 2 } });
  expect(await readFile(report, "utf8")).toContain("Recording incomplete");
}));
