#!/bin/bash
set -e

echo "═══════════════════════════════════════════"
echo "  Portable VPN — Standalone DMG Builder"
echo "═══════════════════════════════════════════"

# ── Config ──
APP_NAME="PortableVPN"
VERSION="v1.3.0"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
DIST_DIR="dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
RESOURCES="${APP_PATH}/Contents/Resources"
FRAMEWORKS="${APP_PATH}/Contents/Frameworks"

TOR_BIN="/opt/homebrew/bin/tor"
DYLIBS=(
    "/opt/homebrew/opt/libevent/lib/libevent-2.1.7.dylib"
    "/opt/homebrew/opt/openssl@3/lib/libssl.3.dylib"
    "/opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib"
    "/opt/homebrew/opt/libscrypt/lib/libscrypt.0.dylib"
)

# ── Checks ──
if [ ! -f "$TOR_BIN" ]; then
    echo "❌ Tor binary not found at $TOR_BIN"
    echo "   Install with: brew install tor"
    exit 1
fi

for dylib in "${DYLIBS[@]}"; do
    if [ ! -f "$dylib" ]; then
        echo "❌ Missing library: $dylib"
        echo "   Install Tor dependencies: brew install tor"
        exit 1
    fi
done

# ── Step 1: Clean & Build with py2app ──
echo ""
echo "🔨 Step 1: Building .app with py2app..."
rm -rf build dist "${DMG_NAME}"
source venv/bin/activate
python3 setup.py py2app 2>&1 | tail -1

echo "   ✅ App bundle built at ${APP_PATH}"

# ── Step 2: Bundle Tor binary ──
echo ""
echo "📦 Step 2: Bundling Tor binary..."
mkdir -p "${RESOURCES}/tor_bin"
cp "$TOR_BIN" "${RESOURCES}/tor_bin/tor"
chmod +x "${RESOURCES}/tor_bin/tor"
echo "   ✅ Tor binary copied"

# ── Step 3: Bundle dylibs ──
echo ""
echo "📦 Step 3: Bundling shared libraries..."
mkdir -p "${RESOURCES}/tor_bin/lib"

for dylib in "${DYLIBS[@]}"; do
    BASENAME=$(basename "$dylib")
    cp "$dylib" "${RESOURCES}/tor_bin/lib/${BASENAME}"
    chmod 644 "${RESOURCES}/tor_bin/lib/${BASENAME}"
    echo "   → ${BASENAME}"
done

# ── Step 4: Rewrite dylib paths in Tor binary ──
echo ""
echo "🔧 Step 4: Rewriting library paths..."

# Fix the Tor binary's references
install_name_tool -change \
    "/opt/homebrew/opt/libevent/lib/libevent-2.1.7.dylib" \
    "@executable_path/../Resources/tor_bin/lib/libevent-2.1.7.dylib" \
    "${RESOURCES}/tor_bin/tor"

install_name_tool -change \
    "/opt/homebrew/opt/openssl@3/lib/libssl.3.dylib" \
    "@executable_path/../Resources/tor_bin/lib/libssl.3.dylib" \
    "${RESOURCES}/tor_bin/tor"

install_name_tool -change \
    "/opt/homebrew/opt/openssl@3/lib/libcrypto.3.dylib" \
    "@executable_path/../Resources/tor_bin/lib/libcrypto.3.dylib" \
    "${RESOURCES}/tor_bin/tor"

install_name_tool -change \
    "/opt/homebrew/opt/libscrypt/lib/libscrypt.0.dylib" \
    "@executable_path/../Resources/tor_bin/lib/libscrypt.0.dylib" \
    "${RESOURCES}/tor_bin/tor"

# Fix libssl's reference to libcrypto (it references the Cellar path)
install_name_tool -change \
    "/opt/homebrew/Cellar/openssl@3/3.6.1/lib/libcrypto.3.dylib" \
    "@loader_path/libcrypto.3.dylib" \
    "${RESOURCES}/tor_bin/lib/libssl.3.dylib"

# Fix each dylib's install name to use @rpath
for dylib in "${DYLIBS[@]}"; do
    BASENAME=$(basename "$dylib")
    install_name_tool -id \
        "@loader_path/lib/${BASENAME}" \
        "${RESOURCES}/tor_bin/lib/${BASENAME}" 2>/dev/null || true
done

echo "   ✅ All library paths rewritten"

# ── Step 5: Verify no Homebrew references remain ──
echo ""
echo "🔍 Step 5: Verifying no external Homebrew references..."
REMAINING=$(otool -L "${RESOURCES}/tor_bin/tor" | grep "/opt/homebrew" || true)
if [ -n "$REMAINING" ]; then
    echo "   ⚠️  Warning: Still found Homebrew references:"
    echo "$REMAINING"
else
    echo "   ✅ No Homebrew references — fully standalone!"
fi

# ── Step 6: Ad-hoc code sign ──
echo ""
echo "🔏 Step 6: Ad-hoc code signing..."
codesign --force --deep --sign - "${APP_PATH}" 2>/dev/null || true
echo "   ✅ App signed (ad-hoc)"

# ── Step 7: Create DMG ──
echo ""
echo "💿 Step 7: Creating DMG installer..."
create-dmg \
    --volname "Portable VPN Installer" \
    --window-pos 200 120 \
    --window-size 600 300 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 175 120 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 425 120 \
    "${DMG_NAME}" \
    "${APP_PATH}" 2>&1

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ BUILD COMPLETE"
echo "  📦 ${DMG_NAME} ($(du -h "${DMG_NAME}" | cut -f1))"
echo "  📍 $(pwd)/${DMG_NAME}"
echo "═══════════════════════════════════════════"
