#!/usr/bin/env bash
# Rebuilds the whole setup on a fresh Fedora install.
#   git clone https://github.com/<you>/dotfiles ~/dotfiles && ~/dotfiles/install.sh
# Safe to re-run. Existing files get moved to ~/.dotfiles-backup/<timestamp>/.
set -euo pipefail

DOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"

step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

# Symlink $1 (in repo) to $2, backing up whatever was there
link() {
    local src="$DOT/$1" dst="$2"
    mkdir -p "$(dirname "$dst")"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then return; fi
    if [ -e "$dst" ] || [ -L "$dst" ]; then
        mkdir -p "$BACKUP/$(dirname "${dst#$HOME/}")"
        mv "$dst" "$BACKUP/${dst#$HOME/}"
    fi
    ln -s "$src" "$dst"
    echo "  linked ${dst/#$HOME/\~}"
}

if [ "${1:-}" != "--links-only" ]; then
    step "Enabling repos (Hyprland COPR, RPM Fusion, VS Code)"
    sudo dnf install -y dnf-plugins-core
    sudo dnf copr enable -y sdegler/hyprland
    if ! rpm -q rpmfusion-free-release rpmfusion-nonfree-release >/dev/null; then
        sudo dnf install -y \
            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm" \
            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
    fi
    if [ ! -f /etc/yum.repos.d/vscode.repo ]; then
        sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
        printf '[code]\nname=Visual Studio Code\nbaseurl=https://packages.microsoft.com/yumrepos/vscode\nenabled=1\nautorefresh=1\ntype=rpm-md\ngpgcheck=1\ngpgkey=https://packages.microsoft.com/keys/microsoft.asc\n' \
            | sudo tee /etc/yum.repos.d/vscode.repo >/dev/null
    fi

    step "Installing packages"
    sudo dnf upgrade -y --refresh
    grep -vE '^\s*(#|$)' "$DOT/packages.txt" | xargs sudo dnf install -y

    step "Installing flatpaks"
    sudo flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    grep -vE '^\s*(#|$)' "$DOT/flatpaks.txt" | xargs -r sudo flatpak install -y --noninteractive flathub
fi

step "Linking configs"
for d in hypr waybar rofi foot fastfetch fetch waypaper images cava; do
    link "config/$d" "$HOME/.config/$d"
done
link config/gtk3-bookmarks "$HOME/.config/gtk-3.0/bookmarks"
link bin/setwall "$HOME/.local/bin/setwall"
link bashrc "$HOME/.bashrc"

[ "${1:-}" = "--links-only" ] && { echo "Done (links only)."; exit 0; }

step "Wallpapers"
mkdir -p "$HOME/Pictures/Wallpaper"
cp -n "$DOT"/wallpapers/* "$HOME/Pictures/Wallpaper/"

step "Fonts"
FONTS="$HOME/.local/share/fonts"
mkdir -p "$FONTS/rice"
cp -n "$DOT"/fonts/rice/* "$FONTS/rice/"
if [ ! -d "$FONTS/IosevkaNerdFont" ]; then
    mkdir -p "$FONTS/IosevkaNerdFont"
    curl -fL https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Iosevka.tar.xz \
        | tar -xJ -C "$FONTS/IosevkaNerdFont"
fi
fc-cache -f >/dev/null

step "Building fetch (github.com/areofyl/fetch)"
if ! command -v fetch >/dev/null; then
    tmp="$(mktemp -d)"
    git clone --depth 1 https://github.com/areofyl/fetch "$tmp/fetch"
    make -C "$tmp/fetch"
    install -Dm755 "$tmp/fetch/fetch" "$HOME/.local/bin/fetch"
    rm -rf "$tmp"
fi

step "Bluetooth"
sudo systemctl enable --now bluetooth

step "VS Code extensions"
if [ -s "$DOT/vscode/extensions.txt" ]; then
    xargs -n1 code --install-extension < "$DOT/vscode/extensions.txt"
fi

step "Claude Code"
command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash

step "Done! Reboot, then pick Hyprland at the login screen."
[ -d "$BACKUP" ] && echo "Old files were backed up to $BACKUP"
