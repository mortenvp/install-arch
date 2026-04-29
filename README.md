# install-arch

Minimal personal Arch setup helper. Inspired by Omarchy, but simplified.

## Structure

- `packages/base.packages`: pacman packages you always want.
- `packages/aur.packages`: AUR packages installed with `yay`.
- `packages/vscode.extensions`: VS Code extensions installed with `code`.
- `config/`: files copied into `~/.config/`.
- `default/`: reserved for dotfiles copied to `$HOME` (currently unused).
- `scripts/`: install/config helpers.
  - Includes upstream installer wrappers for `lix`/`nix`, `devbox`, `uv`, and `tailscale`.
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
1. Install pacman packages from `packages/base.packages`.
2. Install AUR packages from `packages/aur.packages` (requires `yay`), and refresh installed development packages (for example `*-git`) to the latest upstream commits.
3. Detect GPU vendor(s) and auto-install hardware codec packages when available (plus CPU decode baseline packages).
4. Install upstream tools (`lix`/`nix`, `devbox`, `uv`, `tailscale`) via scripts in `scripts/`.
5. Apply configs from `config/` and `default/`.
6. Install VS Code extensions from `packages/vscode.extensions` (if `code` is available).
7. Bind VS Code `Alt+Q` to Rewrap Revived (`rewrap.rewrapComment`) when `code` is available.
8. Apply audio defaults (disable WirePlumber auto-switch to Bluetooth headset profile when recording).
9. Set `kernel.yama.ptrace_scope=0` for debugger attach without repeated superuser prompts (system-wide).
10. Configure global GDB pretty printers in `~/.gdbinit`.
11. Set the default shell to fish.
12. Apply GNOME keybindings, default to 8 workspaces, and set dark mode (if GNOME settings are available).
13. Enable GNOME extensions for Pop Shell, AppIndicator tray support, and Arch Update Indicator (if available).
14. Configure Arch Update Indicator to check/apply updates with `yay` (if installed).
15. Add GNOME autostart entry for `pear-desktop`.
16. Sync GNOME monitor layout to GDM via `/etc/xdg/monitors.xml` and `/var/lib/gdm/.config/monitors.xml`, and install a `gdm.service` drop-in to refresh both before login.

Skip optional steps:

```bash
SKIP_SHELL=1 ./install.sh
SKIP_VSCODE_EXTENSIONS=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
SKIP_GNOME_WORKSPACES=1 ./install.sh
SKIP_GNOME_THEME=1 ./install.sh
SKIP_AUDIO_TWEAKS=1 ./install.sh
SKIP_PTRACE_SCOPE=1 ./install.sh
SKIP_GDB_PRETTY_PRINTERS=1 ./install.sh
SKIP_GDM_MONITORS=1 ./install.sh
SKIP_HW_CODECS=1 ./install.sh
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

## Debugger attach without sudo (ptrace_scope)

`install.sh` runs `scripts/configure-ptrace.sh` by default, which:
- sets `kernel.yama.ptrace_scope=0` immediately
- writes `kernel.yama.ptrace_scope = 0` to `/etc/sysctl.d/10-ptrace.conf` for reboot persistence

Warning: this lowers ptrace isolation system-wide. Use only on trusted development machines.

Opt out for a run:

```bash
SKIP_PTRACE_SCOPE=1 ./install.sh
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
- VS Code keybindings: `scripts/configure-vscode-keybindings.sh` ensures `Alt+Q` is bound to Rewrap Revived (`rewrap.rewrapComment`) in `~/.config/Code/User/keybindings.json`.
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

## Arch Update Indicator (yay)

This repo installs `gnome-shell-extension-arch-update-git` from AUR and applies defaults so the extension uses `yay` for checks and updates.

If you need to re-apply these settings manually:

```bash
./scripts/configure-gnome-arch-update.sh
```
