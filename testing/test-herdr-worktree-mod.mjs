import assert from "node:assert/strict";
import { execFile as execFileCallback, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import vm from "node:vm";
import test from "node:test";

const execFile = promisify(execFileCallback);
const root = fileURLToPath(new URL("../", import.meta.url));
const mods = join(root, "patches/herdr-worktrees/mods");
const gitEnv = { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1" };

function load(name, host = {}) {
  const source = readFileSync(join(mods, name, "main.js"), "utf8")
    .replace(/^import .+;\n/gm, "")
    .replace(/export default class (\w+) extends View/, "globalThis.Mod = class $1 extends View");
  const context = vm.createContext({ View: class {}, ...host });
  vm.runInContext(source, context);
  return context;
}

async function git(cwd, ...args) {
  const result = await execFile("git", args, { cwd, env: gitEnv });
  return result.stdout.trim();
}

async function repository(t, { separate = false } = {}) {
  const directory = mkdtempSync(join(tmpdir(), "herdr wt "));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const main = join(directory, "my project");
  mkdirSync(main);
  await git(main, "init", "--initial-branch=main", ...(separate ? ["--separate-git-dir", join(directory, "git metadata")] : []));
  await git(main, "config", "user.name", "Test");
  await git(main, "config", "user.email", "test@example.invalid");
  await git(main, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "initial");
  return { directory, main };
}

function worktreeHost() {
  const commands = [], actions = [];
  let props = { argv: ["test-agent"], tab: "new tab" };
  const context = load("wt-worktree", {
    props: () => props,
    run: (name, args) => actions.push({ name, args }),
    exec: async (command, args, options) => {
      assert.equal(command, "git");
      commands.push({ args, options });
      try {
        const { stdout, stderr } = await execFile(command, args, { cwd: options.cwd, env: gitEnv });
        return { code: 0, stdout, stderr };
      } catch (error) {
        return { code: error.code, stdout: error.stdout ?? "", stderr: error.stderr ?? "" };
      }
    },
  });
  return { context, commands, actions, setProps: value => { props = value; } };
}

test("branch and location rules match the actual WT functions", () => {
  const branches = ["feature/login", "fix/a.b", "_leading_", "...dots...", "---", "___", "é", "a//b", "a  b", "hello🙂world", "UPPER.case_1"];
  const main = "/tmp/a folder/my.repo";
  const script = `import __future__, ast, json, re, sys
from pathlib import Path
from types import SimpleNamespace
source = Path(sys.argv[1])
nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in ("branch_component", "suggested_worktree_path")]
ns = {"Path": Path, "re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec", flags=__future__.annotations.compiler_flag), ns)
branches, main = json.loads(sys.argv[2])
worktrees = [SimpleNamespace(path=Path(main), main=True)]
print(json.dumps([[ns["branch_component"](b), str(ns["suggested_worktree_path"](worktrees, b))] for b in branches]))`;
  const result = spawnSync("python3", ["-c", script, join(root, "bin/wt-ui"), JSON.stringify([branches, main])], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const context = load("wt-worktree");
  const actual = branches.map(branch => {
    context.branch = branch;
    context.main = main;
    return [vm.runInContext("slug(branch)", context), vm.runInContext("`${ROOT(main)}/${slug(branch)}`", context)];
  });
  assert.deepEqual(actual, JSON.parse(result.stdout));
});

for (const separate of [false, true]) {
  test(`uses WT's first registered checkout from a linked checkout (separate git dir: ${separate})`, async t => {
    const { directory, main } = await repository(t, { separate });
    const linked = join(directory, "elsewhere", "source");
    await git(main, "worktree", "add", "-b", "source", linked);
    mkdirSync(join(linked, "nested"));
    const host = worktreeHost();
    const repo = await host.context.repoOf(join(linked, "nested"), null);
    // Use exactly what WT reads. With --separate-git-dir, Git can report its
    // metadata folder as the first checkout; do not invent a different policy.
    const registeredMain = (await git(linked, "worktree", "list", "--porcelain", "-z")).split("\0")[0].slice(9);
    assert.equal(repo.main, registeredMain);
    assert.equal(repo.top, linked);
    assert.equal(repo.linked, true);
    const dialog = new host.context.Mod();
    Object.assign(dialog, { repo, text: "feature/login", on: null });
    assert.equal(await dialog.create(), "");
    const expected = `${registeredMain}.worktrees/feature-login`;
    assert.equal(await git(expected, "branch", "--show-current"), "feature/login");
    assert.equal(host.actions.length, 1);
    assert.equal(host.actions[0].name, "space.new");
    assert.equal(host.actions[0].args.folder, expected);
    assert.equal(host.actions[0].args.tab, "new tab");
    assert.equal(host.actions[0].args.machine, "");
    assert.deepEqual(host.actions[0].args.argv, ["test-agent"]);
    assert.equal(host.commands.find(c => c.args[0] === "worktree" && c.args[1] === "add").options.cwd, linked);
    // No move/remove, publication or stash operation is added by this mod.
    assert.ok(host.commands.every(c => !c.args.includes("remove") && !c.args.includes("move") && !c.args.includes("push") && !c.args.includes("stash")));
    assert.equal(dirname(expected), `${registeredMain}.worktrees`);
  });
}

test("an existing branch uses the same sibling location", async t => {
  const { main } = await repository(t);
  await git(main, "branch", "existing/topic");
  const host = worktreeHost();
  const dialog = new host.context.Mod();
  Object.assign(dialog, { repo: await host.context.repoOf(main, null), text: "existing/topic", on: null });
  assert.equal(await dialog.create(), "");
  assert.equal(await git(`${main}.worktrees/existing-topic`, "branch", "--show-current"), "existing/topic");
  assert.ok(!host.commands.find(c => c.args[1] === "add").args.includes("-b"));
});

test("a failed add never opens a space or overwrites the destination", async t => {
  const { main } = await repository(t);
  const destination = `${main}.worktrees/conflict`;
  mkdirSync(destination, { recursive: true });
  writeFileSync(join(destination, "keep.txt"), "untouched");
  const host = worktreeHost();
  const dialog = new host.context.Mod();
  Object.assign(dialog, { repo: await host.context.repoOf(main, null), text: "conflict", on: null });
  assert.notEqual(await dialog.create(), "");
  assert.equal(host.actions.length, 0);
  assert.equal(readFileSync(join(destination, "keep.txt"), "utf8"), "untouched");
});

test("remote git calls and space creation keep their machine", async () => {
  const calls = [], actions = [];
  const context = load("wt-worktree", {
    props: () => ({}),
    run: (name, args) => actions.push({ name, args }),
    exec: async (_command, args, options) => {
      calls.push({ args, options });
      const stdout = args[0] === "rev-parse" ? "/remote/repo.worktrees/current\n"
        : args[1] === "list" ? "worktree /remote/repo\0HEAD 123\0branch refs/heads/main\0\0" : "";
      return { code: args[0] === "show-ref" ? 1 : 0, stdout, stderr: "" };
    },
  });
  const dialog = new context.Mod();
  Object.assign(dialog, { repo: await context.repoOf("/remote/repo.worktrees/current", "remote"), text: "feature/new", on: "remote" });
  assert.equal(await dialog.create(), "");
  assert.ok(calls.every(c => c.options.on === "remote"));
  assert.equal(actions[0].args.machine, "remote");
  assert.equal(actions[0].args.folder, "/remote/repo.worktrees/feature-new");
});

test("space context menu opens the custom dialog with original props", () => {
  const overlays = [];
  const context = load("wt-menu", {
    props: () => ({ tab: "space", target: { id: "space-test" }, overlay: "menu-test" }),
    closeOverlay: id => assert.equal(id, "menu-test"),
    openOverlay: spec => overlays.push(spec),
  });
  const menu = new context.Mod();
  menu.git = "main";
  menu.choose(1);
  assert.equal(overlays[0].mod, "wt-worktree");
  assert.equal(overlays[0].props.space, "space-test");
  assert.equal(overlays[0].props.action, "new");
});

test("both menu entry points and their callers route through custom clones", () => {
  for (const [name, targets] of Object.entries({
    "wt-menu": ["wt-worktree"], "wt-new-menu": ["wt-worktree"],
    "wt-tabs": ["wt-menu", "wt-new-menu"], "wt-spaces": ["wt-menu"],
  })) {
    const source = readFileSync(join(mods, name, "main.js"), "utf8");
    for (const target of targets) assert.ok(source.includes(`mod: "${target}"`));
    assert.ok(!/mod:\s*"(?:worktree|menu|new-menu)"/.test(source));
  }
  const layout = JSON.parse(readFileSync(join(root, "patches/herdr-worktrees/layouts/wt.json"), "utf8"));
  assert.equal(layout.terminal_menu, "wt-menu");
  const text = JSON.stringify(layout);
  assert.ok(text.includes('"mod":"wt-tabs"'));
  assert.ok(text.includes('"mod":"wt-spaces"'));
});
