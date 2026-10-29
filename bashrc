# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
  . /etc/bashrc
fi

# User specific environment
if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then
  PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi
export PATH

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions
if [ -d ~/.bashrc.d ]; then
  for rc in ~/.bashrc.d/*; do
    if [ -f "$rc" ]; then
      . "$rc"
    fi
  done
fi
unset rc

# Animated pokemon fastfetch on terminal start (interactive terminals only).
# Run `poke-sprites` once to download the sprites; the old spinning `fetch` is still installed.
if [[ $- == *i* && -t 0 && -t 1 ]] && command -v pokefetch >/dev/null; then
  pokefetch 658
fi

# Minimal prompt: current dir + arrow (both blue from the kitty theme)
PS1='\[\e[34m\]\w \[\e[34m\]❯\[\e[0m\] '
