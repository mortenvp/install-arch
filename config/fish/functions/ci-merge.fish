function ci-merge --description 'Wait for CI and safely squash-merge a pull request'
    if not command -q ci-merge-ui
        echo 'ci-merge: ci-merge-ui is not installed or is not on PATH' >&2
        return 127
    end

    command ci-merge-ui $argv
end
