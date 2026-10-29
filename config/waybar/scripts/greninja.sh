#!/usr/bin/env bash
# Animates the Greninja sprite in the bar: points $OUT at the next frame in
# ~/.config/waybar/greninja/, and the "image#greninja" module re-reads it.
# Like the old cat, it runs faster the busier the CPU is.
# Prints nothing, so its own "custom/greninja" module stays hidden.

FRAMES=(~/.config/waybar/greninja/frame-*.png)
OUT="${XDG_RUNTIME_DIR:-/run/user/$UID}/waybar-greninja.png"

read_cpu() {
    local _ user nice sys idle
    read -r _ user nice sys idle _ < /proc/stat
    active=$((user + nice + sys)); total=$((active + idle))
}

read_cpu; prev_active=$active; prev_total=$total
while true; do
    read_cpu
    da=$((active - prev_active)); dt=$((total - prev_total))
    prev_active=$active; prev_total=$total
    usage=$(( dt > 0 ? 100 * da / dt : 0 ))
    # 80 ms per frame at idle (the sprite's own speed), down to 30 ms at full load
    delay=$(printf '0.%03d' $(( 80 - usage / 2 )))

    for f in "${FRAMES[@]}"; do
        ln -sfn "$f" "$OUT.tmp" && mv -fT "$OUT.tmp" "$OUT"
        sleep "$delay"
    done
done
