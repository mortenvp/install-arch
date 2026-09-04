function wt --description 'Create or enter a Git worktree'
    if not command -q wt-ui
        echo 'wt: wt-ui is not installed or is not on PATH' >&2
        return 127
    end

    set -l target (command wt-ui $argv)
    set -l wt_status $status
    if test $wt_status -ne 0
        return $wt_status
    end

    if test (count $target) -gt 1
        echo 'wt: wt-ui returned more than one path' >&2
        return 1
    end

    if test -n "$target"
        builtin cd -- "$target"
    end
end
