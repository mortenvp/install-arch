# install-arch

Minimal personal Arch setup helper. Inspired by Omarchy, but simplified.

## Structure

- `packages/base.packages`: pacman packages you always want.
- `packages/aur.packages`: AUR packages installed with `yay`.
- `packages/vscode.extensions`: VS Code extensions installed with `code`.
- `config/`: files copied into `~/.config/`.
- `default/`: reserved for dotfiles copied to `$HOME` (currently unused).
- `scripts/`: install/config helpers.
  - Includes installer/config wrappers for Warp (official Arch pacman repo), Nix, `devbox`, `uv`, and `tailscale`.
- `install.sh`: main entry point.

## Install

Run the top-level installer:

```bash
./install.sh
```

By default, GNOME keybindings use the `laptop` profile (`<Control><Alt>...`).
To switch to the `desktop` profile (`<Alt>...`), run:

```bash
GNOME_KEYBINDINGS_PROFILE=desktop ./install.sh
```

This also controls the Home folder shortcut and overview key:
- `laptop`: home `<Control><Alt>f`, overview `Super`
- `desktop`: home `<Alt>f`, overview `Super_L` (left Super only)

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

Use the GNOME desktop keybinding profile during bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | GNOME_KEYBINDINGS_PROFILE=desktop bash
```

or

```bash
wget -qO- https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | bash
```

This will:
1. Remove an existing Lix install if detected.
2. Install pacman packages from `packages/base.packages`, including Arch's `nix` package.
3. Configure Warp's official pacman repo/signing key and install `warp-terminal`.
4. Install AUR packages from `packages/aur.packages` (requires `yay`), and refresh installed development packages (for example `*-git`) to the latest upstream commits.
5. Detect GPU vendor(s) and auto-install hardware codec packages when available (plus CPU decode baseline packages).
6. On NVIDIA systems, install the DKMS driver/header packages and early-load NVIDIA DRM modules from the initramfs for more reliable monitor detection before GDM starts.
7. Install upstream tools (`devbox`, `uv`, `tailscale`, `@earendil-works/pi-coding-agent`, `playwright`) via scripts in `scripts/`.
8. Apply configs from `config/` and `default/`.
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
19. Apply GNOME keybindings, default to 8 workspaces, set dark mode, and use a 24-hour clock (if GNOME settings are available).
20. Enable GNOME extensions for Pop Shell, GSConnect, AppIndicator tray support, and Arch Update Indicator (if available).
21. Configure Arch Update Indicator to check/apply updates with `yay` (if installed).
22. Add GNOME autostart entry for `pear-desktop`.
23. Sync GNOME monitor layout to GDM via `/etc/xdg/monitors.xml` and `/var/lib/gdm/.config/monitors.xml`, remapping unstable connector names from monitor EDIDs when available, and install a `gdm.service` drop-in to refresh both before login.

Skip optional steps:

```bash
SKIP_LIX_REMOVAL=1 ./install.sh
SKIP_NIX=1 ./install.sh
SKIP_SHELL=1 ./install.sh
SKIP_VSCODE_EXTENSIONS=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
SKIP_GNOME_WORKSPACES=1 ./install.sh
SKIP_GNOME_THEME=1 ./install.sh
SKIP_AUDIO_TWEAKS=1 ./install.sh
SKIP_NVIDIA_DISPLAY=1 ./install.sh
SKIP_PTRACE_SCOPE=1 ./install.sh
SKIP_TCPDUMP_SUDO=1 ./install.sh
SKIP_GDB_PRETTY_PRINTERS=1 ./install.sh
SKIP_GDM_MONITORS=1 ./install.sh
SKIP_HW_CODECS=1 ./install.sh
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
- Warp terminal (Arch): managed by `scripts/install-warp-terminal.sh` (official repo package, not AUR).
- VS Code extensions: add extension IDs to `packages/vscode.extensions`.
- Upstream tools: edit `scripts/install-upstream-tools.sh` and per-tool scripts in `scripts/`.

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

- Fish config: `config/fish/config.fish` (copied to `~/.config/fish/config.fish`).
- Git config: `config/git/config` (copied to `~/.config/git/config`).
- VS Code settings: `config/Code/User/settings.json` merged into `~/.config/Code/User/settings.json` (adds missing keys; prompts on conflicts when interactive; non-interactive runs overwrite conflicting keys with repo defaults).
- VS Code keybindings: `scripts/configure-vscode-keybindings.sh` ensures `Alt+Q` is bound to Rewrap Revived (`rewrap.rewrapComment`) and `Ctrl+Shift+S` is bound to Save All (`workbench.action.files.saveAll`) in `~/.config/Code/User/keybindings.json`.
- OpenCode config: `config/opencode/opencode.json` (copied to `~/.config/opencode/opencode.json`) and includes the Warp plugin (`@warp-dot-dev/opencode-warp`).

Apply configs only:

```bash
./scripts/apply-config.sh
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
- checks both `yay` updates and global npm updates (when `npm` is installed)
- cleans up legacy npm-global files under `/usr` before updating
- runs `yay`, then user-local `npm update -g` only if `yay` succeeds (`NPM_CONFIG_PREFIX=$HOME/.local`, no `sudo`)
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
