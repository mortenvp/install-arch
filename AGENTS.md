# Agent guide for install-arch

This repo is a personal Arch Linux setup/install script.

## Important safety rules

- Do not run `./install.sh` on the host unless explicitly asked.
- Prefer static checks before attempting any install steps.
- Scripts should be safe to re-run/idempotent where practical.
- Avoid interactive prompts; use noninteractive flags where possible.
- Top-level `install.sh` must be run as a normal user, not root.
- Never commit or hard-code secrets, API keys, tokens, private keys, passwords, host-specific credentials, or other personal/private information.
- Use placeholders or documented environment variables for anything sensitive.

## Repo structure

- `boot.sh`: online bootstrap entry point used by curl/wget.
- `install.sh`: main installer.
- `scripts/`: individual install/configuration steps.
- `packages/base.packages`: official pacman packages only.
- `packages/aur.packages`: AUR packages only.
- `packages/vscode.extensions`: VS Code extensions.
- `config/`: files copied into `~/.config`.
- `testing/`: validation scripts.

## Style/conventions

- Bash scripts use:

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  ```

- Shared logging comes from `scripts/logging.sh`.
- Prefer small focused scripts in `scripts/`.
- Keep package installation logic separate from configuration logic.
- Keep skip flags in the form `SKIP_SOMETHING=1`.
- Document new environment variables in `README.md`.

## Fast checks

Run these before/after changes:

```bash
bash -n boot.sh install.sh scripts/*.sh testing/*.sh
shellcheck boot.sh install.sh scripts/*.sh testing/*.sh
```

On Arch, also run:

```bash
./testing/check-base-packages.sh
```

## Common skip flags

Examples:

```bash
SKIP_VSCODE_EXTENSIONS=1 ./install.sh
SKIP_GNOME_EXTENSIONS=1 ./install.sh
SKIP_HW_CODECS=1 ./install.sh
SKIP_NVIDIA_DISPLAY=1 ./install.sh
SKIP_GDM_MONITORS=1 ./install.sh
```

## User preferences

- Target OS: Arch Linux.
- Desktop: GNOME.
- AUR helper: yay.
- Keep this repo simple and personal, not a generic distro installer.
