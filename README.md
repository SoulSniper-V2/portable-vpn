# Portable VPN for macOS 🟢 🚀

A simple, lightweight macOS menu bar application that bundles its own private Tor instance to bypass network-level blocks (like school/work filters).

## Features
- **Menu Bar Only**: Lives entirely in the system tray, no Dock icon.
- **Bundled Tor**: Works out of the box on any Mac without needing Homebrew or any terminal setup.
- **One-Click Toggle**: Switch between "Blocked" and "Bypassed" in a single click.
- **Secure & Private**: Routes all system traffic through the Tor network.

## Installation
1.  **Download** the latest `PortableVPN.dmg` from the [Releases](https://github.com/SoulSniper-V2/portable-vpn/releases) section.
2.  **Open** the DMG and **drag** the `PortableVPN` icon into your Applications folder.
3.  **Right-click** on `PortableVPN.app` in your Applications folder and select **Open**. (Since it's unsigned, macOS will ask for permission the first time).

## Usage
- Click the **🟢 VPN ON** or **🔴 VPN OFF** icon in your menu bar.
- Click **"Toggle VPN"** to switch states.
- Your entire computer will follow the state shown in the menu bar.

## Development
To build from source:
1.  Install dependencies: `pip install rumps py2app`
2.  Install Tor (to bundle it): `brew install tor`
3.  Run build: `python3 setup.py py2app`

## Disclaimer
This project is for educational and privacy purposes only. Please follow your network's policies and use responsibly.
