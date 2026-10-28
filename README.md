# dotfiles

My Fedora + Hyprland setup (lavender rice: waybar, rofi, kitty, fastfetch, fetch, plus LazyVim and btop).

## Fresh install

1. Install Fedora Workstation, log in, connect to Wi-Fi.
2. Open a terminal and run:

   ```bash
   sudo dnf install -y git
   git clone https://github.com/CadenFendya/dotfiles ~/dotfiles
   ~/dotfiles/install.sh
   ```

3. Reboot, choose **Hyprland** at the login screen (gear icon), log in.

The script enables RPM Fusion, installs every package in `packages.txt` and
every Flathub app in `flatpaks.txt`, symlinks the configs from
this repo into `~/.config`, installs fonts (downloads Iosevka Nerd Font) and
wallpapers, builds `fetch` from source, installs lazygit, turns on Bluetooth, and installs VS Code
extensions and Claude Code. Anything it replaces is backed up to
`~/.dotfiles-backup/`.

## Keybinds

See [KEYBINDS.md](KEYBINDS.md).

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

## Controller not working in Steam games

Symptom: the controller works in Steam (Xbox button opens the overlay) but does
nothing in any game. Every game here runs through Proton.

Cause: OpenRGB's udev rules make the NZXT Kraken M22 / Smart Device V2 and MSI
Mystic Light hidraw devices readable by my user. Proton's `winebus` hangs while
setting them up (`winebus failed to start: 1053` in a `PROTON_LOG=1` log), so it
never gets to the controller.

Fix: `config/hypr/hyprland.lua` sets

```
PROTON_DISABLE_HIDRAW=0x1E71/0x2006,0x1E71/0x1715,0x1462/0x7D31
```

so Proton skips those devices. Log out and back in after changing it. If new
RGB/cooler hardware breaks controllers again, add its `VID/PID` (from `lsusb`)
to that list. To debug, set a game's launch options to
`PROTON_LOG=1 WINEDEBUG=+hid,+plugplay %command%` and read `~/steam-<appid>.log`.
