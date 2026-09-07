#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

detect_gnome_keybindings_profile() {
  local sysfs="${1:-/sys}" chassis='' supply type scope

  if [[ -r "$sysfs/class/dmi/id/chassis_type" ]]; then
    IFS= read -r chassis < "$sysfs/class/dmi/id/chassis_type" || true
  fi
  case "$chassis" in
    # SMBIOS portable, laptop, notebook, handheld, sub-notebook, tablet,
    # convertible, and detachable chassis types (including docked laptops).
    8|9|10|11|14|30|31|32)
      printf 'laptop\n'
      return
      ;;
    3|4|5|6|7|13|15|16|23|24|35|36)
      printf 'desktop\n'
      return
      ;;
  esac

  # Fall back to a system battery when DMI is missing or inconclusive.
  # Ignore batteries belonging to peripherals such as mice and keyboards.
  for supply in "$sysfs"/class/power_supply/*; do
    [[ -r "$supply/type" ]] || continue
    type='' scope=''
    IFS= read -r type < "$supply/type" || true
    if [[ -r "$supply/scope" ]]; then
      IFS= read -r scope < "$supply/scope" || true
    fi
    if [[ "$type" == Battery && "$scope" != Device ]]; then
      printf 'laptop\n'
      return
    fi
  done

  printf 'desktop\n'
}

prompt_gnome_keybindings_profile() {
  local profile="$1" tty_fd="$2" key sequence option label

  printf '\n\033[1mGNOME keybindings\033[0m\n' >&"$tty_fd"
  printf 'Hardware guess: %s\n' "$profile" >&"$tty_fd"
  printf 'Use Up/Down to select, Enter to confirm, Esc to cancel.\n\n' >&"$tty_fd"

  while true; do
    for option in laptop desktop; do
      case "$option" in
        laptop) label='Laptop   Ctrl+Alt shortcuts | Super overview' ;;
        desktop) label='Desktop  Alt shortcuts      | Left Super overview' ;;
      esac
      if [[ "$option" == "$profile" ]]; then
        printf '\033[2K\033[1;36m  > %s\033[0m\n' "$label" >&"$tty_fd"
      else
        printf '\033[2K    %s\n' "$label" >&"$tty_fd"
      fi
    done

    if ! IFS= read -r -s -n 1 -u "$tty_fd" key; then
      printf '\nSelection cancelled.\n' >&"$tty_fd"
      return 1
    fi
    case "$key" in
      '') break ;;
      $'\e')
        sequence=''
        IFS= read -r -s -n 2 -t 0.2 -u "$tty_fd" sequence || true
        case "$sequence" in
          '[A'|'OA') profile=laptop ;;
          '[B'|'OB') profile=desktop ;;
          '')
            printf '\nSelection cancelled.\n' >&"$tty_fd"
            return 1
            ;;
        esac
        ;;
    esac
    printf '\033[2A' >&"$tty_fd"
  done

  printf '\n' >&"$tty_fd"
  printf '%s\n' "$profile"
}

select_gnome_keybindings_profile() {
  local profile="${GNOME_KEYBINDINGS_PROFILE:-}" tty_fd

  if [[ -n "$profile" ]]; then
    case "$profile" in
      laptop|desktop) printf '%s\n' "$profile" ;;
      *)
        printf "Error: Unsupported GNOME_KEYBINDINGS_PROFILE '%s'. Supported values: laptop, desktop.\n" "$profile" >&2
        return 1
        ;;
    esac
    return
  fi

  profile=$(detect_gnome_keybindings_profile)
  # Use the controlling terminal, not stdin: boot.sh can be piped into bash,
  # and the selected profile is captured from stdout by the calling script.
  if [[ "${TERM:-dumb}" == dumb ]] || ! { exec {tty_fd}<>/dev/tty; } 2>/dev/null; then
    log_step "No interactive terminal; using GNOME keybindings profile: $profile" >&2
    printf '%s\n' "$profile"
    return
  fi

  profile=$(prompt_gnome_keybindings_profile "$profile" "$tty_fd") || {
    exec {tty_fd}>&-
    return 1
  }
  exec {tty_fd}>&-
  log_step "Selected GNOME keybindings profile: $profile" >&2
  printf '%s\n' "$profile"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  select_gnome_keybindings_profile
fi
