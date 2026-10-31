#!/usr/bin/env bash
# Compile Accueil Zen (Android TV 7.0 et plus) sans Android Studio ni SDK complet :
#   aapt2 (embarqué dans apktool) + ressources du framework Android (embarquées dans apktool)
#   javac (JDK 8+) contre android-all (Robolectric) -> dx -> classes.dex -> signature apksig (v2)
# Les outils sont téléchargés une fois depuis Maven Central dans ./.outils
set -euo pipefail
cd "$(dirname "$0")"

MAVEN="${MAVEN:-https://maven-central.storage-download.googleapis.com/maven2}"
O=.outils
B=build
mkdir -p "$O" "$B"

telecharger() { # chemin_maven fichier
  [ -s "$O/$2" ] || { echo "Téléchargement de $2…"; curl -fsSL -o "$O/$2" "$MAVEN/$1"; }
}
telecharger org/apktool/apktool-cli/3.0.3/apktool-cli-3.0.3.jar apktool.jar
telecharger com/jakewharton/android/repackaged/dalvik-dx/16.0.1/dalvik-dx-16.0.1.jar dx.jar
telecharger com/android/tools/build/apksig/2.3.0/apksig-2.3.0.jar apksig.jar
telecharger org/robolectric/android-all/11-robolectric-6757853/android-all-11-robolectric-6757853.jar android-all.jar

case "$(uname -s)" in
  Darwin) PLAT=macosx/aapt2 ;;
  *) PLAT=linux/aapt2 ;;
esac
if [ ! -x "$O/aapt2" ]; then
  unzip -o -q -j "$O/apktool.jar" "prebuilt/$PLAT" -d "$O" && chmod +x "$O/aapt2"
  unzip -o -q -j "$O/apktool.jar" "prebuilt/android-framework.jar" -d "$O"
fi

# Images (fonds nature + icône/bannière) si absentes
if [ ! -f res/drawable/banniere.png ] || [ -z "$(ls assets/fonds 2>/dev/null)" ]; then
  python3 outils/generer_images.py assets/fonds res/drawable
fi

rm -rf "$B"/*
mkdir -p "$B/res" "$B/classes"

echo "1/5 Ressources (aapt2)"
"$O/aapt2" compile --dir res -o "$B/res/compilees.zip"
"$O/aapt2" link -o "$B/sans_dex.apk" -I "$O/android-framework.jar" \
  --manifest AndroidManifest.xml -A assets --java "$B/gen" \
  --min-sdk-version 24 --target-sdk-version 28 --version-code 1 --version-name 1.0 \
  "$B/res/compilees.zip"

echo "2/5 Java (javac)"
javac -nowarn -encoding UTF-8 --release 8 -Xlint:-options \
  -cp "$O/android-all.jar" -d "$B/classes" \
  $(find src "$B/gen" -name '*.java')

echo "3/5 Dex (dx)"
java -cp "$O/dx.jar" com.android.dx.command.Main --dex --min-sdk-version=24 \
  --output="$B/classes.dex" "$B/classes"

echo "4/5 Assemblage"
cp "$B/sans_dex.apk" "$B/non_signe.apk"
(cd "$B" && zip -q -j non_signe.apk classes.dex)

echo "5/5 Signature v2 (apksig) — Android 7 minimum"
CLE=cle/accueilzen.p12
if [ ! -f "$CLE" ]; then
  mkdir -p cle
  keytool -genkeypair -keystore "$CLE" -storetype PKCS12 -storepass accueilzen -keypass accueilzen \
    -alias accueilzen -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Accueil Zen, O=Lourdes, C=FR" >/dev/null 2>&1
fi
javac -nowarn -encoding UTF-8 -cp "$O/apksig.jar" -d "$B/signeur" outils/Signer.java
java --add-exports java.base/sun.security.x509=ALL-UNNAMED --add-exports java.base/sun.security.pkcs=ALL-UNNAMED --add-exports java.base/sun.security.util=ALL-UNNAMED -cp "$O/apksig.jar:$B/signeur" Signer "$CLE" accueilzen accueilzen "$B/non_signe.apk" ../dist/AccueilZen.apk

echo "APK prêt : $(cd ../dist && pwd)/AccueilZen.apk ($(du -k ../dist/AccueilZen.apk | cut -f1) Ko)"
