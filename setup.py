from setuptools import setup
import os

APP = ['portable_vpn.py']
DATA_FILES = [
    ('', ['/opt/homebrew/bin/tor']),
]
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
        'CFBundleName': 'PortableVPN',
        'CFBundleDisplayName': 'Portable VPN',
        'CFBundleIdentifier': 'com.user.portablevpn',
        'CFBundleVersion': '1.1.0',
        'CFBundleShortVersionString': '1.1.0',
    },
    'packages': ['rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
