/** Positive-control adapter for the grader, never provided to the implementation sessions. */
import { createReadStream } from "node:fs";
import { link, unlink } from "node:fs/promises";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";
import { readRecording } from "/oracle/src/recording/reader.ts";
import { RecordingWriter } from "/oracle/src/recording/writer.ts";
import { decodeEventLine } from "/oracle/src/protocol/decode.ts";
import { main } from "/oracle/src/cli.ts";

const args = process.argv.slice(2);
const controller = new AbortController();
process.once("SIGINT", () => controller.abort());
process.once("SIGTERM", () => controller.abort());
function error(code: string, exit: number) {
  console.log(JSON.stringify({ protocolVersion: 2, status: "error", error: { code, message: "Recovery failed." } }));
  process.exitCode = exit;
}
if (args[0] === "presentation" && args[1] === "capabilities") {
  const child = Bun.spawn([process.execPath, "/oracle/src/cli.ts", ...args], { stdout: "pipe" });
  const response = await new Response(child.stdout).json() as any;
  response.recording.recover = true; console.log(JSON.stringify(response)); await child.exited;
} else if (args[0] === "presentation" && args[1] === "--help") {
  console.log("hamio presentation recover --input RECORDING --output RECORDING");
} else if (args[0] !== "presentation" || args[1] !== "recover") {
  process.exitCode = await main(args);
} else {
  let temporary: string | undefined; let writer: RecordingWriter | undefined;
  try {
    const options = new Map<string, string>();
    for (let index = 2; index < args.length; index += 2) {
      const key = args[index]!; const value = args[index + 1];
      if (!["--input", "--output"].includes(key) || options.has(key) || !value || value === "-" || value.startsWith("--")) throw { code: "INVALID_ARGUMENT" };
      options.set(key, value);
    }
    if (options.size !== 2) throw { code: "INVALID_ARGUMENT" };
    const input = options.get("--input")!; const output = options.get("--output")!;
    const replay = await readRecording(input, controller.signal);
    if (replay.kind === "invalid" && replay.line === 1) throw { code: replay.issue.code };
    temporary = join(dirname(output), `.recover-${randomUUID()}.tmp`);
    writer = await RecordingWriter.create(temporary);
    if (replay.eventCount) {
      const stream = createReadStream(input, { signal: controller.signal }); let rest = Buffer.alloc(0); let lines = 0;
      try {
        outer: for await (const chunk of stream) {
          let from = 0;
          for (let end = chunk.indexOf(10); end !== -1; end = chunk.indexOf(10, from)) {
            const part = chunk.subarray(from, end); const frame = rest.length ? Buffer.concat([rest, part]) : part;
            rest = Buffer.alloc(0); from = end + 1;
            if (lines++) await writer.append(decodeEventLine(frame));
            if (lines === replay.eventCount + 1) break outer;
          }
          const tail = chunk.subarray(from); if (tail.length) rest = rest.length ? Buffer.concat([rest, tail]) : Buffer.from(tail);
        }
      } finally { stream.destroy(); }
    }
    const status = replay.kind === "complete" ? "complete" : "partial";
    await writer.finish(status);
    if (controller.signal.aborted) throw { code: "INTERRUPTED" };
    await link(temporary, output);
    const state = replay.kind === "invalid" ? replay.acceptedPrefix : replay.state;
    const metadata = { recordingVersion: 1, eventCount: replay.eventCount, lastRecordedSeq: replay.lastSeq };
    console.log(JSON.stringify({ protocolVersion: 2, status: "ok", runId: state.run.kind === "none" ? null : state.run.value.id, runState: state.run.kind === "none" ? null : state.run.value.state.kind, sourceRecording: { ...metadata, status: replay.kind, ...(replay.kind === "invalid" ? { issue: { line: replay.line, code: replay.issue.code } } : {}) }, recording: { ...metadata, status } }));
  } catch (failure) {
    const code = (failure as any).code;
    if (controller.signal.aborted || code === "INTERRUPTED") error("INTERRUPTED", 130);
    else if (code === "EEXIST" || code === "INVALID_ARGUMENT") error("INVALID_ARGUMENT", 2);
    else if (["INVALID_JSON", "INVALID_SHAPE", "UNSUPPORTED_VERSION", "LIMIT_EXCEEDED"].includes(code)) error(code, 2);
    else error("IO_ERROR", 7);
  } finally {
    await writer?.abort();
    if (temporary) await unlink(temporary).catch(() => {});
  }
}
