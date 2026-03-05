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

or

```bash
wget -qO- https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh | bash
```

This will:
1. Install pacman packages from `packages/base.packages`.
2. Install AUR packages from `packages/aur.packages` (requires `yay`).
3. Install upstream tools (`lix`/`nix`, `devbox`, `uv`, `tailscale`) via scripts in `scripts/`.
4. Apply configs from `config/` and `default/`.
5. Set the default shell to fish.
6. Enable the Pop Shell GNOME extension (if GNOME + extension are present).

Skip optional steps:

```bash
SKIP_SHELL=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
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
