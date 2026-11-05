// herdr-agent-resume pi session hook
// Local compatibility template; the upstream installer substitutes the script path.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

const script = __SCRIPT__;

export default function (pi) {
  let noted = "";

  function note(_event, ctx) {
    if (!process.env.HC_TERMINAL_ID) return;
    let file = "";
    let id = "";
    let cwd = "";
    try {
      file = ctx.sessionManager.getSessionFile() || "";
      id = ctx.sessionManager.getSessionId() || "";
      cwd = ctx.sessionManager.getCwd() || ctx.cwd || "";
    } catch {
      return;
    }
    // Pi allocates the path before it writes the first conversation message.
    // Never replace a recoverable label with a session that exists only in memory.
    if (!file || !id || !existsSync(file)) return;
    const key = id + "\0" + file;
    if (key === noted) return;
    let result;
    try {
      result = spawnSync("python3", [script, "hook", "pi"], {
        input: JSON.stringify({
          hook_event_name: "SessionStart",
          session_id: id,
          transcript_path: file,
          cwd,
        }),
        timeout: 8000,
        encoding: "utf8",
      });
    } catch {
      return;
    }
    // The Python hook also exits zero for ignored events and transient failures.
    const outcome = String(result?.stdout || "").trim();
    if (result?.status === 0 && (outcome === "saved" || outcome === "already noted")) noted = key;
  }

  pi.on("session_start", note);
  // By the first provider request, Pi has persisted the user message. Recording
  // here also covers a reboot during the first long-running agent turn.
  pi.on("before_provider_request", note);
  pi.on("agent_end", note);
}
