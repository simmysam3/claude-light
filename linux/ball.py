#!/usr/bin/python3
"""claude-light ball for Linux: the lamp, drawn on the Wayland overlay layer (Hyprland/Omarchy,
Sway, KDE, ... via gtk4-layer-shell), pinned top-right, never taking keyboard focus.
A renderer of display.json; every decision lives in ../src (lightd.py decides, lightctl.py writes
the settings). The Linux "tray" is a Waybar module: `claude-light waybar --follow` / `claude-light menu`.

  ball.py <display.json> <bong.wav>

Needs (Arch / Omarchy): sudo pacman -S --needed python-gobject python-cairo gtk4 gtk4-layer-shell
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time
from ctypes import CDLL

try:
    CDLL("libgtk4-layer-shell.so")   # must be loaded before GTK (gtk4-layer-shell's Python rule)
    HAVE_LAYER_LIB = True
except OSError:
    HAVE_LAYER_LIB = False

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
LayerShell = None
if HAVE_LAYER_LIB:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402
    except (ValueError, ImportError):
        LayerShell = None
import cairo  # noqa: E402
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, PangoCairo  # noqa: E402

try:
    gi.require_foreign("cairo")   # lets GTK take a cairo.Region (the click-through input region)
except ImportError:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "src"))
import fsutil  # noqa: E402
import uihelp  # noqa: E402

COLORS = {"green": (0.10, 0.90, 0.38), "yellow": (1.00, 0.76, 0.08), "red": (1.00, 0.16, 0.14)}
HEADLINES = {"green": "QUESTION FOR YOU", "yellow": "WAITING FOR YOU", "red": "ERROR"}


def log(text):
    sys.stderr.write("ball: %s\n" % text)
    sys.stderr.flush()


def blend(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def draw_lamp(cr, w, h, d):
    """The same lamp as the Mac: glow, black housing, glass lens with a hot centre, highlight, words."""
    c = COLORS.get(d.get("color"), COLORS["yellow"])
    cx, cy = w / 2.0, h / 2.0
    r = min(w, h) / 2.0 / 1.12
    tau = 2 * math.pi

    glow = cairo.RadialGradient(cx, cy, r * 0.95, cx, cy, r * 1.12)
    glow.add_color_stop_rgba(0, c[0], c[1], c[2], 0.55)
    glow.add_color_stop_rgba(1, c[0], c[1], c[2], 0.0)
    cr.set_source(glow)
    cr.arc(cx, cy, r * 1.12, 0, tau)
    cr.fill()

    ring = cairo.LinearGradient(0, cy - r, 0, cy + r)
    ring.add_color_stop_rgb(0, 0.24, 0.24, 0.24)
    ring.add_color_stop_rgb(1, 0.04, 0.04, 0.04)
    cr.set_source(ring)
    cr.arc(cx, cy, r, 0, tau)
    cr.fill()

    lr = r * 0.86
    fy = cy - lr * 0.18
    lens = cairo.RadialGradient(cx, fy, 0, cx, fy, lr * 1.18)
    hot, rim = blend(c, (1, 1, 1), 0.55), blend(c, (0, 0, 0), 0.55)
    lens.add_color_stop_rgb(0.0, *hot)
    lens.add_color_stop_rgb(0.55, *c)
    lens.add_color_stop_rgb(1.0, *rim)
    cr.set_source(lens)
    cr.arc(cx, cy, lr, 0, tau)
    cr.fill()

    cr.save()
    cr.translate(cx, cy - 0.57 * lr)
    cr.scale(0.62 * lr, 0.29 * lr)
    cr.arc(0, 0, 1, 0, tau)
    cr.restore()
    shine = cairo.LinearGradient(0, cy - 0.86 * lr, 0, cy - 0.28 * lr)
    shine.add_color_stop_rgba(0, 1, 1, 1, 0.42)
    shine.add_color_stop_rgba(1, 1, 1, 1, 0.0)
    cr.set_source(shine)
    cr.fill()

    red = d.get("color") == "red"
    ink = (1, 1, 1, 1) if red else (0.07, 0.07, 0.07, 0.92)
    halo = (0, 0, 0, 0.55) if red else (1, 1, 1, 0.35)
    width = lr * 1.5
    if d.get("message"):
        text(cr, d.get("headline", ""), lr * 0.12, Pango.Weight.HEAVY, ink, halo, cx, cy - 0.52 * lr, width, 0.22 * lr)
        text(cr, d.get("detail", ""), lr * 0.07, Pango.Weight.SEMIBOLD, ink, halo, cx, cy - 0.30 * lr, width, 0.12 * lr)
        text(cr, d["message"], lr * 0.068, Pango.Weight.MEDIUM, ink, halo, cx, cy - 0.14 * lr, lr * 1.42, 0.80 * lr,
             drop_from_start=True)
    else:
        text(cr, d.get("headline", ""), lr * 0.15, Pango.Weight.HEAVY, ink, halo, cx, cy - 0.16 * lr, width, 0.26 * lr)
        text(cr, d.get("detail", ""), lr * 0.085, Pango.Weight.SEMIBOLD, ink, halo, cx, cy + 0.14 * lr, width, 0.26 * lr)
    faint = ink[:3] + (ink[3] * 0.6,)
    text(cr, "click to dismiss", lr * 0.05, Pango.Weight.NORMAL, faint, halo, cx, cy + 0.72 * lr, width, 0.08 * lr)


def text(cr, s, size, weight, ink, halo, cx, top, width, height, drop_from_start=False):
    """Centred, wrapped text in a box; if it overflows, drop words from the start (the ask is at the end)."""
    if not s or size < 1:
        return
    layout = PangoCairo.create_layout(cr)
    layout.set_width(int(width * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_alignment(Pango.Alignment.CENTER)
    font = Pango.FontDescription.from_string("Sans")
    font.set_weight(weight)
    font.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(font)
    layout.set_text(s, -1)
    if drop_from_start:
        words = s.split(" ")
        while len(words) > 1 and layout.get_pixel_extents()[1].height > height:
            words.pop(0)
            layout.set_text("…" + " ".join(words), -1)
    th = min(layout.get_pixel_extents()[1].height, height)
    x, y = cx - width / 2.0, top + (height - th) / 2.0
    cr.save()
    cr.rectangle(x - 4, top - 4, width + 8, height + 8)
    cr.clip()
    cr.set_source_rgba(*halo)
    cr.move_to(x, y + 1)
    PangoCairo.show_layout(cr, layout)
    cr.set_source_rgba(*ink)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    cr.restore()


class Ball:
    def __init__(self, app, display_path, bong_path):
        self.root = os.path.dirname(display_path)
        self.display_path = display_path
        self.player = uihelp.pick_player(shutil.which, bong_path)
        self.current = {}
        self.shown = None          # what is drawn now
        self.dismissed = set()
        self.last_bonged = None
        self.preview = None        # (display, until)
        self.side = 0

        self.win = Gtk.Window(application=app)
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.on_draw)
        self.win.set_child(self.area)
        click = Gtk.GestureClick()
        click.connect("pressed", self.on_click)
        self.area.add_controller(click)
        self.win.connect("map", self.on_map)

        css = Gtk.CssProvider()
        rule = "window, window.background { background: transparent; box-shadow: none; }"
        if hasattr(css, "load_from_string"):          # GTK >= 4.12
            css.load_from_string(rule)
        else:
            try:
                css.load_from_data(rule.encode(), -1)
            except TypeError:                          # older PyGObject: one argument
                css.load_from_data(rule.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.layer = bool(LayerShell) and (getattr(LayerShell, "is_supported", lambda: True)())
        if self.layer:
            LayerShell.init_for_window(self.win)
            LayerShell.set_namespace(self.win, "claude-light")
            LayerShell.set_layer(self.win, LayerShell.Layer.OVERLAY)
            LayerShell.set_anchor(self.win, LayerShell.Edge.TOP, True)
            LayerShell.set_anchor(self.win, LayerShell.Edge.RIGHT, True)
            LayerShell.set_keyboard_mode(self.win, LayerShell.KeyboardMode.NONE)
        else:
            log("no layer-shell (GNOME, or gtk4-layer-shell missing): the ball cannot stay on top")
        GLib.timeout_add(250, self.poll)
        self.poll()

    # ---- display -------------------------------------------------------------------------
    def poll(self):
        try:
            self._poll()
        except Exception as e:  # never die on a bad frame
            log("poll failed: %r" % (e,))
        return True

    def _poll(self):
        req = os.path.join(self.root, "preview.json")
        if os.path.exists(req):
            p = read_json(req) or {}
            try:
                os.remove(req)
            except OSError:
                pass
            self.start_preview(p.get("color", "yellow"))
        if self.preview and self.preview[1] > time.time():
            self.render(self.preview[0])
            return
        if self.preview:
            self.preview = None
            self.hide()
        d = read_json(self.display_path)
        if not isinstance(d, dict):
            return
        self.current = d
        keys = set(d.get("keys") or [])
        suppressed = bool(keys) and keys <= self.dismissed
        if d.get("visible") and not suppressed:
            self.render(d)
        else:
            self.hide()
        if not d.get("visible"):
            self.dismissed.clear()

    def render(self, d):
        side = self.side_for(int(d.get("size") or 5))
        if side != self.side:
            self.side = side
            self.area.set_size_request(side, side)
            self.win.set_default_size(side, side)
            if self.win.get_visible():
                self.win.set_visible(False)       # a layer surface takes a new size on its next map
        if d != self.shown:
            self.shown = d
            self.area.queue_draw()
        if not self.win.get_visible():
            self.win.present()
        if d.get("alert_id") != self.last_bonged:
            self.last_bonged = d.get("alert_id")
            if d.get("sound", True):
                self.bong(d.get("alert_id"))
            else:
                log("alert=%s shown silently (sound off)" % d.get("alert_id"))

    def hide(self):
        if self.win.get_visible():
            self.win.set_visible(False)

    def side_for(self, size):
        """Size n of 10 = a ball n/10 of the screen height across, pinned top-right."""
        mon = None
        monitors = Gdk.Display.get_default().get_monitors()
        if monitors.get_n_items():
            mon = monitors.get_item(0)
        w, h = (mon.get_geometry().width, mon.get_geometry().height) if mon else (1920, 1080)
        usable = min(w, h * 0.96)                 # leave room for a bar (Waybar's exclusive zone)
        side = int(usable * max(1, min(10, size)) / 10)
        if self.layer:
            margin = int(max(0, min(h * 0.012, (usable - side) / 2)))
            LayerShell.set_margin(self.win, LayerShell.Edge.TOP, margin)
            LayerShell.set_margin(self.win, LayerShell.Edge.RIGHT, margin)
        return side

    def on_draw(self, area, cr, w, h):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self.shown:
            draw_lamp(cr, w, h, self.shown)

    def on_map(self, *_):
        """Let clicks through everywhere but the circle (strips approximate it)."""
        try:
            surface = self.win.get_surface()
            side, r = self.side, self.side / 2.0 / 1.12
            region = cairo.Region()
            strips = 48
            for i in range(strips):
                y0 = side / 2.0 - r + 2 * r * i / strips
                dy = abs(y0 + r / strips - side / 2.0)
                half = math.sqrt(max(0.0, r * r - dy * dy))
                region.union(cairo.RectangleInt(int(side / 2.0 - half), int(y0), int(2 * half) + 1,
                                                int(2 * r / strips) + 1))
            surface.set_input_region(region)
        except Exception as e:
            log("input region not set: %r" % (e,))

    def bong(self, alert):
        if not self.player:
            log("bong alert=%s skipped: no pw-play, paplay or aplay" % alert)
            return

        def play():
            try:
                subprocess.Popen(self.player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log("bong alert=%s played=true" % alert)
            except OSError as e:
                log("bong alert=%s failed: %r" % (alert, e))
            return False

        play()
        GLib.timeout_add(1100, play)

    def on_click(self, *_):
        self.hide()
        if self.preview:
            self.preview = None
            return
        keys = list(self.current.get("keys") or [])
        self.dismissed |= set(keys)
        try:
            fsutil.write_json(os.path.join(self.root, "ack.json"), {"keys": keys})
        except OSError as e:
            log("ack failed: %r" % (e,))

    def start_preview(self, color):
        cfg = self.current.get("config") or {}
        color = color if color in COLORS else "yellow"
        d = {"visible": True, "color": color, "headline": HEADLINES[color], "detail": "preview",
             "message": ("This is where the end of Claude's last message appears, so you can see what it "
                         "is asking for.") if cfg.get("show_message") else "",
             "sound": cfg.get("sound", True), "size": cfg.get("size", 5),
             "alert_id": "preview-%f" % time.time()}
        self.hide()
        self.preview = (d, time.time() + 6)


def main(argv):
    if len(argv) < 3:
        sys.stderr.write("usage: ball.py <display.json> <bong.wav>\n")
        return 2
    app = Gtk.Application(application_id="dev.claudelight.ball", flags=Gio.ApplicationFlags.NON_UNIQUE)
    holder = {}

    def activate(a):
        a.hold()                                    # stay alive while the ball is hidden
        holder["ball"] = Ball(a, argv[1], argv[2])

    app.connect("activate", activate)
    return app.run([argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
