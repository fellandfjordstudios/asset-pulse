# Working on the catalogue consumer

Read README.md and the repository brief. Run `tools/setup.sh` before work;
`tools/setup.sh --hooks-only` installs hooks without runtime packages.
Use `tools/check.sh` for isolated packaging checks. Browser checks remain the
separate commands documented in README.md.

The clean library checkout at library.lock supplies the shared studio identity
implementation. Checked-in hooks delegate to it; never bypass either hook or
edit supplier files. Commits carry the studio name and email, unsigned.
Do not rewrite historical authors. Use a topic branch, incorporate current
main, and push normally.

Daily runs, backlog derivation, pin bumps and publication have external effects.
Do not use them as local tests. Do not dispatch workflows, cancel runs or alter
schedules without the owner's instruction. Keep generated assets outside Git.
