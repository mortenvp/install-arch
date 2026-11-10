# Herdr WT worktree layout

Personal copies of [herdrdev/herdr-app](https://github.com/herdrdev/herdr-app)
**v0.1.14**, commit `2405bf388c568c3ed479f05b8e405ccfa44b3f2c`.
Upstream code is Apache-2.0; see `LICENSE`.

Modifications:

- `wt-worktree`: create `<main-checkout>.worktrees/<branch>` using exactly
  `bin/wt-ui`'s branch-folder rules. Resolve the main checkout with Git's
  NUL-delimited worktree list, not an assumed `.git` directory. Explicitly
  target the local machine when opening local spaces, even if focus changed.
- `wt-menu` and `wt-new-menu`: open `wt-worktree` instead of `worktree`.
- `wt-spaces` and `wt-tabs`: open those custom menus.
- `wt` layout: main-layout copy referencing the custom spaces, tabs and
  terminal context menu. Other panels and SVG assets stay upstream-owned.
- Each mod's placement is `none`: only the custom layout/menu chain mounts it.

These are frozen copies, deliberately outside `config/` so the generic config
copy step cannot overwrite them. `scripts/install-herdr-worktrees.sh` owns
installation, checks, backups, activation and removal. It does not modify any
shipped mod, keybinding, repository or existing worktree.

The clone chain is necessary because menu targets are hard-coded upstream:
https://github.com/herdrdev/herdr-app/issues/289

Before refreshing these copies, review native placement support and upstream
changes to all five copied mods, their imported APIs, the main layout and SVG
paths. Do not blindly replace them at every app update. Run the Python/Node
tests, `herdr-app check` through the installer, and exercise both menu entry
points. Retire the customization when native desktop placement matches WT.
