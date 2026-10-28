#!/usr/bin/env bash
# Audio device dropdown for waybar, built on rofi + pactl.
# Pick an output or input to make it the default and move running streams to it.

# Clicking the icon again closes the popup
pkill -x rofi && exit 0

menu() {
    rofi -dmenu -i -p "$1" -theme-str '
        window   { location: north east; anchor: north east; x-offset: -8px; y-offset: 4px; width: 380px; }
        listview { lines: 10; }
        mainbox  { children: [ inputbar, listview ]; }'
}

device_lines() {
    # $1 = sink|source, $2 = icon. Prints "label|kind:name" lines, current default marked
    local kind="$1" icon="$2" default
    default=$(pactl get-default-"$kind")
    pactl -f json list "${kind}s" | jq -r --arg kind "$kind" --arg def "$default" --arg icon "$icon" '
        .[] | select((.name | test("\\.monitor$")) | not)
            | "\(if .name == $def then "󰄬" else $icon end)  \(.description)|\($kind):\(.name)"'
}

outputs=$(device_lines sink "󰕾")
inputs=$(device_lines source "󰍬")
all=$(printf '%s\n%s\n%s' "$outputs" "$inputs" "󰒓  Sound settings|settings" | sed '/^$/d')

choice=$(cut -d'|' -f1 <<<"$all" | menu "Audio") || exit 0
sel=$(grep -F "$choice|" <<<"$all" | head -n1 | cut -d'|' -f2)

case "$sel" in
    settings) pavucontrol & ;;
    sink:*)
        dev=${sel#sink:}
        pactl set-default-sink "$dev"
        pactl list short sink-inputs | cut -f1 | xargs -r -I{} pactl move-sink-input {} "$dev"
        ;;
    source:*)
        dev=${sel#source:}
        pactl set-default-source "$dev"
        pactl list short source-outputs | cut -f1 | xargs -r -I{} pactl move-source-output {} "$dev"
        ;;
esac
