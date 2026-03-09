# install-arch

Minimal personal Arch setup helper. Inspired by Omarchy, but simplified.

## Structure

- `packages/base.packages`: pacman packages you always want.
- `packages/aur.packages`: AUR packages installed with `yay`.
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
2. Install AUR packages from `packages/aur.packages` (requires `yay`).
3. Install upstream tools (`lix`/`nix`, `devbox`, `uv`, `tailscale`) via scripts in `scripts/`.
4. Apply configs from `config/` and `default/`.
5. Apply audio defaults (disable WirePlumber auto-switch to Bluetooth headset profile when recording).
6. Set the default shell to fish.
7. Apply GNOME keybindings, default to 8 workspaces, and set dark mode (if GNOME settings are available).
8. Enable GNOME extensions for Pop Shell and AppIndicator tray support (if available).
9. Add GNOME autostart entry for `pear-desktop`.

Skip optional steps:

```bash
SKIP_SHELL=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
SKIP_GNOME_WORKSPACES=1 ./install.sh
SKIP_GNOME_THEME=1 ./install.sh
SKIP_AUDIO_TWEAKS=1 ./install.sh
```

## Add packages

- Pacman: add to `packages/base.packages`.
- AUR: add to `packages/aur.packages`.
- Upstream tools: edit `scripts/install-upstream-tools.sh` and per-tool scripts in `scripts/`.

Then run:

```bash
./scripts/install-all.sh
```

## Config files

- Fish config: `config/fish/config.fish` (copied to `~/.config/fish/config.fish`).
- Git config: `config/git/config` (copied to `~/.config/git/config`).

Apply configs only:

```bash
./scripts/apply-config.sh
```

## Notes

- Scripts call `sudo` only where needed; run as your normal user.
- Package installs use `--needed` to avoid re-installing.

## GNOME tray icons (AppIndicator)

On GNOME (especially Wayland), tray icons do not appear unless a StatusNotifier/AppIndicator host is enabled.

This repo includes `gnome-shell-extension-appindicator` in `packages/base.packages` and enables it via `scripts/enable-gnome-extensions.sh` when present.

If tray icons still do not appear after install:

```bash
gnome-extensions list --enabled | rg appindicator
busctl --user list | rg -i StatusNotifier
```

Then log out and back in (Wayland session) and re-launch the app.
