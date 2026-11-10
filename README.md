# install-arch

Minimal personal Arch setup helper. Inspired by Omarchy, but simplified.

## Structure

- `packages/base.packages`: pacman packages you always want.
- `packages/aur.packages`: AUR packages installed with `yay`.
- `packages/vscode.extensions`: VS Code extensions installed with `code`.
- `config/`: user configuration files, generally copied into `~/.config/` (Claude Code settings go into `~/.claude/`).
- `bin/`: user commands installed into `~/.local/bin/`.
- `scripts/`: install/config helpers.
  - Includes installer/config wrappers for Warp (official Arch pacman repo), Nix, `devbox`, `uv`, Claude Code (official installer), Blip AI (official AppImage), and `tailscale`.
- `install.sh`: main entry point.

## Install

Run the top-level installer:

```bash
./install.sh
```

At startup, an interactive GNOME keybinding selector guesses whether this is a laptop or desktop and highlights that profile. Use **↑ / ↓** to choose and **Enter** to confirm (**Esc** or **Ctrl+C** cancels before installation starts).

Detection uses the machine's chassis type, falling back to a system battery when needed (not mouse/keyboard batteries). If neither gives a laptop signal, it defaults to `desktop`. Docked laptops still default to `laptop`.

The prompt also works with `curl | bash`. Without a usable terminal, the detected profile is used automatically. Set `GNOME_KEYBINDINGS_PROFILE=laptop` or `desktop` to bypass the prompt and force a profile:

```bash
GNOME_KEYBINDINGS_PROFILE=desktop ./install.sh
```

This also controls the Home folder shortcut and overview key:
- `laptop`: home `<Control><Alt>f`, overview `Super`
- `desktop`: home `<Alt>f`, overview `Super_L` (left Super only)

The Home folder shortcut runs `nautilus --new-window`, opening a separate Files window on every press instead of reusing a window/tab. This replaces GNOME's built-in Home shortcut with a custom launcher. Nautilus has no global setting to disable tabs; explicit tab actions and folder-opening requests from other apps are unchanged.

The selected profile also controls [GNOME power defaults](#gnome-power-defaults): desktops stay awake with no idle screen blanking or dimming; laptop power settings are left unchanged.

To choose and apply just the keybindings again:

```bash
./scripts/apply-gnome-keybindings.sh
```

`SKIP_GNOME_KEYBINDINGS=1 ./install.sh` skips both the selector and keybinding changes.

Test profile detection and the terminal selector without changing system settings:

```bash
python testing/test-gnome-keybindings-profile.py
```

## Test on a fresh Arch VM (Vagrant)

Use the Vagrant environment in `testing/vagrant` to validate the install on a clean machine.
This VM intentionally mounts no local folders, so the install is tested over the internet only.

Prerequisites:
- Vagrant
- VirtualBox

From the repository root:

```bash
cd testing/vagrant
```

Start from scratch each time:

```bash
vagrant destroy -f
vagrant up
```

This recreates the VM from scratch for each test run.
If you also want to force re-download of the base image:

```bash
vagrant destroy -f
vagrant box remove archlinux/archlinux --provider virtualbox -f
vagrant up
```

Run the full test cycle automatically (boot, install via internet, destroy VM instance):

```bash
./testing/run-vagrant-test.sh
```

SSH into the VM and run the installer:

```bash
vagrant ssh
command -v curl >/dev/null || sudo pacman -Sy --noconfirm curl
curl -fsSL https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | bash
```

Exit the VM when done:

```bash
exit
```

Optional cleanup after testing:

```bash
cd testing/vagrant
vagrant destroy -f
```

## Online install (curl/wget)

Like Omarchy, you can bootstrap with a single command (after publishing):

```bash
curl -fsSL https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | bash
```

To bypass the selector and force the GNOME desktop keybinding profile during bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | GNOME_KEYBINDINGS_PROFILE=desktop bash
```

or

```bash
wget -qO- https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | bash
```

This will:
1. Remove an existing Lix install if detected.
2. Install pacman packages from `packages/base.packages`, including Arch's `nix` package, then offer to install Steam from multilib with matching GPU libraries (default: no; includes a full system upgrade if accepted).
3. Configure Warp's official pacman repo/signing key and install `warp-terminal`.
4. Install AUR packages from `packages/aur.packages` (requires `yay`), and refresh installed development packages (for example `*-git`) to the latest upstream commits.
5. Detect GPU vendor(s) and auto-install hardware codec packages when available (plus CPU decode baseline packages).
6. On NVIDIA systems, install the DKMS driver/header packages and early-load NVIDIA DRM modules from the initramfs for more reliable monitor detection before GDM starts.
7. Install upstream tools (`devbox`, `uv`, Claude Code, Herdr, Blip AI, `tailscale`, `@earendil-works/pi-coding-agent`, `playwright`) via scripts in `scripts/`.
8. Install user commands from `bin/`, apply configs from `config/`, bind Warp voice input to Right Super, and configure Pi to start with GPT-6.1 Sol at xhigh thinking.
9. Install VS Code extensions from `packages/vscode.extensions` (if `code` is available).
10. Bind VS Code `Alt+Q` to Rewrap Revived (`rewrap.rewrapComment`) when `code` is available.
11. Apply audio defaults (disable WirePlumber auto-switch to Bluetooth headset profile when recording).
12. Set `kernel.yama.ptrace_scope=0` for debugger attach without repeated superuser prompts (system-wide).
13. Allow the install user to run `sudo tcpdump` without a password via `/etc/sudoers.d/10-tcpdump-$USER`.
14. Configure global GDB pretty printers in `~/.gdbinit`.
15. Enable and start `nix-daemon.service` with `systemctl` when available.
16. Enable and start `sshd.service` with `systemctl`.
17. Enable and start `tailscaled.service` with `systemctl` when available.
18. Set the default shell to fish.
19. Apply GNOME keybindings, default to 8 workspaces, set dark mode, use a 24-hour clock, and disable idle screen blanking, dimming, and automatic suspend for desktops (if GNOME settings are available).
20. Install Shatter Shell from Git and GitHub Tray from its verified release, disable Pop Shell if present, and enable Shatter Shell, GitHub Tray, GSConnect, AppIndicator tray support, and Arch Update Indicator (if available).
21. Configure Arch Update Indicator to check/apply updates with `yay` (if installed).
22. Add GNOME autostart entries for `pear-desktop` and Blip AI.
23. Sync GNOME monitor layout to GDM via `/etc/xdg/monitors.xml` and `/var/lib/gdm/.config/monitors.xml`, remapping unstable connector names from monitor EDIDs when available, and install a `gdm.service` drop-in to refresh both before login.

The installer also enables and starts `paccache.timer` (`sudo systemctl enable --now paccache.timer`) for weekly pacman cache cleanup, keeping the latest three cached versions of each package by default. The timer is provided by `pacman-contrib`, included in `packages/base.packages`.

Skip optional steps:

```bash
SKIP_LIX_REMOVAL=1 ./install.sh
SKIP_NIX=1 ./install.sh
SKIP_STEAM=1 ./install.sh
SKIP_SHELL=1 ./install.sh
SKIP_CLAUDE_CODE=1 ./install.sh
SKIP_HERDR=1 ./install.sh
SKIP_HERDR_AGENT_RESUME=1 ./install.sh
SKIP_HERDR_WORKTREES=1 ./install.sh
SKIP_BLIP_AI=1 ./install.sh
SKIP_PI_SETTINGS=1 ./install.sh
SKIP_WARP_SETTINGS=1 ./install.sh
SKIP_VSCODE_EXTENSIONS=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
SKIP_SHATTER_SHELL=1 ./install.sh
SKIP_GITHUB_TRAY=1 ./install.sh
SKIP_GNOME_KEYBINDINGS=1 ./install.sh
SKIP_GNOME_WORKSPACES=1 ./install.sh
SKIP_GNOME_THEME=1 ./install.sh
SKIP_GNOME_POWER=1 ./install.sh
SKIP_AUDIO_TWEAKS=1 ./install.sh
SKIP_NVIDIA_DISPLAY=1 ./install.sh
SKIP_PTRACE_SCOPE=1 ./install.sh
SKIP_TCPDUMP_SUDO=1 ./install.sh
SKIP_GDB_PRETTY_PRINTERS=1 ./install.sh
SKIP_GDM_MONITORS=1 ./install.sh
SKIP_HW_CODECS=1 ./install.sh
```

## Steam (Arch multilib)

Steam is optional: `install.sh` (via `scripts/install-all.sh`) asks `Install Steam? [y/N]:`. Press Enter to skip, or answer `y`/`yes` to install. The prompt also works with `curl | bash`; without a usable terminal, Steam is skipped. Skipping leaves multilib unchanged and does not remove an existing Steam installation.

To run just the Steam setup as your normal user (with the same prompt):

```bash
./scripts/install-steam.sh
```

This enables Arch's `[multilib]` repository if needed, preserving existing settings and saving the original `/etc/pacman.conf` as `/etc/pacman.conf.before-steam` before changing it. It installs `steam` and 64-/32-bit OpenGL and Vulkan libraries for detected Intel, AMD, and NVIDIA GPUs, including hybrid systems. With no supported GPU detected, it uses software Vulkan (limited gaming performance).

The script runs `pacman -Syu --noconfirm --needed`, so **it also performs a full system upgrade** rather than an unsupported partial upgrade. NVIDIA support targets the current official Arch driver; a working kernel/display driver is still required. The full installer handles that separately through `scripts/configure-nvidia-display.sh`. Legacy NVIDIA/AUR driver stacks need matching libraries installed manually instead.

Preview package selection without changing anything:

```bash
./scripts/install-steam.sh --check
```

Launch **Steam** from GNOME or run `steam` (not with sudo), then sign in. For Windows games, use Steam's **Settings → Compatibility** to enable Steam Play/Proton as needed. If kernel or GPU drivers were upgraded, reboot before playing.

Set `INSTALL_STEAM=1 ./install.sh` to install without prompting, or `SKIP_STEAM=1 ./install.sh` to skip without prompting. Both also work with `scripts/install-all.sh` and `scripts/install-steam.sh`; `SKIP_STEAM=1` takes precedence. `--check` never prompts or installs.

Test with mocked package commands and temporary configuration files (no installation):

```bash
python testing/test-steam.py
```

## Warp terminal on Arch (official repo)

`install.sh` runs `scripts/install-warp-terminal.sh`, which:
- adds Warp's pacman repository (`[warpdotdev]`) to `/etc/pacman.conf` when missing
- imports and locally signs `linux-maintainers@warp.dev`
- removes conflicting AUR-provided `warp-terminal` packages (if present)
- installs `warp-terminal` with pacman

Run it manually:

```bash
./scripts/install-warp-terminal.sh
```

The config step updates only `agents.voice.voice_input_toggle_key` in `~/.config/warp-terminal/settings.toml`, setting it to Warp's `super_right` value. Existing Warp settings are preserved. Apply just this setting with:

```bash
./scripts/configure-warp-terminal.sh
```

Opt out for a run with `SKIP_WARP_SETTINGS=1 ./install.sh`.

## Hunk terminal diff viewer (AUR)

[Hunk](https://www.hunk.dev/) is installed from the community-maintained `hunk-bin` AUR package via `packages/aur.packages`. It uses upstream's prebuilt binaries, with updates managed by `yay` rather than `hunk update`.

To install only Hunk as your normal user (requires `yay`):

```bash
yay -S --needed hunk-bin
```

From a Git repository:

```bash
hunk diff          # review working-tree changes, including untracked files
hunk diff --watch  # refresh as files change
hunk show          # review the latest commit
```

This repo does not change your Git pager or difftool settings.

## Claude Code (official installer)

`install.sh` runs `scripts/install-claude-code.sh`, which uses the official native installer at `https://claude.ai/install.sh` (no npm or AUR package). It installs the `claude` command into `~/.local/bin`, already included in this repo's Fish `PATH`, and skips installation when Claude Code is already present.

Run it manually as your normal user:

```bash
./scripts/install-claude-code.sh
```

Then run `claude` and sign in. Native installations update automatically.

The config step (`scripts/apply-config.sh`) also runs `scripts/configure-claude-code.sh`. It merges `config/claude/settings.json` into `~/.claude/settings.json`, setting `attribution.commit` to `""` to disable Claude's `Co-Authored-By` commit attribution and `attribution.sessionUrl` to `false` to omit session links from commits and PRs. Other settings, including PR attribution text, are preserved. Invalid existing JSON is left untouched and reported as an error.

Apply just the Claude Code settings (also works for an existing installation):

```bash
./scripts/configure-claude-code.sh
```

If you use a custom Claude directory, set `CLAUDE_CONFIG_DIR` when running the configuration script or installer; settings are then merged into `$CLAUDE_CONFIG_DIR/settings.json`. Project or managed Claude settings can override these user-level defaults.

Skip both Claude Code installation and configuration for a run:

```bash
SKIP_CLAUDE_CODE=1 ./install.sh
```

## Herdr (desktop and terminal apps)

`install.sh` installs the Herdr desktop app and the [Herdr terminal app](https://github.com/herdrdev/herdr) through `scripts/install-upstream-tools.sh` and `scripts/install-herdr.sh`. The script uses the official installers at `https://releases.herdr.dev/core/install.sh` and `https://releases.herdr.dev/app/install.sh`, installing `herdr-core` first, then the desktop app. It also installs the separate `herdr` terminal command using `https://herdr.dev/install.sh`. Downloads complete before execution; upstream verifies release checksums.

Run just this step as your normal user:

```bash
./scripts/install-herdr.sh
```

The desktop app lives in `$XDG_DATA_HOME/herdr-app` (default `~/.local/share/herdr-app`), with `herdr-app` and `herdr-core` commands in `~/.local/bin` and a GNOME app-launcher entry. Upstream also adds `hc` if that command is not already taken. The terminal app is installed as `~/.local/bin/herdr`; run `herdr` in your existing terminal to start it. Existing desktop, core, and terminal installations are left alone; reruns install only missing components. The desktop app manages subsequent updates itself; use `herdr update` for the terminal app. This component installer does not change Herdr settings or add autostart entries. The full pipeline also installs the agent-resume mod and selects the WT-compatible worktree layout described below.

The script installs missing Arch dependencies (`curl` and `gawk`, plus `tar`, `libxkbcommon-x11`, and `vulkan-icd-loader` when desktop/core installation is needed) via pacman. The desktop app requires a desktop session and a working Vulkan driver; the script does not select or replace your GPU driver. Launch **Herdr** from GNOME or run `herdr-app`. Installing only the missing terminal command does not require desktop dependencies.

Skip installation with `SKIP_HERDR=1 ./install.sh`; the flag also works with `scripts/install-herdr.sh` and `scripts/install-upstream-tools.sh`. Test without network access or installation:

```bash
python testing/test-herdr.py
```

### Herdr agent resume (auto mode)

After installing Herdr and Pi, the full pipeline runs `scripts/install-herdr-agent-resume.sh`. It installs [mortenvp/herdr-agent-resume](https://github.com/mortenvp/herdr-agent-resume), pinned to commit `a62a3eeb9d2fc46f60490ecd44042b0a0b77cb28` (v0.4.1), with `--auto --update --no-adopt`. Change the pinned revision in the script deliberately after reviewing fork updates; it does not track upstream automatically. Before updating, follow the [workaround review and retirement checklist](#herdr-workaround-review-and-retirement).

```bash
./scripts/install-herdr-agent-resume.sh
# Remove the mod, its hooks, shortcut and shell-startup blocks:
./scripts/install-herdr-agent-resume.sh --uninstall
```

The mod lives in `~/.config/herdr-app/mods/agent-resume` (`HERDR_APP_HOME` or `XDG_CONFIG_HOME` can change the app directory). Its installer adds Ctrl+Shift+R, a Pi session-reporting extension in `~/.pi/agent/extensions`, hooks for other supported agents already configured on this machine, and automatic-resume blocks for configured bash/zsh/fish shells. The wrapper initializes absent Herdr/Pi configuration directories and Fish's `conf.d` when Fish is installed, so a fresh setup is covered too. Agent and Fish configuration locations follow the mod's standard `~/.pi`, `~/.claude`, `~/.config/fish`, etc. paths; custom agent/Fish config roots are not supported by this revision.

The installer backs up changed files under the app home's `backups/agent-resume/`. Reruns update installer-owned mod files and refresh auto-mode configuration; edited mod files, conflicting shortcuts, symlinked configuration files and unrelated same-named Pi extensions are refused. Missing `git`/`python` are installed with pacman. `SKIP_HERDR=1` or `SKIP_HERDR_AGENT_RESUME=1` skips this step without disabling an existing installation.

The wrapper supplies `scripts/herdr-pi-session-hook.js` as the installer's Pi extension template. It records only transcript files that actually exist (Pi allocates a filename before saving any messages), records newly saved sessions before the first provider request, and retries ignored/failed hook attempts instead of treating every zero exit code as success. The upstream installer still owns extension backups and removal.

No core restart, logout or reboot is performed. New agent sessions pick up the hooks; existing Pi sessions inside Herdr need `/reload`, while other running agents need to be restarted/resumed before their new hooks record them. Auto mode runs when a kept terminal's replacement shell starts, not merely when the desktop window opens. To pause automatic recovery, export `AGENT_RESUME_AUTO=0` in the relevant shell configuration (Fish: `set -gx AGENT_RESUME_AUTO 0`).

To inspect recovery without starting anything:

```bash
python3 "${HERDR_APP_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr-app}/mods/agent-resume/agent_resume.py" status
```

A Pi label reporting `no saved conversation to resume` cannot recover a transcript that was never written. Use `pi --resume` in that Herdr pane to choose an existing saved conversation; recovery deliberately does not substitute an arbitrary recent session. A brand-new Pi session needs at least one saved message to be recoverable.

**Experimental:** this pinned revision still has known Pi launch-option limitations and a manual/automatic recovery race. It can lose CLI tool restrictions or custom session-directory options; its argument filter can retain positional prompt text if captured alongside certain flags. Do not rely on it to preserve safety restrictions or guarantee idle-only recovery. Avoid pressing Ctrl+Shift+R while automatic recovery is running. The wrapper adds installer guards and the Pi extension fix above, but does not patch the Python mod itself.

Offline installer and Pi lifecycle tests:

```bash
python testing/test-herdr-agent-resume.py
node --test testing/test-herdr-pi-session-hook.mjs
```

### Herdr worktree locations (same as WT)

The full pipeline runs `scripts/install-herdr-worktrees.sh`. It installs and selects the personal **wt** layout, based on Herdr's main layout, so **New worktree** in the tab bar's **+** menu and the space's right-click menu creates `<main-checkout>.worktrees/<branch>`. Branch folder names use the same sanitization as `bin/wt-ui`. Creation from an existing linked worktree still uses the same main-checkout entry that WT reads from Git's worktree list. Only placement matches WT; Herdr's branch creation behavior is otherwise unchanged.

```bash
./scripts/install-herdr-worktrees.sh
# Return to main and remove installer-owned customization files:
./scripts/install-herdr-worktrees.sh --uninstall
```

The sources live in `patches/herdr-worktrees/`: five separately named `wt-*` mods and `layouts/wt.json`, reviewed against Herdr **0.1.14**. They are frozen personal copies, not edits to shipped mods. Herdr upgrades therefore leave them alone; other main-layout panels still use shipped mods and receive updates. The original **main**, **terminals**, and **win98** layouts are unchanged and retain Herdr's default paths. Keep **wt** selected for this behavior; rerunning the installer selects it again. Review native support and the copied mods before deliberately refreshing the snapshot—Herdr's future menu changes do not automatically propagate into these copies.

Installation works before the first Herdr launch too. The script uses `HERDR_APP_HOME`, otherwise `$XDG_CONFIG_HOME/herdr-app`, otherwise `~/.config/herdr-app`. All five mods must pass `herdr-app check` before installation. Reruns leave identical files alone, back up updated owned files under `backups/wt-worktrees/`, and refuse edited/unrelated files or symlinked targets. A running app is switched through its command API; with Herdr closed, only the selected layout in `shared.json` is changed, preserving other keys. No settings, keybindings, terminal processes, Git repositories or existing worktree paths are changed. **Open worktree** still lists registered checkouts at any location. Uninstallation leaves backups, mod state, editor helpers and unrelated files alone.

`SKIP_HERDR=1` or `SKIP_HERDR_WORKTREES=1` skips setup; neither removes an existing installation. Test without a desktop session or network:

```bash
python testing/test-herdr-worktrees.py
node --test testing/test-herdr-worktree-mod.mjs
```

### Herdr workaround review and retirement

**These customizations are temporary workarounds, not features we want to maintain forever.** At each Herdr app/core update, and before updating a mod pin or local compatibility fix, check whether upstream now supports the behavior. Prefer native support and retire the redundant mod or patch once it is verified.

Original review baseline: **Herdr desktop 0.1.13**; the worktree layout was reviewed and added on **0.1.14**. Issue states below are from those reviews; recheck them rather than treating them as permanent.

| Customization | Upstream tracking / what to review | When we can drop it |
| --- | --- | --- |
| Agent-resume mod (**installed**) | [herdr-app#406: reboot/session recovery](https://github.com/herdrdev/herdr-app/issues/406) (open); check desktop/core release notes and native agent-session metadata. | Native recovery automatically restores the correct Pi/Claude conversation in each kept pane after reboot, preserves launch restrictions, and does not restart intentionally exited agents or arbitrary commands. |
| Local Pi recording fix (**installed**, `scripts/herdr-pi-session-hook.js`) | Review the [agent-resume fork](https://github.com/mortenvp/herdr-agent-resume), especially its Pi extension, before moving the pin. This patch may become unnecessary before the whole mod does. | The reviewed upstream extension waits for an actual saved transcript and retries ignored/failed hook attempts. Then remove our template substitution instead of carrying a duplicate fix. |
| Sibling worktree folders (**installed**, `patches/herdr-worktrees/`) | `<repo>.worktrees/<branch>`, matching WT. [herdr-app#289](https://github.com/herdrdev/herdr-app/issues/289) (open at the 0.1.14 review) explains the five-mod/menu clone chain. [herdr#261](https://github.com/herdrdev/herdr/issues/261) was closed as **not planned** and concerns the **terminal app**, not desktop support. | Native desktop placement matches WT from both the main checkout and a linked worktree. Remove with `./scripts/install-herdr-worktrees.sh --uninstall`, then retire its pipeline step, templates, wrapper/helper and tests. |

On each review:

1. Check current desktop release notes, settings, shipped mods, and the linked issues. A closed issue, proposed PR, or terminal-only feature is **not** proof that the desktop behavior is available.
2. In a backed-up test setup, disable the matching workaround and test the native replacement. For agent recovery, verify Pi and Claude across a controlled reboot; for worktree placement, verify the destination from both the main checkout and a linked worktree. Do not leave two automatic recovery mechanisms enabled together.
3. If native support is sufficient, remove the workaround's pipeline call, installer/configuration, obsolete flags, patches, and workaround-only tests/docs as appropriate. Uninstall an existing agent-resume installation with `./scripts/install-herdr-agent-resume.sh --uninstall`; `SKIP_HERDR_AGENT_RESUME=1` only skips setup and **does not uninstall it**. Uninstall the worktree layout with `./scripts/install-herdr-worktrees.sh --uninstall`; its skip flag does not uninstall it. Removing a worktree customization must not delete or move existing worktrees.
4. Record the reviewed versions, result, and remaining need in this section. If support is still missing, keep the workaround and its regression tests; do not update personal mod clones blindly, since they no longer receive shipped-mod fixes automatically.

## Blip AI (official Linux AppImage)

`install.sh` installs [Blip AI](https://www.blipai.app/linux) through `scripts/install-upstream-tools.sh` and `scripts/install-blip-ai.sh`. It downloads the latest official x86_64 AppImage from `abnsl0014/blipai-releases` on GitHub, verifies the release asset's SHA-256 digest, and installs it as `~/.local/bin/BlipAI.AppImage`, with a **Blip AI** GNOME launcher. It never launches the app during installation. Other architectures are skipped.

Run just this step as your normal user:

```bash
./scripts/install-blip-ai.sh
```

Missing Arch dependencies (`curl`, `jq`, `fuse2`, `wtype`, `wl-clipboard`, and `ydotool`) are installed with pacman. Existing executable AppImages at that path are preserved on reruns (this script is not an updater). The installer calls `scripts/configure-blip-ai.sh` to recreate the launcher under `${XDG_DATA_HOME:-$HOME/.local/share}/applications/` and an autostart entry at `${XDG_CONFIG_HOME:-$HOME/.config}/autostart/blip-ai.desktop`. Blip AI starts when you log into GNOME, including after a reboot, not before login.

Enable autostart for an already-installed AppImage without downloading, installing packages, or launching the app:

```bash
./scripts/configure-blip-ai.sh
```

### Wayland setup (explicit permission grant)

Following [upstream's setup guide](https://www.blipai.app/articles/linux-setup), GNOME Wayland needs input access and the ydotool user daemon. **These are not enabled automatically:** membership in `input` allows applications running as your user to read raw keyboard/mouse events, potentially including passwords, and use input devices outside Wayland's normal isolation. Only grant it on a trusted personal machine:

```bash
sudo groupadd -f input
sudo usermod -aG input "$(id -un)"
```

Fully log out and back in (or reboot), then run these in your graphical session:

```bash
groups | grep input
systemctl --user enable --now ydotool
systemctl --user status ydotool
```

If the daemon cannot access `/dev/uinput`, check the device permissions and group membership; do not make input devices world-writable. X11 does not need these Wayland steps.

Blip AI opens automatically at your next GNOME login. To use it now, open **Blip AI** from GNOME or run `~/.local/bin/BlipAI.AppImage`, sign in, and hold **Ctrl+Super** to dictate. No Blip settings or hotkeys are changed by this repo.

Skip installation and autostart setup with `SKIP_BLIP_AI=1 ./install.sh`; the flag also works with `scripts/install-blip-ai.sh`, `scripts/configure-blip-ai.sh`, and `scripts/install-upstream-tools.sh`. Skipping leaves existing autostart entries unchanged. Test without network access, installation, or permission changes:

```bash
python testing/test-blip-ai.py
```

## Pi coding agent defaults

The config step merges `config/pi/settings.json` into `~/.pi/agent/settings.json`. It configures `openai-codex/gpt-6.1-sol` as the startup model with the `xhigh` thinking level while preserving unrelated settings and installed packages.

Apply just the Pi defaults with:

```bash
./scripts/configure-pi.sh
```

Set `PI_CODING_AGENT_DIR` to use a custom Pi config directory, or opt out for a run with `SKIP_PI_SETTINGS=1 ./install.sh`.

## Media codecs (auto-detect + install)

`install.sh` now runs `scripts/install-hw-codecs.sh`, which:
- installs CPU decode baseline packages (`ffmpeg`, `openh264`)
- detects GPU vendor(s) (Intel/AMD/NVIDIA)
- installs matching hardware decode packages when available in pacman

Run it manually:

```bash
./scripts/install-hw-codecs.sh
```

Check only (no installation):

```bash
./scripts/install-hw-codecs.sh --check
```

## NVIDIA display reliability

`install.sh` runs `scripts/configure-nvidia-display.sh`, which detects NVIDIA GPUs and configures early NVIDIA DRM loading through `/etc/mkinitcpio.conf.d/90-nvidia-early-kms.conf`. It skips the initramfs rebuild when the packages and drop-in are already in place.

Run it manually after changing NVIDIA or kernel packages:

```bash
./scripts/configure-nvidia-display.sh
```

Check only (no installation or initramfs rebuild):

```bash
./scripts/configure-nvidia-display.sh --check
```

## Shatter Shell (from Git)

The package step runs `scripts/install-shatter-shell.sh` instead of installing Pop Shell from AUR. It clones [adil192/shatter-shell](https://github.com/adil192/shatter-shell) from `master_resolute`, fast-forwards the checkout on reruns, and builds with the project's locked npm dependencies. Missing build tools are installed with pacman. The script refuses modified checkouts and GNOME versions not supported by the checked-out extension's metadata.

Sources are kept in `${XDG_CACHE_HOME:-$HOME/.cache}/install-arch/shatter-shell`; the extension and compiled settings schema are installed under `${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/shatter-shell@adilhanney.com`. No system-wide extension files are overwritten.

Build/install or update just Shatter Shell as your normal user:

```bash
./scripts/install-shatter-shell.sh
```

Then log out and back in, and enable/configure it:

```bash
./scripts/enable-gnome-extensions.sh
```

The configuration step disables Pop Shell before enabling Shatter Shell and makes workspaces span displays. Existing Pop Shell packages are kept as a fallback, but never enabled by this installer. Pop Shell preferences are not migrated to Shatter Shell. If GNOME cannot see the new extension yet, the installer reports that you need to log out/in and rerun the enable script.

Set `SKIP_SHATTER_SHELL=1` to skip both its installation and configuration, leaving Pop Shell unchanged. `SKIP_GNOME_EXTENSIONS=1` skips extension configuration only; it does not skip building Shatter Shell.

Test without installing packages, accessing the network, or changing GNOME settings:

```bash
python testing/test-shatter-shell.py
```

## GitHub Tray GNOME extension

The package step runs `scripts/install-github-tray.sh` to install [debba/github-tray-gnome-extension](https://github.com/debba/github-tray-gnome-extension). It downloads the upstream **v19** release bundle, checks its pinned SHA-256 digest, validates GNOME compatibility and settings schemas, installs it for your user with `gnome-extensions install`, and applies this repo's [Done-button patch](patches/github-tray-v19-done.patch) ([upstream MIT license](patches/github-tray-LICENSE)). This release supports GNOME Shell 45–51. Review the release and digest before updating the pin in the script.

```bash
./scripts/install-github-tray.sh
./scripts/enable-gnome-extensions.sh
```

A new extension may not be visible to the running Shell yet. On Wayland, log out and back in, then rerun the enable script if needed. No logout or Shell restart is performed automatically. The extension lives under `${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/github-tray@debba.github.com`; its compiled settings schema is included. Reruns apply the Done patch to an existing v19 installation without downloading it again, leave an already-patched v19 unchanged, and preserve newer compatible versions without patching or downgrading them. The patch is dry-run before any source changes; incompatible edits and symlinked source files are refused. GNOME/upstream extension updates can overwrite the local patch; rerun the installer for v19, and review/rebase the patch before using it with another release.

Missing Arch dependencies (`curl`, `jq`, `unzip`, `glib2`, `libsoup3`, `zenity`, and `patch`) are installed with pacman. GNOME must already be installed. Installation does not configure authentication or copy credentials from `gh` or other tools.

GitHub Tray is a panel widget, not a separate app. The installer runs `scripts/configure-github-tray.sh` to add a **GitHub Tray Settings** launcher under `${XDG_DATA_HOME:-$HOME/.local/share}/applications/`. Search for it in GNOME to open authentication/preferences directly. The widget's initial “configure token and username” message is not clickable, and its gear button may not appear until repositories have loaded. You can also open preferences with:

```bash
gnome-extensions prefs github-tray@debba.github.com
```

To create or repair just the launcher for an existing installation, run `./scripts/configure-github-tray.sh`; this does not download, enable, or launch anything.

In **Authentication**, enter your GitHub username and personal access token manually, pressing each field's Apply/checkmark button to save. Upstream documents `public_repo` for public repositories or `repo` for private repositories; use the least privileges you need. Notification APIs require a **classic** personal access token with `notifications` scope (or `repo`, which also grants notification access); fine-grained PATs are not supported by GitHub's notification endpoints. **Upstream stores the token in GSettings, not an encrypted keyring.** Never put tokens in this repo, scripts, or shell commands/history.

Each notification has a **Done** button alongside the existing **Mark as read** checkmark. Done calls GitHub's `DELETE /notifications/threads/{id}` endpoint: it marks the notification as Done in GitHub's inbox, not just read locally. It does not delete the issue/PR or unsubscribe from the thread. The row and counts update only after GitHub confirms success; failed requests keep the notification and show **Retry Done**. To add it to an existing v19 installation, run `./scripts/install-github-tray.sh`, then log out and back in. The installer never reads or changes your token and makes no notification API calls.

`SKIP_GITHUB_TRAY=1` skips installation, launcher setup, and enabling without disabling an existing installation. `SKIP_GNOME_EXTENSIONS=1` skips extension enabling only, consistent with Shatter Shell; package installation still creates the settings launcher.

Offline tests (no downloads, package installs, or real GNOME changes; includes JS behavior tests when Node.js is available):

```bash
python testing/test-github-tray.py
```

## GNOME power defaults

`install.sh` runs `scripts/apply-gnome-power.sh`. For the `desktop` profile it sets screen blanking to **Never** (`idle-delay=0`), disables idle dimming, and disables automatic idle suspend on both AC and battery power. The `laptop` profile leaves all existing power settings unchanged.

It reuses `GNOME_KEYBINDINGS_PROFILE` from the startup selector. When run standalone or with `SKIP_GNOME_KEYBINDINGS=1`, it uses hardware detection unless that variable is explicitly set; it never opens an extra prompt.

Apply just these settings as your normal user:

```bash
./scripts/apply-gnome-power.sh
```

Use `GNOME_KEYBINDINGS_PROFILE=desktop` or `laptop` to override detection. Set `SKIP_GNOME_POWER=1 ./install.sh` to leave power settings untouched. These are user-session idle settings; manual locking/suspend and the GDM login screen are unchanged.

Test without changing system settings:

```bash
python testing/test-gnome-power.py
```

## GDM monitor layout

`install.sh` runs `scripts/setup-gdm-monitor-sync.sh`, which installs a GDM pre-start helper. The helper uses each machine's own `~/.config/monitors.xml` as the source of truth, reads the currently connected DRM monitor EDIDs, and rewrites only the connector names before syncing the layout to GDM.

This avoids hard-coding any monitor model, serial, connector, or desk layout in the repository. Different machines keep their own GNOME display layout, including intentionally disabled displays.

Run it manually after changing display layout in GNOME Settings:

```bash
./scripts/sync-gdm-monitors.sh --update-source
```

## Debugger attach without sudo (ptrace_scope)

`install.sh` runs `scripts/configure-ptrace.sh` by default, which:
- sets `kernel.yama.ptrace_scope=0` immediately
- writes `kernel.yama.ptrace_scope = 0` to `/etc/sysctl.d/10-ptrace.conf` for reboot persistence

Warning: this lowers ptrace isolation system-wide. Use only on trusted development machines.

Opt out for a run:

```bash
SKIP_PTRACE_SCOPE=1 ./install.sh
```

## Perf event access

`install.sh` runs `scripts/configure-perf-events.sh` by default, which:
- sets `kernel.perf_event_paranoid=1` immediately
- writes `kernel.perf_event_paranoid = 1` to `/etc/sysctl.d/10-perf-events.conf` for reboot persistence

Opt out for a run:

```bash
SKIP_PERF_EVENTS=1 ./install.sh
```

## Tcpdump without sudo password

`install.sh` runs `scripts/configure-tcpdump-sudo.sh` by default, which writes and validates a sudoers drop-in allowing the install user to run `/usr/bin/tcpdump` with `sudo` without a password.

Opt out for a run:

```bash
SKIP_TCPDUMP_SUDO=1 ./install.sh
```

## GDB pretty printers (global)

`install.sh` runs `scripts/configure-gdb-pretty-printers.sh` by default, which:
- writes a managed pretty-printer block into `~/.gdbinit`
- enables Python auto-loading in GDB
- adds default `skip` rules so stepping avoids common system/libstdc++ code paths
- adds `/usr/share/gcc-*/python` to the Python path and registers libstdc++ pretty printers

Run it manually:

```bash
./scripts/configure-gdb-pretty-printers.sh
```

Opt out for a run:

```bash
SKIP_GDB_PRETTY_PRINTERS=1 ./install.sh
```

## Add packages

- Pacman: add to `packages/base.packages`.
- AUR: add to `packages/aur.packages`.
- Steam (Arch): managed by `scripts/install-steam.sh` (multilib setup and GPU libraries, not AUR).
- Warp terminal (Arch): managed by `scripts/install-warp-terminal.sh` (official repo package, not AUR).
- VS Code extensions: add extension IDs to `packages/vscode.extensions`.
- Upstream tools: edit `scripts/install-upstream-tools.sh` and per-tool scripts in `scripts/`.
- Personal Pi package: `scripts/install-pi-agent-stuff.sh` installs `mortenvp/agent-stuff` from its `main` branch. Arch Update Indicator reports new commits and refreshes the package during updates.

Then run:

```bash
./scripts/install-all.sh
```

Install VS Code extensions only:

```bash
./scripts/install-vscode-extensions.sh
```

Configure VS Code keybindings only:

```bash
./scripts/configure-vscode-keybindings.sh
```

## Config files

- Fish config: `config/fish/config.fish` (copied to `~/.config/fish/config.fish`) and adds `~/.local/bin` to `PATH`.
- Fish functions: `config/fish/functions/` (copied to `~/.config/fish/functions/`), including the thin `wt` and `ci-merge` shell wrappers.
- User commands: `bin/` (installed executable into `~/.local/bin/`), including the Python-powered `wt-ui` worktree selector and `ci-merge-agent` pull-request merger. `ci-merge` is the human-facing wrapper; `ci-merge-agent` is the standalone JSON-first command for agents. Both work from any shell.
- Git config: `config/git/config` (copied to `~/.config/git/config`). Rewrites GitHub HTTPS URLs to SSH only for `mortenvp/` and `steinwurf/`; other owners are unchanged. Requires working GitHub SSH authentication.
- VS Code settings: `config/Code/User/settings.json` merged into `~/.config/Code/User/settings.json` (adds missing keys; prompts on conflicts when interactive; non-interactive runs overwrite conflicting keys with repo defaults).
- VS Code keybindings: `scripts/configure-vscode-keybindings.sh` ensures `Alt+Q` is bound to Rewrap Revived (`rewrap.rewrapComment`) and `Ctrl+Shift+S` is bound to Save All (`workbench.action.files.saveAll`) in `~/.config/Code/User/keybindings.json`.
- OpenCode config: `config/opencode/opencode.json` (copied to `~/.config/opencode/opencode.json`) and includes the Warp plugin (`@warp-dot-dev/opencode-warp`).
- Warp settings: `scripts/configure-warp-terminal.sh` preserves existing settings and sets the voice input toggle to Right Super in `~/.config/warp-terminal/settings.toml`.
- Pi settings: `config/pi/settings.json` is merged into `~/.pi/agent/settings.json`, selecting `openai-codex/gpt-6.1-sol` with `xhigh` thinking while preserving unrelated settings.
- Claude Code settings: `config/claude/settings.json` (merged into `~/.claude/settings.json`, or `$CLAUDE_CONFIG_DIR/settings.json`) disables commit attribution and session links without replacing other settings.

Apply configs and user commands only:

```bash
./scripts/apply-config.sh
```

## Git worktree selector

From any Git worktree, run:

```fish
wt
```

`wt` first offers four interactive, arrow-key-driven flows:

- **Use an existing remote branch:** fetch and prune all Git remotes, show remote branches newest-first by commit date, and create a tracking worktree (or enter its existing worktree).
- **Create a new branch:** update the current branch with `git pull --ff-only`, create the branch in a new worktree, and publish it with `git push --set-upstream` to the current branch's remote. If there are uncommitted changes, first ask whether to move them to the new worktree (defaults to **No**; declining cancels without changing anything). Accepted transfers include staged, unstaged, and untracked files, preserve staging, and leave ignored files behind. A temporary stash protects the changes while pulling; failures before worktree creation attempt to restore them to the original worktree, and transfer conflicts retain the stash with recovery instructions. Existing stashes are preserved. Changes inside submodules must be handled manually.
- **Delete an existing worktree:** pick a linked worktree (the main worktree is never offered), see its branch, upstream, unpushed commits, and dirty state, then remove it with `git worktree remove`. Deleting the local and remote branch are separate confirmations that default to **Yes**; discarding uncommitted changes and force-deleting an unmerged local branch default to **No**, and the remote's default branch is never deleted. If you delete the worktree you are standing in, `wt` moves you to the main worktree.
- **Clean up worktrees:** fetch and prune all remotes, then review clean linked worktrees in a multi-select list. Suggestions show merge ancestry against the upstream remote's default branch (when known), a gone upstream, and unpushed commits. Without a remote upstream, merge ancestry is checked against any known remote default branch. Missing worktree directories are also offered for registration removal. The main worktree and dirty, locked, or detached worktrees are skipped. Ignored files (such as build output, caches, and virtual environments) do not block cleanup and are deleted with the worktree; affected worktrees are labeled. No boxes are checked initially. Press **Enter** to delete the highlighted worktree, or check multiple worktrees with **Space** and press **Enter** to delete only those checked. There is **no additional confirmation**. Press **Ctrl+C** to cancel without deleting anything. Cleanup rechecks each worktree, never forces removal, and **keeps all local and remote branches**, including unpushed commits. If your current worktree is removed, `wt` moves you to the main worktree.

Jump directly to cleanup with either command:

```fish
wt cleanup
wt prune
```

A clean worktree only means there are no uncommitted changes—not that its branch was merged. A gone upstream is not proof of a merge either. Merge labels use Git ancestry against locally known remote default refs (`<remote>/HEAD`); squash/rebase merges may not be recognized. Use **Delete an existing worktree** if you also want to delete branches. Unlike `git worktree prune`, this cleanup flow can remove actual worktree directories after review, not just stale registrations.

Test the worktree flows with disposable local repositories (no installation required):

```bash
uv run --script testing/test-wt-ui.py
```

The `wt-ui` executable uses Questionary for selection and Rich for terminal output. Its PEP 723 metadata lets it run through `uv` with isolated Python dependencies. UI is written to stderr; only the selected path is written to stdout for the Fish wrapper to consume and `cd` into.

## CI-gated pull-request merge

Run from the clean, fully pushed branch associated with a GitHub pull request:

```fish
ci-merge
ci-merge 42
ci-merge https://github.com/owner/repository/pull/42
```

`ci-merge` requires authenticated `gh`, an open non-draft pull request, a local branch and HEAD matching the pushed PR head, at least one CI check before merging, and squash merging support. It shows the PR and checks, asks for confirmation with **No** as the safe default, waits for pending checks, and revalidates the local state and exact PR head SHA before running a guarded squash merge. If GitHub has not reported any checks yet, confirming starts a scheduling grace period: it polls every 10 seconds for up to 120 seconds for checks to appear, then waits normally for them to finish. If no checks appear, it stops without merging. Checks disappearing after they have been reported, failed checks, local changes, unpushed commits, review blockers, or PR changes also stop the merge.

### Agent usage

Agents should call `ci-merge-agent` directly from any shell, from the clean, fully pushed PR branch. No Fish function, terminal interaction, or agent-specific plugin is needed. It requires `uv`, Git, and authenticated `gh`, just like the interactive command.

```bash
ci-merge-agent 42 --yes --timeout 900
```

- `--yes` explicitly authorizes a squash merge without prompting. It **only bypasses confirmation**, not CI, review, local-state, or SHA checks. Without it, merge mode fails before inspecting a PR or attempting a merge; local skill refresh can still run.
- JSON output is automatic: stdout contains one result object; progress and skill-update messages go to stderr, without spinners or live tables. `ci-merge --yes --json` uses the same interface, including automatic skill refresh. `ci-merge-agent --help` returns help in a JSON result without requiring `--yes`.
- `--timeout SECONDS` is a positive integer, default **900 seconds**, for CI waiting and final revalidation after confirmation/authorization. The initial no-checks grace period is still capped at 120 seconds. In-flight Git/GitHub calls retain their individual 30-second timeouts, so this is not a hard wall-clock limit on the whole process. The deadline is checked again before submitting a merge; merge submission and verification have separate command timeouts.
- The PR number can be replaced by a URL or omitted to infer the current branch's PR. An explicit target is recommended for agents.

The interactive `ci-merge` command also accepts `--yes`, `--json`, and `--timeout`. Without `--yes`, it requires a terminal and keeps its confirmation prompt with **No** as the default. All entry points now use the 900-second default waiting limit; increase it for slower CI.

JSON fields are `status`, `exit_code`, `message`, `pr_number`, `pr_url`, `head_sha`, `merge_commit`, and `merge_attempted`. PR details and the merge commit are `null` when unavailable. Status is `merged`, `error`, `timeout`, `cancelled`, `help`, or `skills_installed`. Agents should treat only `status: "merged"` as confirmation of a successful merge—not merely exit code 0, which also covers help and skill installation.

| Exit code | Meaning |
| --- | --- |
| `0` | Verified merge, help, or successful skill installation |
| `1` | Safety check, Git/GitHub, or explicit skill-installation failure |
| `2` | Invalid arguments or missing noninteractive authorization |
| `3` | Interactive confirmation declined or input closed |
| `124` | CI discovery/waiting deadline expired; no merge submitted |
| `130` | Interrupted with Ctrl+C |

If a non-success result has `merge_attempted: true`, the remote outcome may be uncertain: inspect the PR with `gh pr view` before retrying. Also verify the remote state if the process is killed or produces no complete result. Never respond to a blocked merge by falling back to an unguarded or administrative merge.

Suggested instruction for an agent:

> When I authorize merging, use `ci-merge-agent <PR-number-or-URL> --yes --timeout 900` from the clean, pushed PR branch. Parse its stdout as JSON. Report blockers rather than bypassing them, and verify the remote state before retrying an uncertain merge outcome.

To update these commands and their Fish wrapper from this checkout (without applying unrelated configs):

```bash
install -Dm755 bin/ci-merge-agent "$HOME/.local/bin/ci-merge-agent"
install -Dm755 bin/ci-merge "$HOME/.local/bin/ci-merge"
install -Dm644 config/fish/functions/ci-merge.fish "$HOME/.config/fish/functions/ci-merge.fish"
"$HOME/.local/bin/ci-merge-agent" --install-skills
```

Ensure `~/.local/bin` is on the agent's `PATH`, or call `~/.local/bin/ci-merge-agent` explicitly. Start a new Fish session after updating its wrapper. The normal `scripts/apply-config.sh` flow installs both commands and the Fish wrapper too.

### Automatically maintained agent skills

On each successfully parsed agent-mode invocation (including `--help` and a merge request missing `--yes`), the tool compares its bundled skill with these personal skill files and installs or refreshes them:

- Claude Code: `~/.claude/skills/ci-merge-agent/SKILL.md`
- Pi: `~/.pi/agent/skills/ci-merge-agent/SKILL.md`

`CLAUDE_CONFIG_DIR` and `PI_CODING_AGENT_DIR` override the respective config roots; use the same environment as the agent session. The skill teaches when to use the command, prerequisites, explicit merge authorization, JSON results, timeouts, and safe handling of uncertain outcomes. It grants no tool permissions and does not change agent settings.

Bootstrap or refresh the skills without GitHub access, a Git repository, or any merge:

```bash
ci-merge-agent --install-skills
```

This returns `status: "skills_installed"` only when both destinations are up to date. It cannot be combined with a PR target or `--yes`.

The skill is bundled in `bin/ci-merge-agent`, so updating the installed commands also updates the available instructions. Content comparison detects changes without a version bump or network request. Identical files are left untouched; changed files are replaced atomically. Only files with this tool's managed marker are replaced. Unmanaged same-name skills, symlinked skill files/directories, and unrelated skills are preserved. Edits to a managed copy are overwritten on the next refresh; keep personal additions in a separate skill.

An automatic refresh failure warns on stderr without preventing an otherwise authorized merge. Explicit `--install-skills` returns exit 1 if either destination cannot be updated; the other destination is still attempted. Set `SKIP_CI_MERGE_SKILLS=1` to disable automatic refresh (for example, in a read-only or ephemeral home). Explicit `--install-skills` still runs when that variable is set. The human-facing command does not automatically install skills unless used in JSON mode.

After first installation or an update:

- **Pi:** run `/reload` or start a new session; invoke explicitly with `/skill:ci-merge-agent`.
- **Claude Code:** skills normally refresh automatically; use `/reload-skills` if the directory is newly created, or restart the session. Invoke explicitly with `/ci-merge-agent`.

Sources: [Pi skills](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md) and [Claude Code skills](https://code.claude.com/docs/en/skills).

Test CI scheduling, agent output, skill synchronization in disposable homes, and merge safeguards with mocked GitHub/Git calls (no real merges):

```bash
uv run --script testing/test-ci-merge-agent.py
```

## Notes

- Scripts call `sudo` only where needed; run as your normal user.
- Package installs use `--needed` to avoid re-installing.
- Audio tweak persistence is provided via `config/wireplumber/wireplumber.conf.d/` (disable profile autoswitch and prefer Bluetooth output as default when connected) and applied to `~/.config/wireplumber/wireplumber.conf.d/`.

## GNOME tray icons (AppIndicator)

On GNOME (especially Wayland), tray icons do not appear unless a StatusNotifier/AppIndicator host is enabled.

This repo includes `gnome-shell-extension-appindicator` in `packages/base.packages` and enables it via `scripts/enable-gnome-extensions.sh` when present.

If tray icons still do not appear after install:

```bash
gsettings get org.gnome.shell disable-user-extensions
gnome-extensions list --enabled | rg appindicator
busctl --user list | rg -i StatusNotifier
```

If `disable-user-extensions` is `true`, run:

```bash
gsettings set org.gnome.shell disable-user-extensions false
./scripts/enable-gnome-extensions.sh
```

Then log out and back in (Wayland session) and re-launch the app.

## Arch Update Indicator (yay + npm)

This repo installs `gnome-shell-extension-arch-update-git` from AUR and applies defaults so the extension:
- checks `yay` updates, global npm updates (when `npm` is installed), and new commits on the personal `mortenvp/agent-stuff` Pi package
- cleans up legacy npm-global files under `/usr` before updating
- runs `yay`, then user-local `npm update -g` only if `yay` succeeds (`NPM_CONFIG_PREFIX=$HOME/.local`, no `sudo`), then refreshes the personal `mortenvp/agent-stuff` Pi package
- avoids persisting npm `prefix`/`globalconfig` in `~/.npmrc`, because those settings break nvm-based AUR builds

If you need to re-apply these settings manually:

```bash
./scripts/configure-gnome-arch-update.sh
```

If an nvm-based AUR package fails with `Your user's .npmrc file has a globalconfig and/or a prefix setting`, clean up the legacy user npm config:

```bash
./scripts/cleanup-npm-global-conflicts.sh
```

Note: this script prefers `gnome-terminal` when available, and for both `gnome-terminal`
and `kgx` it runs npm-global cleanup, then `yay`, then user-local `npm update -g` when available only if `yay` succeeds, then `exec`s into an interactive shell. This avoids landing in a
read-only `Command exited` window after updates.
