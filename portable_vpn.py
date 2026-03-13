import rumps
import subprocess
import os
import sys
import signal
import time

class PortableVPNToggleApp(rumps.App):
    def __init__(self):
        super(PortableVPNToggleApp, self).__init__("VPN")
        self.menu = ["Status", "Toggle VPN", None, "Restart Tor", None]
        
        # Determine path for the bundled Tor binary
        if getattr(sys, 'frozen', False):
            # Running as a bundled app (py2app)
            # Standard py2app resource path
            resource_path = os.environ.get('RESOURCEPATH', os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Resources'))
            self.tor_path = os.path.join(resource_path, 'tor')
        else:
            # Running as a script (for testing)
            self.tor_path = "/opt/homebrew/bin/tor"

        self.tor_process = None
        self.start_bundled_tor()
        self.update_status()

    def start_bundled_tor(self):
        """Starts a private Tor instance for the app."""
        if self.tor_process:
            try:
                self.tor_process.terminate()
                self.tor_process.wait(timeout=2)
            except:
                pass
            
        try:
            # We use a custom DataDirectory to avoid conflicts
            data_dir = os.path.expanduser("~/.portable_tor_data")
            os.makedirs(data_dir, exist_ok=True)
            
            # Use absolute path to the binary to be safe
            abs_tor_path = os.path.abspath(self.tor_path)
            
            self.tor_process = subprocess.Popen(
                [abs_tor_path, '--SocksPort', '9050', '--DataDirectory', data_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2) # Give it a second to bind the port
        except Exception as e:
            rumps.alert("Tor Error", f"Could not start bundled Tor at {self.tor_path}: {e}")

    def get_vpn_status(self):
        try:
            output = subprocess.check_output(['networksetup', '-getsocksfirewallproxy', 'Wi-Fi']).decode('utf-8')
            return "Enabled: Yes" in output
        except:
            return False

    def update_status(self):
        is_on = self.get_vpn_status()
        if is_on:
            self.title = "🟢 VPN ON"
            self.menu["Status"].title = "Status: 🟢 Protected (Bundled Tor)"
        else:
            self.title = "🔴 VPN OFF"
            self.menu["Status"].title = "Status: 🔴 Unprotected"

    @rumps.clicked("Toggle VPN")
    def toggle(self, _):
        is_on = self.get_vpn_status()
        new_state = "off" if is_on else "on"
        try:
            subprocess.run(['networksetup', '-setsocksfirewallproxystate', 'Wi-Fi', new_state], check=True)
            self.update_status()
        except Exception as e:
            rumps.alert("Error", f"Could not toggle: {e}")

    @rumps.clicked("Restart Tor")
    def restart_tor(self, _):
        self.start_bundled_tor()
        rumps.notification("VPN App", "Tor Restarted", "Private Tor instance has been reset.")

    def on_quit(self):
        # Kill Tor when the app exits
        if self.tor_process:
            self.tor_process.terminate()
        # Also turn off the proxy to be safe
        subprocess.run(['networksetup', '-setsocksfirewallproxystate', 'Wi-Fi', 'off'])

if __name__ == "__main__":
    app = PortableVPNToggleApp()
    app.run()
