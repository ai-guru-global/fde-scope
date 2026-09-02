#!/usr/bin/env bash
# Build fde-scope WebView client APK with aapt/javac/d8/zipalign/apksigner.
# Toolchain: android/.toolchain/{build-tools,android.jar}; falls back to env
# ANDROID_BT (build-tools dir) and ANDROID_PLATFORM_JAR. Java 8+ is enough.
set -euo pipefail
cd "$(dirname "$0")"

PKG_DIR="android-11"   # build-tools 30.0.1 / platform-30 both extract to android-11
BT="${ANDROID_BT:-.toolchain/$PKG_DIR}"
JAR="${ANDROID_PLATFORM_JAR:-$BT/android.jar}"

if [[ ! -x "$BT/aapt" || ! -f "$JAR" ]]; then
  echo "toolchain missing: run (from android/.toolchain)"
  echo "  curl -sSLO https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r30.0.1-macosx.zip"
  echo "  curl -sSLO https://mirrors.cloud.tencent.com/AndroidSDK/platform-30_r03.zip"
  echo "  unzip -qo build-tools_r30.0.1-macosx.zip && unzip -qo platform-30_r03.zip"
  exit 2
fi

rm -rf build && mkdir -p build/gen build/classes build/dex

"$BT/aapt" package -f -m -M AndroidManifest.xml -S res -I "$JAR" -J build/gen
javac -source 8 -target 8 -nowarn -classpath "$JAR" -d build/classes \
  $(find build/gen src -name '*.java')
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \
  --lib "$JAR" --release --output build/dex \
  $(find build/classes -name '*.class')

"$BT/aapt" package -f -M AndroidManifest.xml -S res -A assets -I "$JAR" -F build/app.unsigned.apk
(cd build/dex && zip -q ../app.unsigned.apk classes.dex)
"$BT/zipalign" -f 4 build/app.unsigned.apk build/app.aligned.apk

KS=debug.keystore
# apksigner requires Java 9+; prepend a Homebrew OpenJDK when system java is 8
if ! java -cp "$BT/lib/apksigner.jar" com.android.apksigner.ApkSignerTool --help >/dev/null 2>&1; then
  for cand in /opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
              /usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home; do
    if [[ -x "$cand/bin/java" ]]; then export PATH="$cand/bin:$PATH"; break; fi
  done
fi
if [[ ! -f "$KS" ]]; then
  keytool -genkeypair -keystore "$KS" -storepass android -keypass android \
    -alias fdebug -dname "CN=fde-scope debug" -keyalg RSA -keysize 2048 \
    -validity 10000 >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --out fde-scope-console.apk build/app.aligned.apk
"$BT/apksigner" verify fde-scope-console.apk
ls -lh fde-scope-console.apk
