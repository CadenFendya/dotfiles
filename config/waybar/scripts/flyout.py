#!/usr/bin/env python3
"""Windows-style flyouts for waybar: `flyout.py volume|tray|bluetooth|power`.

Opens under the cursor, closes when the mouse leaves (or on Esc / clicking the
button again). Built on GTK3 + gtk-layer-shell, styled to match the bar.
"""
import json
import os
import re
import signal
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("DbusmenuGtk3", "0.4")
from gi.repository import DbusmenuGtk3, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "volume"
PIDFILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "waybar-flyout.pid")
CLOSE_GRACE_MS = 350  # how long the mouse can be outside before closing

CSS = b"""
* { font-family: "Iosevka Nerd Font", monospace; font-size: 13px; color: #ffffff; }
window { background: rgba(0, 0, 0, 0.85); }
.flyout { padding: 10px; }
.heading { color: #777777; font-size: 11px; font-weight: 800; margin: 8px 2px 2px; }
button { background: transparent; border: none; border-radius: 0; box-shadow: none;
         padding: 6px 8px; text-shadow: none; -gtk-icon-shadow: none; }
button:hover { background: #222222; }
button.active label { font-weight: 800; }
button.dim label { color: #aaaaaa; }
scale { padding: 0 6px; }
scale trough { min-height: 4px; border-radius: 0; border: none; background: rgba(255,255,255,0.15); }
scale highlight { border-radius: 0; background: #ffffff; }
scale slider { min-width: 12px; min-height: 12px; margin: -4px; border-radius: 0;
               border: none; background: #ffffff; box-shadow: none; }
.pct { min-width: 38px; }
switch { border-radius: 0; border: none; background: rgba(255,255,255,0.15); min-height: 18px; }
switch:checked { background: #ffffff; }
switch slider { border-radius: 0; border: none; background: #777777; box-shadow: none; min-width: 18px; }
switch:checked slider { background: #000000; }
button:disabled label { color: #555555; }
"""


def run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def hypr(cmd):
    return json.loads(run("hyprctl", "-j", cmd) or "null")


def toggle_existing():
    """Close any open flyout. Returns True if it was this same flyout (i.e. a toggle-off)."""
    try:
        with open(PIDFILE) as f:
            pid, mode = f.read().split()
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            if b"flyout.py" not in f.read():
                return False
        os.kill(int(pid), signal.SIGTERM)
        return mode == MODE
    except (OSError, ValueError):
        return False


class Flyout(Gtk.Window):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.menu_open = False
        self.outside_ms = 0

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_namespace(self, "waybar-flyout")
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        self.connect("key-press-event", lambda _w, e: e.keyval == 0xff1b and self.close())
        self.connect("destroy", Gtk.main_quit)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.box.get_style_context().add_class("flyout")
        self.box.set_size_request(width, -1)
        self.add(self.box)

    def place(self):
        """Center under the cursor, clamped to the screen edge."""
        cur = hypr("cursorpos")
        mon = next(m for m in hypr("monitors") if m["focused"])
        bar = next((l for out in hypr("layers").values() for lvl in out["levels"].values()
                    for l in lvl if l["namespace"] == "waybar"), {"h": 30})
        self.click_x = cur["x"] - mon["x"]
        self.mon_w, self.bar_h = mon["width"], bar["h"]
        right = max(4, min(self.mon_w - self.click_x - self.width // 2, self.mon_w - self.width - 4))
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, right)
        self.left = self.mon_w - right - self.width
        self.mon_x = mon["x"]

    def start(self):
        self.place()
        self.show_all()
        GLib.timeout_add(100, self.watch_pointer)

    def watch_pointer(self):
        """Close once the cursor leaves the flyout (or the button it came from)."""
        if self.menu_open:
            self.outside_ms = 0
            return True
        cur = hypr("cursorpos")
        x, y = cur["x"] - self.mon_x, cur["y"]
        h = self.get_allocated_height()
        in_flyout = self.left - 8 <= x <= self.left + self.width + 8 and y <= self.bar_h + h + 8
        in_button = abs(x - self.click_x) <= 30 and y <= self.bar_h
        self.outside_ms = 0 if (in_flyout or in_button) else self.outside_ms + 100
        if self.outside_ms >= CLOSE_GRACE_MS:
            self.close()
            return False
        return True

    def heading(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("heading")
        self.box.pack_start(label, False, False, 0)

    def popup_menu(self, menu):
        self.menu_open = True
        menu.connect("deactivate", lambda _m: GLib.timeout_add(150, self.after_menu))
        menu.popup_at_pointer(None)

    def after_menu(self):
        self.menu_open = False
        return False


# ---------------------------------------------------------------- volume ----

class VolumeFlyout(Flyout):
    def __init__(self):
        super().__init__(320)
        self.updating = False

        row = Gtk.Box(spacing=4)
        self.mute_btn = Gtk.Button()
        self.mute_btn.connect("clicked", lambda _b: self.set_mute())
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self.on_scale)
        self.pct = Gtk.Label(xalign=1)
        self.pct.get_style_context().add_class("pct")
        row.pack_start(self.mute_btn, False, False, 0)
        row.pack_start(self.scale, True, True, 0)
        row.pack_start(self.pct, False, False, 0)
        self.box.pack_start(row, False, False, 0)

        self.devices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.pack_start(self.devices, False, False, 0)

        settings = Gtk.Button(label="󰒓  Sound settings", xalign=0)
        settings.get_style_context().add_class("dim")
        settings.get_child().set_xalign(0)
        settings.connect("clicked", lambda _b: (subprocess.Popen(["pavucontrol"]), self.close()))
        self.box.pack_start(settings, False, False, 4)

        self.refresh_volume()
        self.build_devices()
        GLib.timeout_add(500, self.refresh_volume)

    def refresh_volume(self):
        out = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@").split()
        vol = round(float(out[1]) * 100) if len(out) > 1 else 0
        muted = "[MUTED]" in out
        self.updating = True
        if not self.scale.has_grab():
            self.scale.set_value(vol)
        self.updating = False
        self.pct.set_text(f"{int(self.scale.get_value())}%")
        icon = "󰝟" if muted else "󰕿" if vol < 34 else "󰖀" if vol < 67 else "󰕾"
        self.mute_btn.set_label(icon)
        return True

    def on_scale(self, scale):
        self.pct.set_text(f"{int(scale.get_value())}%")
        if not self.updating:
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{int(scale.get_value())}%"])

    def set_mute(self):
        run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
        self.refresh_volume()

    def build_devices(self):
        for child in self.devices.get_children():
            child.destroy()
        for kind, title, icon in (("sink", "OUTPUT", "󰕾"), ("source", "INPUT", "󰍬")):
            label = Gtk.Label(label=title, xalign=0)
            label.get_style_context().add_class("heading")
            self.devices.pack_start(label, False, False, 0)
            default = run("pactl", "get-default-" + kind).strip()
            for dev in json.loads(run("pactl", "-f", "json", "list", kind + "s") or "[]"):
                if dev["name"].endswith(".monitor"):
                    continue
                active = dev["name"] == default
                btn = Gtk.Button(label=f"{'󰄬' if active else icon}  {dev['description']}")
                btn.get_child().set_xalign(0)
                btn.get_child().set_ellipsize(3)  # Pango.EllipsizeMode.END
                btn.get_style_context().add_class("active" if active else "dim")
                btn.connect("clicked", lambda _b, k=kind, n=dev["name"]: self.switch(k, n))
                self.devices.pack_start(btn, False, False, 0)
        self.devices.show_all()

    def switch(self, kind, name):
        run("pactl", "set-default-" + kind, name)
        streams, move = (("sink-inputs", "move-sink-input") if kind == "sink"
                         else ("source-outputs", "move-source-output"))
        for line in run("pactl", "list", "short", streams).splitlines():
            run("pactl", move, line.split()[0], name)
        self.build_devices()
        self.refresh_volume()


# ------------------------------------------------------------------ tray ----

class TrayFlyout(Flyout):
    ICON = 22

    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        items = self.watcher_items()
        cols = max(1, min(len(items), 5))
        super().__init__(cols * (self.ICON + 22) + 20)

        grid = Gtk.FlowBox(max_children_per_line=cols, min_children_per_line=cols,
                           selection_mode=Gtk.SelectionMode.NONE, homogeneous=True)
        self.box.pack_start(grid, False, False, 0)
        if not items:
            self.box.pack_start(Gtk.Label(label="No apps"), False, False, 6)
        for item in items:
            btn = self.item_button(item)
            if btn:
                grid.add(btn)

    def watcher_items(self):
        try:
            res = self.bus.call_sync(
                "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")),
                None, Gio.DBusCallFlags.NONE, 1000, None)
            return res.unpack()[0]
        except GLib.Error:
            return []

    def item_button(self, item):
        name, _, path = item.partition("/")
        path = "/" + path if path else "/StatusNotifierItem"
        try:
            props = self.bus.call_sync(
                name, path, "org.freedesktop.DBus.Properties", "GetAll",
                GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)),
                None, Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]
        except GLib.Error:
            return None

        btn = Gtk.Button()
        btn.set_image(self.item_icon(props))
        btn.set_always_show_image(True)
        tip = props.get("ToolTip")
        title = (tip[2] if tip and tip[2] else None) or props.get("Title") or props.get("Id", "")
        btn.set_tooltip_text(title)

        menu = None
        if props.get("Menu"):
            menu = DbusmenuGtk3.Menu.new(name, props["Menu"])
            menu.attach_to_widget(btn, None)

        def call(method, x=0, y=0):
            self.bus.call(name, path, "org.kde.StatusNotifierItem", method,
                          GLib.Variant("(ii)", (x, y)), None, Gio.DBusCallFlags.NONE, 1000, None,
                          None, None)

        def on_press(_w, event):
            if event.button == 1 and not props.get("ItemIsMenu", False):
                call("Activate", int(event.x_root), int(event.y_root))
                self.close()
            elif event.button == 2:
                call("SecondaryActivate", int(event.x_root), int(event.y_root))
            elif menu is not None:
                self.popup_menu(menu)
            else:
                call("ContextMenu", int(event.x_root), int(event.y_root))
            return True

        btn.connect("button-press-event", on_press)
        return btn

    def item_icon(self, props):
        theme = Gtk.IconTheme.get_default()
        if props.get("IconThemePath"):
            theme.append_search_path(props["IconThemePath"])
        icon_name = props.get("IconName")
        if icon_name:
            if os.path.isabs(icon_name) and os.path.exists(icon_name):
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_name, self.ICON, self.ICON)
                return Gtk.Image.new_from_pixbuf(pb)
            if theme.has_icon(icon_name):
                pb = theme.load_icon(icon_name, self.ICON, Gtk.IconLookupFlags.FORCE_SIZE)
                return Gtk.Image.new_from_pixbuf(pb)
        pixmaps = props.get("IconPixmap") or []
        if pixmaps:
            w, h, data = max(pixmaps, key=lambda p: p[0] * p[1])
            data = bytearray(data)
            for i in range(0, len(data), 4):  # ARGB (network order) -> RGBA
                a, r, g, b = data[i:i + 4]
                data[i:i + 4] = bytes((r, g, b, a))
            pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(data)),
                                                 GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
            pb = pb.scale_simple(self.ICON, self.ICON, GdkPixbuf.InterpType.BILINEAR)
            return Gtk.Image.new_from_pixbuf(pb)
        return Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.LARGE_TOOLBAR)


# ------------------------------------------------------------- bluetooth ----

def in_background(work, done):
    """Run slow bluetoothctl calls off the UI thread, then call done(result) on it."""
    threading.Thread(target=lambda: GLib.idle_add(done, work()), daemon=True).start()


class BluetoothFlyout(Flyout):
    def __init__(self):
        super().__init__(300)
        self.busy = set()  # MACs with a connect/pair in progress
        self.found = []    # (mac, name) from the last scan

        row = Gtk.Box(spacing=8)
        title = Gtk.Label(label="󰂯  Bluetooth", xalign=0)
        self.power = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.power.connect("state-set", self.on_power)
        row.pack_start(title, True, True, 2)
        row.pack_start(self.power, False, False, 2)
        self.box.pack_start(row, False, False, 4)

        self.devices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.pack_start(self.devices, False, False, 0)

        self.scan_btn = self.action_button("󰂰  Scan for devices", self.scan)
        self.action_button("󰒓  Bluetooth settings",
                           lambda: (subprocess.Popen(["blueman-manager"]), self.close()))
        self.build()

    def action_button(self, label, callback):
        btn = Gtk.Button(label=label)
        btn.get_child().set_xalign(0)
        btn.get_style_context().add_class("dim")
        btn.connect("clicked", lambda _b: callback())
        self.box.pack_start(btn, False, False, 0)
        return btn

    @staticmethod
    def powered():
        return "Powered: yes" in run("bluetoothctl", "show")

    @staticmethod
    def device_list(which):
        out = run("bluetoothctl", "devices", *([which] if which else []))
        return [(p[1], p[2]) for p in (l.split(" ", 2) for l in out.splitlines())
                if len(p) == 3 and p[0] == "Device"]

    @staticmethod
    def info(mac):
        text = run("bluetoothctl", "info", mac)
        battery = re.search(r"Battery Percentage: \S+ \((\d+)\)", text)
        return "Connected: yes" in text, battery.group(1) if battery else None

    def build(self):
        for child in self.devices.get_children():
            child.destroy()
        on = self.powered()
        self.power.handler_block_by_func(self.on_power)
        self.power.set_active(on)
        self.power.handler_unblock_by_func(self.on_power)
        self.scan_btn.set_sensitive(on)

        if not on:
            self.note("Bluetooth is off")
        else:
            paired = self.device_list("Paired")
            self.section("PAIRED", paired, paired=True)
            known = {mac for mac, _ in paired}
            self.section("AVAILABLE", [d for d in self.found if d[0] not in known], paired=False)
            if not paired and not self.found:
                self.note("No devices yet - try scanning")
        self.devices.show_all()

    def note(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("heading")
        self.devices.pack_start(label, False, False, 4)

    def section(self, title, devices, paired):
        if not devices:
            return
        label = Gtk.Label(label=title, xalign=0)
        label.get_style_context().add_class("heading")
        self.devices.pack_start(label, False, False, 0)
        for mac, name in devices:
            connected, battery = self.info(mac) if paired else (False, None)
            if mac in self.busy:
                text = f"󰂳  {name}  …"
            elif connected:
                text = f"󰂱  {name}" + (f"  {battery}%" if battery else "")
            else:
                text = f"󰂯  {name}"
            btn = Gtk.Button(label=text)
            btn.get_child().set_xalign(0)
            btn.get_child().set_ellipsize(3)
            btn.get_style_context().add_class("active" if connected else "dim")
            btn.set_tooltip_text("Click to disconnect" if connected
                                 else "Click to connect" if paired else "Click to pair")
            btn.connect("clicked", lambda _b, m=mac, c=connected, p=paired: self.on_device(m, c, p))
            self.devices.pack_start(btn, False, False, 0)

    def on_power(self, _switch, state):
        run("bluetoothctl", "power", "on" if state else "off")
        if not state:
            self.found = []
        GLib.timeout_add(300, lambda: self.build() or False)
        return False

    def on_device(self, mac, connected, paired):
        if mac in self.busy:
            return
        if connected:
            steps = [["disconnect", mac]]
        elif paired:
            steps = [["connect", mac]]
        else:
            steps = [["pair", mac], ["trust", mac], ["connect", mac]]
        self.busy.add(mac)
        self.build()

        def work():
            for step in steps:
                subprocess.run(["bluetoothctl", "--timeout", "15", *step], capture_output=True)

        def done(_):
            self.busy.discard(mac)
            self.build()

        in_background(work, done)

    def scan(self):
        self.scan_btn.set_label("󰂰  Scanning…")
        self.scan_btn.set_sensitive(False)

        def work():
            subprocess.run(["bluetoothctl", "--timeout", "8", "scan", "on"], capture_output=True)
            # skip unnamed devices, which bluetoothctl lists by their address
            return [(m, n) for m, n in self.device_list(None) if n.replace("-", ":") != m]

        def done(found):
            self.found = found
            self.scan_btn.set_label("󰂰  Scan for devices")
            self.build()

        in_background(work, done)


# ----------------------------------------------------------------- power ----

class PowerFlyout(Flyout):
    # (label, command, needs confirmation)
    ACTIONS = (
        ("󰌾  Lock", ["sh", "-c", "pidof hyprlock || hyprlock"], False),
        ("󰤄  Suspend", ["systemctl", "suspend"], False),
        ("󰍃  Log out", ["hyprctl", "dispatch", "hl.dsp.exit()"], True),
        ("󰜉  Reboot", ["systemctl", "reboot"], True),
        ("󰐥  Shut down", ["systemctl", "poweroff"], True),
    )

    def __init__(self):
        super().__init__(200)
        self.armed = None  # button waiting for a second click to confirm
        for label, cmd, confirm in self.ACTIONS:
            btn = Gtk.Button(label=label)
            btn.get_child().set_xalign(0)
            btn.connect("clicked", lambda b, l=label, c=cmd, k=confirm: self.on_action(b, l, c, k))
            self.box.pack_start(btn, False, False, 0)

    def on_action(self, btn, label, cmd, confirm):
        if confirm and self.armed is not btn:
            if self.armed:
                self.armed.set_label(self.armed.original)
            btn.original = label
            btn.set_label(f"{label.split()[0]}  Click again to {label.split('  ', 1)[1].lower()}")
            self.armed = btn
            return
        self.close()
        subprocess.Popen(cmd)


def main():
    if toggle_existing():
        return
    with open(PIDFILE, "w") as f:
        f.write(f"{os.getpid()} {MODE}")
    try:
        win = {"tray": TrayFlyout, "bluetooth": BluetoothFlyout, "power": PowerFlyout}.get(MODE, VolumeFlyout)()
        signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(win.close))
        win.start()
        Gtk.main()
    finally:
        try:
            with open(PIDFILE) as f:
                if f.read().split()[0] == str(os.getpid()):
                    os.remove(PIDFILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
