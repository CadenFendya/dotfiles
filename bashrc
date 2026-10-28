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

# Animated fetch on terminal start (interactive terminals only)
if [[ $- == *i* && -t 0 && -t 1 ]] && command -v fetch >/dev/null; then
    fetch
fi

# Minimal prompt: current dir + arrow (blue / purple from the kitty theme)
PS1='\[\e[34m\]\w \[\e[35m\]❯\[\e[0m\] '
