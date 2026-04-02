if status is-interactive
    # Commands to run in interactive sessions can go here
end

set -gx SSH_AUTH_SOCK "$HOME/.bitwarden-ssh-agent.sock"
alias lg="lazygit"
alias ls="lsd --group-dirs=first --icon=always"
alias ll="lsd -la --group-dirs=first --icon=always"
alias c="code . -n"

zoxide init fish | source
