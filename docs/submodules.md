# Submodule-backed assets

Keep submodule pins in your own dotfiles repository and place each linked tree
inside its Etch module. For a repository that previously linked `editors/vim`
to `~/.vim` and `terminals/tmux` to `~/.tmux`, move those trees into module-owned
directories while preserving their Git gitlinks and `.gitmodules` entries:

```text
modules/
  vim/
    module.conf
    files/
      bundle/Vundle.vim/        # Git submodule, not copied plugin files
      pack/.../start/.../       # existing pinned Git submodules
  tmux/
    module.conf
    files/
      plugins/tpm/              # Git submodule
```

Configure the Vim and tmux `link` actions to use `path: "files"` and destinations
`~/.vim` and `~/.tmux`, respectively. Keep each module's regular configuration
files beside its submodules. Git must record the moved paths as gitlinks at the
new locations; changing the directory tree alone does not move the pins.

After cloning the consumer repository, run `git submodule update --init --recursive`
there before `etch plan`, `etch doctor`, or `etch apply`. These commands check the
linked source for missing, uninitialized, and non-pinned submodule revisions and
report the offending path. Etch does not fetch or initialize submodules, and it
does not change the home directory during inspection. An initialized source links
normally; existing destination conflict and repeat-apply rules are unchanged.

`etch import` continues to reject gitlinks. Import copies a self-contained
module snapshot and cannot preserve a submodule pin without adding a separate
Git dependency and checkout policy. Keep these modules in the consumer repository
and initialize them with Git instead of importing them.
