# install-arch

Minimal personal Arch setup helper. Inspired by Omarchy, but simplified.

## Structure

- `packages/base.packages`: pacman packages you always want.
- `packages/aur.packages`: AUR packages installed with `yay`.
- `config/`: files copied into `~/.config/`.
- `default/`: reserved for dotfiles copied to `$HOME` (currently unused).
- `scripts/`: install/config helpers.
- `install.sh`: main entry point.

## Install

Run the top-level installer:

```bash
./install.sh
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
3. Apply configs from `config/` and `default/`.
4. Set the default shell to fish.
5. Enable the Pop Shell GNOME extension (if GNOME + extension are present).

Skip optional steps:

```bash
SKIP_SHELL=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
```

## Add packages

- Pacman: add to `packages/base.packages`.
- AUR: add to `packages/aur.packages`.

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
