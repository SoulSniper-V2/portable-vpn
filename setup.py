from setuptools import setup
import os

APP = ['portable_vpn.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,
        'CFBundleName': 'PortableVPN',
        'CFBundleDisplayName': 'Portable VPN',
        'CFBundleIdentifier': 'com.user.portablevpn',
        'CFBundleVersion': '1.3.0',
        'CFBundleShortVersionString': '1.3.0',
    },
    'packages': ['objc', 'AppKit', 'Foundation'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
