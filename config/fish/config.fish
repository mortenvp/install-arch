if status is-interactive
    # Commands to run in interactive sessions can go here
end

set -Ux SSH_AUTH_SOCK $XDG_RUNTIME_DIR/gnupg/S.gpg-agent.ssh
alias lg="lazygit"
alias ll="ls -la"

zoxide init fish | source
set -x SSH_AUTH_SOCK /home/mvp/.bitwarden-ssh-agent.sock
