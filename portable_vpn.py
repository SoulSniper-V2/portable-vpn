#!/usr/bin/env python3
"""
Portable VPN for macOS — Custom Popover Menu Bar App
Routes system traffic through a bundled Tor SOCKS proxy with a rich UI.
"""

import objc
import subprocess
import os
import sys
import socket
import threading
import time
import json
import signal
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*ObjCPointer.*")

from Foundation import (
    NSObject, NSTimer, NSMakeRect, NSMakeSize,
    NSAttributedString,
)
from AppKit import (
    NSApplication, NSApp, NSStatusBar, NSVariableStatusItemLength,
    NSPopover, NSPopoverBehaviorTransient,
    NSView, NSViewController, NSTextField, NSButton, NSPopUpButton,
    NSFont, NSColor, NSBezierPath,
    NSMinYEdge,
    NSApplicationActivationPolicyAccessory,
    NSAppearance,
    NSForegroundColorAttributeName, NSFontAttributeName,
    NSParagraphStyleAttributeName,
    NSTextAlignmentCenter, NSTextAlignmentLeft,
    NSLineBreakByTruncatingTail,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOR_HOST = "127.0.0.1"
TOR_PORT = 9050

POPOVER_W = 300
PAD = 18
CONTENT_W = POPOVER_W - PAD * 2

COUNTRIES = [
    ("🌐  Any Country", ""),
    ("🇺🇸  United States", "{us}"),
    ("🇬🇧  United Kingdom", "{gb}"),
    ("🇩🇪  Germany", "{de}"),
    ("🇫🇷  France", "{fr}"),
    ("🇳🇱  Netherlands", "{nl}"),
    ("🇨🇦  Canada", "{ca}"),
    ("🇯🇵  Japan", "{jp}"),
    ("🇦🇺  Australia", "{au}"),
    ("🇨🇭  Switzerland", "{ch}"),
    ("🇸🇪  Sweden", "{se}"),
    ("🇷🇴  Romania", "{ro}"),
    ("🇧🇷  Brazil", "{br}"),
    ("🇮🇳  India", "{in}"),
    ("🇸🇬  Singapore", "{sg}"),
    ("🇮🇹  Italy", "{it}"),
    ("🇪🇸  Spain", "{es}"),
    ("🇵🇱  Poland", "{pl}"),
    ("🇭🇰  Hong Kong", "{hk}"),
    ("🇫🇮  Finland", "{fi}"),
]

COUNTRY_FLAGS = {
    "US": "🇺🇸", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷", "NL": "🇳🇱",
    "CA": "🇨🇦", "JP": "🇯🇵", "AU": "🇦🇺", "CH": "🇨🇭", "SE": "🇸🇪",
    "RO": "🇷🇴", "BR": "🇧🇷", "IN": "🇮🇳", "SG": "🇸🇬", "IT": "🇮🇹",
    "ES": "🇪🇸", "PL": "🇵🇱", "HK": "🇭🇰", "FI": "🇫🇮", "RU": "🇷🇺",
    "KR": "🇰🇷", "ZA": "🇿🇦", "MX": "🇲🇽", "NO": "🇳🇴", "DK": "🇩🇰",
    "IE": "🇮🇪", "CZ": "🇨🇿", "AT": "🇦🇹", "BE": "🇧🇪", "PT": "🇵🇹",
}


def rgb(r, g, b, a=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


# Dark theme colors
COL_BG = rgb(20, 20, 30)
COL_CARD = rgb(30, 30, 44)
COL_CARD_LIGHT = rgb(38, 38, 54)
COL_GREEN = rgb(0, 210, 110)
COL_RED = rgb(235, 65, 75)
COL_BLUE = rgb(70, 130, 240)
COL_YELLOW = rgb(240, 190, 50)
COL_TEXT = rgb(235, 235, 242)
COL_TEXT_DIM = rgb(130, 130, 150)
COL_TEXT_XDIM = rgb(80, 80, 100)
COL_SEPARATOR = rgb(45, 45, 65)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper Views
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FlippedView(NSView):
    """NSView subclass with top-left origin (y goes down)."""
    def isFlipped(self):
        return True


class DotView(NSView):
    """Small colored circle indicator."""

    def initWithFrame_color_(self, frame, color):
        self = objc.super(DotView, self).initWithFrame_(frame)
        if self:
            self._color = color
        return self

    def setDotColor_(self, color):
        self._color = color
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if self._color:
            self._color.set()
            NSBezierPath.bezierPathWithOvalInRect_(self.bounds()).fill()


def make_label(text, x, y, w, h, size=13, bold=False, color=None, align=None, mono=False):
    """Create a styled NSTextField label."""
    label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    if mono:
        label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(size, 0))
    elif bold:
        label.setFont_(NSFont.boldSystemFontOfSize_(size))
    else:
        label.setFont_(NSFont.systemFontOfSize_(size))
    label.setTextColor_(color or COL_TEXT)
    if align is not None:
        label.setAlignment_(align)
    label.setLineBreakMode_(NSLineBreakByTruncatingTail)
    return label


def make_card(x, y, w, h):
    """Create a rounded card background view."""
    card = FlippedView.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    card.setWantsLayer_(True)
    card.layer().setCornerRadius_(10)
    card.layer().setBackgroundColor_(COL_CARD.CGColor())
    return card


def make_separator(x, y, w):
    """Create a thin horizontal separator line."""
    sep = NSView.alloc().initWithFrame_(NSMakeRect(x, y, w, 1))
    sep.setWantsLayer_(True)
    sep.layer().setBackgroundColor_(COL_SEPARATOR.CGColor())
    return sep


def make_styled_button(title, x, y, w, h, bg_color, text_color=None):
    """Create a styled button with custom background."""
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    btn.setWantsLayer_(True)
    btn.setBordered_(False)
    btn.layer().setCornerRadius_(8)
    btn.layer().setBackgroundColor_(bg_color.CGColor())
    attrs = {
        NSForegroundColorAttributeName: text_color or COL_TEXT,
        NSFontAttributeName: NSFont.boldSystemFontOfSize_(13),
    }
    btn.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(title, attrs))
    return btn


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main App Controller
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class VPNController(NSObject):

    def init(self):
        self = objc.super(VPNController, self).init()
        if self is None:
            return None

        # — State —
        self._connected = False
        self._tor_ready = False
        self._tor_error = None
        self._tor_process = None
        self._vpn_start_time = None
        self._geo_info = {}
        self._active_interface = "Wi-Fi"
        self._selected_country_code = ""

        # — Tor path —
        if getattr(sys, "frozen", False):
            res = os.environ.get(
                "RESOURCEPATH",
                os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "Resources"),
            )
            self._tor_path = os.path.join(res, "tor_bin", "tor")
            # Ensure bundled dylibs are found
            lib_path = os.path.join(res, "tor_bin", "lib")
            current = os.environ.get("DYLD_LIBRARY_PATH", "")
            os.environ["DYLD_LIBRARY_PATH"] = f"{lib_path}:{current}" if current else lib_path
        else:
            self._tor_path = "/opt/homebrew/bin/tor"

        # — UI references (set in _build_ui) —
        self._status_item = None
        self._popover = None
        self._status_dot = None
        self._status_label = None
        self._uptime_label = None
        self._ip_val = None
        self._country_val = None
        self._city_val = None
        self._isp_val = None
        self._connect_btn = None
        self._country_popup = None
        self._tor_status_label = None

        return self

    # ─── App Lifecycle ────────────────────────

    def applicationDidFinishLaunching_(self, notification):
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self._detect_interface()
        self._setup_status_bar()
        self._setup_popover()
        self._start_tor_async()

        # 1-second UI refresh timer
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "tick:", None, True
        )

    def applicationWillTerminate_(self, notification):
        self._cleanup()

    # ─── Status Bar ───────────────────────────

    def _setup_status_bar(self):
        sb = NSStatusBar.systemStatusBar()
        self._status_item = sb.statusItemWithLength_(NSVariableStatusItemLength)
        btn = self._status_item.button()
        btn.setTitle_("🔴 VPN")
        btn.setTarget_(self)
        btn.setAction_("togglePopover:")

    def togglePopover_(self, sender):
        if self._popover.isShown():
            self._popover.performClose_(sender)
        else:
            btn = self._status_item.button()
            self._refresh_display()
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, NSMinYEdge
            )

    # ─── Popover + UI ─────────────────────────

    def _setup_popover(self):
        self._popover = NSPopover.alloc().init()
        self._popover.setBehavior_(NSPopoverBehaviorTransient)
        self._popover.setAnimates_(True)

        content = self._build_ui()
        vc = NSViewController.alloc().init()
        vc.setView_(content)
        self._popover.setContentViewController_(vc)

    def _build_ui(self):
        y = 0  # running y position

        # Root view
        root = FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, POPOVER_W, 10))
        root.setWantsLayer_(True)
        root.layer().setBackgroundColor_(COL_BG.CGColor())
        try:
            root.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameVibrantDark"))
        except Exception:
            pass

        # ── Header ──
        y += PAD
        title = make_label("🛡  Portable VPN", PAD, y, CONTENT_W, 22, size=17, bold=True, color=COL_TEXT)
        root.addSubview_(title)
        y += 26
        subtitle = make_label("Secure Tor Proxy", PAD, y, CONTENT_W, 16, size=11, color=COL_TEXT_DIM)
        root.addSubview_(subtitle)
        y += 24

        root.addSubview_(make_separator(PAD, y, CONTENT_W))
        y += 13

        # ── Status Card ──
        card_h = 56
        status_card = make_card(PAD, y, CONTENT_W, card_h)
        root.addSubview_(status_card)

        self._status_dot = DotView.alloc().initWithFrame_color_(
            NSMakeRect(14, 18, 10, 10), COL_TEXT_DIM
        )
        status_card.addSubview_(self._status_dot)

        self._status_label = make_label(
            "Starting…", 32, 10, CONTENT_W - 48, 18, size=15, bold=True, color=COL_TEXT
        )
        status_card.addSubview_(self._status_label)

        self._uptime_label = make_label(
            "", 32, 30, CONTENT_W - 48, 16, size=11, color=COL_TEXT_DIM
        )
        status_card.addSubview_(self._uptime_label)
        y += card_h + 10

        # ── Tor Status ──
        self._tor_status_label = make_label(
            "Tor: starting…", PAD + 2, y, CONTENT_W, 14, size=10, color=COL_YELLOW
        )
        root.addSubview_(self._tor_status_label)
        y += 20

        # ── Connection Info Card ──
        section_label = make_label(
            "CONNECTION INFO", PAD + 2, y, CONTENT_W, 14, size=9, bold=True, color=COL_TEXT_XDIM
        )
        root.addSubview_(section_label)
        y += 18

        info_card_h = 132
        info_card = make_card(PAD, y, CONTENT_W, info_card_h)
        root.addSubview_(info_card)

        info_items = [
            ("IP Address", "_ip_val"),
            ("Country", "_country_val"),
            ("City", "_city_val"),
            ("ISP", "_isp_val"),
        ]
        iy = 0
        for i, (label_text, attr_name) in enumerate(info_items):
            row_y = iy + 6
            lbl = make_label(label_text, 12, row_y, 80, 20, size=10, color=COL_TEXT_DIM)
            info_card.addSubview_(lbl)
            val = make_label("—", 90, row_y, CONTENT_W - 110, 20, size=12, color=COL_TEXT, mono=True)
            info_card.addSubview_(val)
            setattr(self, attr_name, val)
            iy += 32
            if i < len(info_items) - 1:
                info_card.addSubview_(make_separator(12, iy, CONTENT_W - 24))
                iy += 1

        y += info_card_h + 14

        # ── Country Selector ──
        country_lbl = make_label(
            "EXIT COUNTRY", PAD + 2, y, CONTENT_W, 14, size=9, bold=True, color=COL_TEXT_XDIM
        )
        root.addSubview_(country_lbl)
        y += 18

        self._country_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(PAD, y, CONTENT_W, 28), False
        )
        for name, _ in COUNTRIES:
            self._country_popup.addItemWithTitle_(name)
        self._country_popup.setTarget_(self)
        self._country_popup.setAction_("countryChanged:")
        root.addSubview_(self._country_popup)
        y += 36

        # ── Connect / Disconnect Button ──
        self._connect_btn = make_styled_button(
            "Connect VPN", PAD, y, CONTENT_W, 38, COL_GREEN
        )
        self._connect_btn.setTarget_(self)
        self._connect_btn.setAction_("toggleVPN:")
        root.addSubview_(self._connect_btn)
        y += 46

        # ── Action Buttons Row ──
        half_w = (CONTENT_W - 8) // 2
        restart_btn = make_styled_button("↻  Restart Tor", PAD, y, half_w, 30, COL_CARD_LIGHT)
        restart_btn.setTarget_(self)
        restart_btn.setAction_("restartTor:")
        root.addSubview_(restart_btn)

        copy_btn = make_styled_button("📋  Copy IP", PAD + half_w + 8, y, half_w, 30, COL_CARD_LIGHT)
        copy_btn.setTarget_(self)
        copy_btn.setAction_("copyIP:")
        root.addSubview_(copy_btn)
        y += 38

        # ── Quit Button ──
        quit_btn = make_styled_button("Quit", PAD, y, CONTENT_W, 26, COL_BG, COL_TEXT_DIM)
        quit_btn.setTarget_(self)
        quit_btn.setAction_("quitApp:")
        root.addSubview_(quit_btn)
        y += 26 + PAD

        # Set final size
        root.setFrame_(NSMakeRect(0, 0, POPOVER_W, y))
        self._popover.setContentSize_(NSMakeSize(POPOVER_W, y))

        return root

    # ─── Timer Tick (main thread, 1s) ─────────

    def tick_(self, timer):
        self._refresh_display()

    def _refresh_display(self):
        """Update all UI elements from current state."""
        is_on = self._get_vpn_status()
        self._connected = is_on

        # Status bar icon
        if self._tor_error:
            self._status_item.button().setTitle_("⚠️ VPN")
        elif is_on:
            self._status_item.button().setTitle_("🟢 VPN")
        else:
            self._status_item.button().setTitle_("🔴 VPN")

        # Status card
        if is_on:
            self._status_dot.setDotColor_(COL_GREEN)
            self._status_label.setStringValue_("Connected")
            self._status_label.setTextColor_(COL_GREEN)
            if self._vpn_start_time:
                elapsed = int(time.time() - self._vpn_start_time)
                h, r = divmod(elapsed, 3600)
                m, s = divmod(r, 60)
                if h > 0:
                    fmt = f"Uptime: {h}h {m:02d}m {s:02d}s"
                elif m > 0:
                    fmt = f"Uptime: {m}m {s:02d}s"
                else:
                    fmt = f"Uptime: {s}s"
                self._uptime_label.setStringValue_(fmt)
        else:
            self._status_dot.setDotColor_(COL_RED)
            self._status_label.setStringValue_("Disconnected")
            self._status_label.setTextColor_(COL_RED)
            self._uptime_label.setStringValue_("")

        # Tor status
        if self._tor_error:
            self._tor_status_label.setStringValue_(f"Tor: ⚠️ {self._tor_error}")
            self._tor_status_label.setTextColor_(COL_RED)
        elif self._tor_ready:
            self._tor_status_label.setStringValue_("Tor: ✓ Running on :9050")
            self._tor_status_label.setTextColor_(COL_GREEN)
        else:
            self._tor_status_label.setStringValue_("Tor: ⏳ Connecting…")
            self._tor_status_label.setTextColor_(COL_YELLOW)

        # Connect button style
        if is_on:
            self._set_button_style(self._connect_btn, "Disconnect VPN", COL_RED)
        else:
            self._set_button_style(self._connect_btn, "Connect VPN", COL_GREEN)

        # Geo info
        geo = self._geo_info
        if geo:
            cc = geo.get("countryCode", "")
            flag = COUNTRY_FLAGS.get(cc, "🌐")
            self._ip_val.setStringValue_(geo.get("query", "—"))
            self._country_val.setStringValue_(f"{flag} {geo.get('country', '—')}")
            self._city_val.setStringValue_(
                f"{geo.get('city', '—')}, {geo.get('regionName', '')}"
            )
            self._isp_val.setStringValue_(geo.get("isp", "—"))

    def _set_button_style(self, btn, title, bg_color):
        btn.layer().setBackgroundColor_(bg_color.CGColor())
        attrs = {
            NSForegroundColorAttributeName: COL_TEXT,
            NSFontAttributeName: NSFont.boldSystemFontOfSize_(13),
        }
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(title, attrs)
        )

    # ─── Network Interface Detection ─────────

    def _detect_interface(self):
        try:
            out = subprocess.check_output(
                ["networksetup", "-listallnetworkservices"], stderr=subprocess.DEVNULL
            ).decode()
            services = [l.strip() for l in out.splitlines()
                        if l.strip() and not l.startswith("An asterisk")]
            for svc in services:
                try:
                    info = subprocess.check_output(
                        ["networksetup", "-getinfo", svc], stderr=subprocess.DEVNULL
                    ).decode()
                    for line in info.splitlines():
                        if line.startswith("IP address:"):
                            ip = line.split(":", 1)[1].strip()
                            if ip and ip.lower() != "none":
                                self._active_interface = svc
                                return
                except subprocess.CalledProcessError:
                    continue
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"[VPN] Interface detect error: {e}")
        self._active_interface = "Wi-Fi"

    # ─── Tor Lifecycle ────────────────────────

    def _start_tor_async(self):
        self._tor_ready = False
        self._tor_error = None
        threading.Thread(target=self._start_tor_blocking, daemon=True).start()

    def _start_tor_blocking(self):
        # Kill existing
        if self._tor_process:
            try:
                self._tor_process.terminate()
                self._tor_process.wait(timeout=3)
            except Exception:
                try:
                    self._tor_process.kill()
                except Exception:
                    pass

        try:
            data_dir = os.path.expanduser("~/.portable_tor_data")
            os.makedirs(data_dir, exist_ok=True)

            # Write torrc with optional ExitNodes
            torrc_path = os.path.join(data_dir, "torrc")
            with open(torrc_path, "w") as f:
                f.write(f"SocksPort {TOR_PORT}\n")
                f.write(f"DataDirectory {data_dir}\n")
                if self._selected_country_code:
                    f.write(f"ExitNodes {self._selected_country_code}\n")
                    f.write("StrictNodes 1\n")

            abs_tor = os.path.abspath(self._tor_path)
            self._tor_process = subprocess.Popen(
                [abs_tor, "-f", torrc_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if self._wait_for_port(TOR_PORT, timeout=30):
                self._tor_ready = True
                self._tor_error = None
            else:
                self._tor_error = "Timed out"
        except FileNotFoundError:
            self._tor_error = f"Tor not found at {self._tor_path}"
        except OSError as e:
            self._tor_error = str(e)

    def _wait_for_port(self, port, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect((TOR_HOST, port))
                s.close()
                return True
            except (socket.error, OSError):
                time.sleep(0.5)
        return False

    # ─── VPN Status ───────────────────────────

    def _get_vpn_status(self):
        try:
            out = subprocess.check_output(
                ["networksetup", "-getsocksfirewallproxy", self._active_interface],
                stderr=subprocess.DEVNULL,
            ).decode()
            return "Enabled: Yes" in out
        except subprocess.CalledProcessError:
            return False

    # ─── IP / Geo Fetching ────────────────────

    def _fetch_geo_info(self):
        """Fetch geo info through the Tor SOCKS proxy using curl."""
        try:
            out = subprocess.check_output(
                [
                    "curl", "-s", "--max-time", "10",
                    "--socks5-hostname", f"{TOR_HOST}:{TOR_PORT}",
                    "http://ip-api.com/json/",
                ],
                stderr=subprocess.DEVNULL,
            ).decode()
            data = json.loads(out)
            if data.get("status") == "success":
                self._geo_info = data
        except Exception as e:
            print(f"[VPN] Geo fetch error: {e}")

    # ─── Actions ──────────────────────────────

    def toggleVPN_(self, sender):
        if not self._tor_ready:
            return  # Tor not ready yet

        is_on = self._get_vpn_status()
        try:
            if is_on:
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate",
                     self._active_interface, "off"],
                    check=True,
                )
                self._vpn_start_time = None
                self._geo_info = {}
                self._ip_val.setStringValue_("—")
                self._country_val.setStringValue_("—")
                self._city_val.setStringValue_("—")
                self._isp_val.setStringValue_("—")
            else:
                # Set proxy address first, then enable
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxy",
                     self._active_interface, TOR_HOST, str(TOR_PORT)],
                    check=True,
                )
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate",
                     self._active_interface, "on"],
                    check=True,
                )
                self._vpn_start_time = time.time()
                # Fetch geo info in background
                threading.Thread(target=self._fetch_geo_info, daemon=True).start()

            self._refresh_display()
        except subprocess.CalledProcessError as e:
            print(f"[VPN] Toggle error: {e}")

    def countryChanged_(self, sender):
        idx = sender.indexOfSelectedItem()
        _, code = COUNTRIES[idx]
        self._selected_country_code = code

        # Disconnect, restart Tor with new exit nodes, user reconnects
        was_on = self._get_vpn_status()
        if was_on:
            try:
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate",
                     self._active_interface, "off"],
                    check=True,
                )
            except subprocess.CalledProcessError:
                pass
            self._vpn_start_time = None
            self._geo_info = {}

        self._start_tor_async()
        self._refresh_display()

    def restartTor_(self, sender):
        was_on = self._get_vpn_status()
        if was_on:
            try:
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxystate",
                     self._active_interface, "off"],
                    check=True,
                )
            except subprocess.CalledProcessError:
                pass
            self._vpn_start_time = None
            self._geo_info = {}

        self._start_tor_async()
        self._refresh_display()

    def copyIP_(self, sender):
        ip = self._geo_info.get("query", "")
        if ip:
            subprocess.run(["pbcopy"], input=ip.encode(), check=True)

    def quitApp_(self, sender):
        self._cleanup()
        NSApp.terminate_(self)

    def _cleanup(self):
        if self._tor_process:
            try:
                self._tor_process.terminate()
                self._tor_process.wait(timeout=3)
            except Exception:
                try:
                    self._tor_process.kill()
                except Exception:
                    pass
        try:
            subprocess.run(
                ["networksetup", "-setsocksfirewallproxystate",
                 self._active_interface, "off"],
                check=True,
            )
        except subprocess.CalledProcessError:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = NSApplication.sharedApplication()
    controller = VPNController.alloc().init()
    app.setDelegate_(controller)
    app.run()


if __name__ == "__main__":
    main()
