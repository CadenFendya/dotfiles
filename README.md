# dotfiles

My Fedora + Hyprland setup (lavender rice: waybar, rofi, foot, fastfetch, fetch).

## Fresh install

1. Install Fedora Workstation, log in, connect to Wi-Fi.
2. Open a terminal and run:

   ```bash
   sudo dnf install -y git
   git clone https://github.com/USERNAME/dotfiles ~/dotfiles
   ~/dotfiles/install.sh
   ```

3. Reboot, choose **Hyprland** at the login screen (gear icon), log in.

The script enables RPM Fusion, installs every package in `packages.txt` and
every Flathub app in `flatpaks.txt`, symlinks the configs from
this repo into `~/.config`, installs fonts (downloads Iosevka Nerd Font) and
wallpapers, builds `fetch` from source, turns on Bluetooth, and installs VS Code
extensions and Claude Code. Anything it replaces is backed up to
`~/.dotfiles-backup/`.

## Day to day

Configs in `~/.config` are symlinks into `~/dotfiles`, so edits land in the repo
automatically. To save them:

```bash
cd ~/dotfiles && git add -A && git commit -m "update" && git push
```

`./install.sh --links-only` re-creates just the symlinks.

## Real-hardware notes

This was built in a VMware VM. On a real PC, in `config/hypr/hyprland.lua`:

- `scale = 1` in the monitor block: try `"auto"` on a HiDPI laptop screen.
- `no_hardware_cursors = true` was a VMware workaround; it's harmless, but you
  can set it to `false` (keep it `true` if you have an NVIDIA card).
- NVIDIA GPU: enable RPM Fusion and install `akmod-nvidia` before using Hyprland.
