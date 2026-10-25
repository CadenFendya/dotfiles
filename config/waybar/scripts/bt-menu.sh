#!/usr/bin/env bash
# Windows-style bluetooth popup for waybar, built on rofi + bluetoothctl.

# Clicking the icon again closes the popup
pkill -x rofi && exit 0

menu() {
    rofi -dmenu -i -p "$1" -theme-str '
        window   { location: north east; anchor: north east; x-offset: -8px; y-offset: 4px; width: 340px; }
        listview { lines: 8; }
        mainbox  { children: [ inputbar, listview ]; }'
}

notify() { command -v notify-send >/dev/null && notify-send -a Bluetooth "Bluetooth" "$1"; }

powered() { bluetoothctl show | grep -q "Powered: yes"; }
connected() { bluetoothctl info "$1" | grep -q "Connected: yes"; }

device_lines() {
    # $1 = Paired or "" (all discovered)
    bluetoothctl devices $1 | while read -r _ mac name; do
        if connected "$mac"; then
            echo "󰂱  $name  (connected)|$mac"
        else
            echo "󰂯  $name|$mac"
        fi
    done
}

pick_device() {
    # Shows "label|mac" lines without the mac, returns the mac of the choice
    local lines="$1" prompt="$2" choice
    choice=$(cut -d'|' -f1 <<<"$lines" | menu "$prompt") || return 1
    grep -F "$choice|" <<<"$lines" | head -n1 | cut -d'|' -f2
}

scan_and_pair() {
    notify "Scanning for devices..."
    bluetoothctl --timeout 8 scan on >/dev/null
    local paired all new mac
    paired=$(bluetoothctl devices Paired | awk '{print $2}')
    all=$(device_lines "")
    new=$(grep -vF -f <(printf '%s\n' $paired) <<<"$all")
    [ -z "$new" ] && { notify "No new devices found"; return; }
    mac=$(pick_device "$new" "Pair") || return
    notify "Pairing..."
    bluetoothctl pair "$mac" >/dev/null && bluetoothctl trust "$mac" >/dev/null \
        && bluetoothctl connect "$mac" >/dev/null && notify "Connected" || notify "Pairing failed"
}

if ! powered; then
    choice=$(printf '󰂯  Turn Bluetooth on\n󰒓  Bluetooth settings\n' | menu "Bluetooth (off)") || exit 0
    case "$choice" in
        *"Turn Bluetooth on"*) bluetoothctl power on >/dev/null ;;
        *settings*) blueman-manager & ;;
    esac
    exit 0
fi

devices=$(device_lines Paired)
extras=$'󰂰  Scan for new devices|scan\n󰂲  Turn Bluetooth off|off\n󰒓  Bluetooth settings|settings'
all=$(printf '%s\n%s' "$devices" "$extras" | sed '/^$/d')

sel=$(pick_device "$all" "Bluetooth") || exit 0

case "$sel" in
    scan) scan_and_pair ;;
    off) bluetoothctl power off >/dev/null ;;
    settings) blueman-manager & ;;
    *)
        if connected "$sel"; then
            bluetoothctl disconnect "$sel" >/dev/null && notify "Disconnected"
        else
            notify "Connecting..."
            bluetoothctl connect "$sel" >/dev/null && notify "Connected" || notify "Connection failed"
        fi
        ;;
esac
