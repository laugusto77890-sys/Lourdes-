#!/usr/bin/env python3
"""Allègement réversible d'une Android TV + installation d'Accueil Zen.

Fonctionne sur Windows, macOS et Linux avec Python 3.8+ (aucune dépendance).
Toutes les commandes se lancent depuis un ordinateur relié au MÊME Wi-Fi que la télé.

    python3 tv_allegement.py tout              # parcours guidé complet (recommandé)

Commandes à l'unité :
    trouver            cherche la télé sur le Wi-Fi
    connecter IP       se connecte en ADB (accepter le message sur la télé)
    sauvegarder        photographie l'état complet AVANT toute modification
    audit              liste ce qui pourrait être allégé (ne modifie rien)
    alleger            désactive pubs / télémétrie / applis inutiles (avec vos réponses)
    installer          installe Accueil Zen et le définit comme écran d'accueil
    fonds DOSSIER      envoie vos propres photos comme fonds d'écran
    capture NOM        prend une capture de la télé
    restaurer          remet la télé exactement dans l'état sauvegardé
    rapport            ouvre le rapport illustré (captures de chaque étape)

Option --essai : affiche les commandes de modification sans les exécuter.
"""
import argparse
import concurrent.futures
import datetime
import html
import ipaddress
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogue as C  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
APK = RACINE / "dist" / "AccueilZen.apk"
PKG_ZEN = "com.lourdes.accueilzen"
ACTIVITE_ZEN = PKG_ZEN + "/.MainActivity"
TRAVAIL = RACINE / "ma-tele"
ETAT = TRAVAIL / "etat.json"
CAPTURES = TRAVAIL / "captures"
ESSAI = False


# --------------------------------------------------------------------------- affichage

def titre(t):
    print("\n" + "═" * 70 + "\n  " + t + "\n" + "═" * 70)


def info(t):
    print("  • " + t)


def ok(t):
    print("  ✔ " + t)


def alerte(t):
    print("  ⚠ " + t)


def erreur(t):
    print("  ✖ " + t)


def demander(question, defaut=False):
    suffixe = " [O/n] " if defaut else " [o/N] "
    while True:
        try:
            r = input("  ? " + question + suffixe).strip().lower()
        except EOFError:
            sys.exit("\nSaisie interrompue : arrêt sans autre modification.")
        if not r:
            return defaut
        if r in ("o", "oui", "y", "yes"):
            return True
        if r in ("n", "non", "no"):
            return False
        print("    Répondez o (oui) ou n (non).")


def lire_etat():
    if ETAT.exists():
        return json.loads(ETAT.read_text(encoding="utf-8"))
    return {}


def ecrire_etat(e):
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- adb

def trouver_adb():
    exe = "adb.exe" if os.name == "nt" else "adb"
    local = RACINE / "platform-tools" / exe
    if local.exists():
        return str(local)
    chemin = shutil.which("adb")
    if chemin:
        return chemin
    titre("Outil ADB introuvable")
    info("ADB est l'outil officiel de Google pour dialoguer avec les appareils Android.")
    systeme = {"Windows": "windows", "Darwin": "darwin"}.get(platform.system(), "linux")
    url = "https://dl.google.com/android/repository/platform-tools-latest-%s.zip" % systeme
    if not demander("Le télécharger depuis le site officiel de Google (%s) ?" % url, True):
        sys.exit("ADB est nécessaire. Installez « Android SDK Platform-Tools » puis relancez.")
    archive = RACINE / "platform-tools.zip"
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(RACINE)
    archive.unlink()
    if os.name != "nt":
        for f in (RACINE / "platform-tools").iterdir():
            f.chmod(0o755)
    ok("ADB installé dans " + str(RACINE / "platform-tools"))
    return str(local)


ADB = None


def adb(*args, serie=None, verifier=False, binaire=False, delai=60):
    global ADB
    if ADB is None:
        ADB = trouver_adb()
    cmd = [ADB]
    if serie:
        cmd += ["-s", serie]
    cmd += list(args)
    r = subprocess.run(cmd, capture_output=True, timeout=delai)
    if verifier and r.returncode != 0:
        raise RuntimeError("Échec : %s\n%s" % (" ".join(args), r.stderr.decode(errors="replace")))
    if binaire:
        return r.stdout
    return (r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")).strip()


class Tele:
    def __init__(self, serie):
        self.serie = serie

    def sh(self, commande, delai=60):
        return adb("shell", commande, serie=self.serie, delai=delai)

    def modifier(self, commande):
        """Commande qui change quelque chose : non exécutée en mode --essai."""
        if ESSAI:
            print("    [essai] adb shell " + commande)
            return "[essai]"
        return self.sh(commande)

    def prop(self, nom):
        return self.sh("getprop " + nom).strip()

    def paquets(self, option=""):
        sortie = self.sh("pm list packages " + option)
        return sorted({l.split(":", 1)[1].strip() for l in sortie.splitlines() if l.startswith("package:")})

    def desactives(self):
        return set(self.paquets("-d"))

    def accueil_actuel(self):
        s = self.sh("cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME")
        lignes = [l.strip() for l in s.splitlines() if "/" in l]
        return lignes[-1] if lignes else ""

    def activite_au_premier_plan(self):
        s = self.sh("dumpsys window windows")
        for l in s.splitlines():
            if "mCurrentFocus" in l or "mFocusedApp" in l:
                return l.strip()
        return ""

    def sdk(self):
        try:
            return int(self.prop("ro.build.version.sdk"))
        except ValueError:
            return 0


def tele_connectee():
    e = lire_etat()
    serie = e.get("appareil")
    if not serie:
        sys.exit("Aucune télé connectée. Lancez d'abord : python3 tv_allegement.py trouver puis connecter IP")
    etat = adb("get-state", serie=serie)
    if etat.strip() != "device":
        adb("connect", serie)
        time.sleep(2)
        etat = adb("get-state", serie=serie)
    if etat.strip() != "device":
        sys.exit("La télé %s ne répond pas (%s). Est-elle allumée et sur le même Wi-Fi ?" % (serie, etat))
    return Tele(serie)


# --------------------------------------------------------------------------- 1. trouver

def mes_adresses_ip():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))  # aucune donnée envoyée : sert à connaître l'interface active
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for r in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(r[4][0])
    except OSError:
        pass
    return [ip for ip in ips if ipaddress.ip_address(ip).is_private and not ip.startswith("127.")]


def port_ouvert(ip, port, delai=0.5):
    try:
        with socket.create_connection((ip, port), timeout=delai):
            return True
    except OSError:
        return False


def cmd_trouver(_args=None):
    titre("Recherche de la télé sur votre Wi-Fi")
    ips = mes_adresses_ip()
    if not ips:
        sys.exit("Impossible de déterminer l'adresse de cet ordinateur sur le réseau local.")
    cibles = []
    for ip in ips:
        reseau = ipaddress.ip_network(ip + "/24", strict=False)
        info("Ordinateur : %s → analyse du réseau %s" % (ip, reseau))
        cibles += [str(h) for h in reseau.hosts() if str(h) != ip]
    # 5555 = ADB réseau ; 8009 = Chromecast/Google Cast ; 6466/6467 = télécommande Android TV
    ports = (5555, 8009, 6466, 6467)
    trouves = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=200) as ex:
        futurs = {ex.submit(port_ouvert, h, p): (h, p) for h in cibles for p in ports}
        for f in concurrent.futures.as_completed(futurs):
            h, p = futurs[f]
            if f.result():
                trouves.setdefault(h, set()).add(p)
    mdns = adb("mdns", "services")
    if not trouves:
        alerte("Aucun appareil Android TV / Cast détecté.")
        info("Vérifiez que la télé est allumée et sur le même Wi-Fi que cet ordinateur.")
        return []
    resultats = []
    for h in sorted(trouves, key=lambda x: ipaddress.ip_address(x)):
        p = trouves[h]
        try:
            nom = socket.gethostbyaddr(h)[0]
        except OSError:
            nom = ""
        android_tv = bool(p & {6466, 6467})
        etat = "ADB ouvert ✔" if 5555 in p else "ADB fermé (à activer)"
        genre = "Android TV / Google TV" if android_tv else ("Appareil Cast" if 8009 in p else "Appareil réseau")
        print("    %-16s %-24s %-22s %s" % (h, genre, etat, nom))
        resultats.append((h, p))
    if mdns and "_adb" in mdns:
        info("Annonces ADB (mDNS) :\n" + mdns)
    if not any(5555 in p for _, p in resultats):
        print()
        alerte("Aucune télé n'a encore l'ADB réseau activé. Sur la télé :")
        guide_activer_adb()
    return resultats


def guide_activer_adb():
    print("""
    1. Paramètres → Système (ou Préférences de l'appareil) → À propos
    2. Descendez sur « Build » / « Version du build » et appuyez 7 fois sur OK
       → message « Vous êtes maintenant développeur ».
    3. Revenez en arrière → « Options pour les développeurs »
    4. Activez « Débogage USB » ET, s'il existe, « Débogage réseau » / « ADB over network ».
    (Les intitulés exacts varient un peu selon la marque.)
    Puis relancez : python3 tv_allegement.py trouver
""")


# --------------------------------------------------------------------------- 2. connecter

def cmd_connecter(args):
    ip = args.ip
    serie = ip if ":" in ip else ip + ":5555"
    titre("Connexion ADB à " + serie)
    info(adb("connect", serie))
    info("Si un message « Autoriser le débogage ? » apparaît sur la télé :")
    info("cochez « Toujours autoriser depuis cet ordinateur » puis choisissez OK.")
    for _ in range(60):
        etat = adb("get-state", serie=serie)
        if etat.strip() == "device":
            break
        time.sleep(2)
        if "unauthorized" in adb("devices"):
            print("    … en attente de votre accord sur l'écran de la télé", end="\r")
    else:
        sys.exit("\nLa télé n'a pas autorisé la connexion. Relancez après avoir accepté le message.")
    t = Tele(serie)
    fiche = {
        "marque": t.prop("ro.product.manufacturer"),
        "modele": t.prop("ro.product.model"),
        "android": t.prop("ro.build.version.release"),
        "sdk": t.sdk(),
        "accueil": t.accueil_actuel(),
    }
    print()
    ok("Connecté : %(marque)s %(modele)s — Android %(android)s (API %(sdk)s)" % fiche)
    info("Écran d'accueil actuel : " + (fiche["accueil"] or "inconnu"))
    e = lire_etat()
    e.update({"appareil": serie, "fiche": fiche})
    ecrire_etat(e)
    capture(t, "connexion")
    return t


# --------------------------------------------------------------------------- captures

def capture(t, nom):
    CAPTURES.mkdir(parents=True, exist_ok=True)
    n = len(list(CAPTURES.glob("*.png"))) + 1
    fichier = CAPTURES / ("%02d_%s.png" % (n, nom))
    donnees = adb("exec-out", "screencap", "-p", serie=t.serie, binaire=True)
    if not donnees.startswith(b"\x89PNG"):
        alerte("Capture impossible (%s)" % donnees[:80])
        return None
    fichier.write_bytes(donnees)
    ok("Capture : " + str(fichier.relative_to(RACINE)))
    generer_rapport()
    return fichier


def generer_rapport():
    e = lire_etat()
    lignes = []
    for f in sorted(CAPTURES.glob("*.png")):
        date = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        lignes.append('<figure><img src="captures/%s"><figcaption>%s — %s</figcaption></figure>'
                      % (html.escape(f.name), html.escape(f.stem.replace("_", " ")), date))
    journal = ""
    s = e.get("sauvegarde")
    if s and (Path(s) / "journal.json").exists():
        actions = json.loads((Path(s) / "journal.json").read_text(encoding="utf-8"))
        journal = "<h2>Journal des modifications (%d)</h2><ol>%s</ol>" % (
            len(actions), "".join("<li>%s</li>" % html.escape(decrire_action(a)) for a in actions))
    fiche = e.get("fiche", {})
    page = """<!DOCTYPE html><html lang="fr"><meta charset="utf-8"><title>Rapport télé</title>
<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;max-width:1100px;margin:auto;padding:24px}
img{width:100%%;border-radius:10px;border:1px solid #333}figure{margin:0 0 28px}figcaption{color:#aaa;margin-top:6px}
h1{font-weight:300}li{margin:4px 0}</style>
<h1>Rapport — %s %s (Android %s)</h1>%s<h2>Captures de la télé</h2>%s</html>""" % (
        html.escape(str(fiche.get("marque", ""))), html.escape(str(fiche.get("modele", ""))),
        html.escape(str(fiche.get("android", ""))), journal, "\n".join(lignes))
    (TRAVAIL / "rapport.html").write_text(page, encoding="utf-8")


def cmd_capture(args):
    capture(tele_connectee(), args.nom or "capture")


def cmd_rapport(_args):
    generer_rapport()
    chemin = TRAVAIL / "rapport.html"
    info("Rapport : " + str(chemin))
    webbrowser.open(chemin.as_uri())


# --------------------------------------------------------------------------- 3. sauvegarde + journal

def dossier_sauvegarde():
    s = lire_etat().get("sauvegarde")
    if not s or not Path(s).exists():
        sys.exit("Aucune sauvegarde : lancez d'abord « python3 tv_allegement.py sauvegarder ».")
    return Path(s)


def cmd_sauvegarder(_args=None):
    t = tele_connectee()
    e = lire_etat()
    ancienne = e.get("sauvegarde")
    if ancienne and Path(ancienne).exists():
        actions = json.loads((Path(ancienne) / "journal.json").read_text(encoding="utf-8"))
        if actions:
            ok("Une sauvegarde d'origine existe déjà (%s) avec %d modification(s) journalisée(s)." % (ancienne, len(actions)))
            info("Elle reste la référence de restauration : on ne l'écrase pas.")
            return Path(ancienne)
    titre("Sauvegarde complète de la télé (avant toute modification)")
    d = TRAVAIL / "sauvegardes" / datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    fichiers = {
        "proprietes.txt": "getprop",
        "paquets_tous.txt": "pm list packages -f -u",
        "paquets_desactives.txt": "pm list packages -d",
        "paquets_systeme.txt": "pm list packages -s",
        "paquets_installes_par_vous.txt": "pm list packages -3",
        "reglages_global.txt": "settings list global",
        "reglages_secure.txt": "settings list secure",
        "reglages_system.txt": "settings list system",
        "activites_preferees.txt": "dumpsys package preferred-activities",
        "accueil.txt": "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME",
    }
    for nom, commande in fichiers.items():
        (d / nom).write_text(t.sh(commande, delai=120), encoding="utf-8")
        ok("Sauvegardé : " + nom)
    instantane = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "appareil": t.serie,
        "desactives_avant": sorted(t.desactives()),
        "accueil_avant": t.accueil_actuel(),
        "reglages_avant": {"%s/%s" % (ns, k): t.sh("settings get %s %s" % (ns, k)).strip()
                           for ns, k, _ in C.REGLAGES_FLUIDITE},
    }
    (d / "instantane.json").write_text(json.dumps(instantane, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "journal.json").write_text("[]", encoding="utf-8")
    e["sauvegarde"] = str(d)
    ecrire_etat(e)
    ecrire_scripts_restauration(d, t.serie)
    capture(t, "avant_modifications")
    ok("Sauvegarde terminée : " + str(d))
    info("Script de restauration autonome : %s / %s" % (d / "restaurer.sh", d / "restaurer.bat"))
    return d


def journaliser(t, action):
    d = dossier_sauvegarde()
    j = d / "journal.json"
    actions = json.loads(j.read_text(encoding="utf-8"))
    action["quand"] = datetime.datetime.now().isoformat(timespec="seconds")
    actions.append(action)
    j.write_text(json.dumps(actions, indent=2, ensure_ascii=False), encoding="utf-8")
    ecrire_scripts_restauration(d, t.serie)


def decrire_action(a):
    if a["type"] == "desactivation":
        return "Désactivé : %s (%s)" % (a["paquet"], a.get("raison", ""))
    if a["type"] == "reglage":
        return "Réglage %s/%s : %s → %s" % (a["ns"], a["cle"], a["avant"], a["apres"])
    if a["type"] == "installation":
        return "Installé : " + a["paquet"]
    if a["type"] == "accueil":
        return "Écran d'accueil : %s → %s" % (a["avant"] or "(choix système)", a["apres"])
    return str(a)


def commandes_restauration(actions):
    """Commandes adb shell inverses, dans l'ordre inverse du journal."""
    cmds = []
    for a in reversed(actions):
        if a["type"] == "desactivation":
            cmds.append(("shell", "pm enable " + a["paquet"]))
        elif a["type"] == "reglage":
            if a["avant"] in ("", "null"):
                cmds.append(("shell", "settings delete %s %s" % (a["ns"], a["cle"])))
            else:
                cmds.append(("shell", "settings put %s %s %s" % (a["ns"], a["cle"], a["avant"])))
        elif a["type"] == "accueil":
            # Si l'accueil d'avant était le sélecteur système (ResolverActivity), rien à forcer :
            # une fois Accueil Zen désinstallé, Android revient seul à l'accueil d'origine.
            if a["avant"] and PKG_ZEN not in a["avant"] and "ResolverActivity" not in a["avant"]:
                cmds.append(("shell", "cmd package set-home-activity " + a["avant"]))
        elif a["type"] == "installation":
            cmds.append(("uninstall", a["paquet"]))
    return cmds


def ecrire_scripts_restauration(d, serie):
    actions = json.loads((d / "journal.json").read_text(encoding="utf-8"))
    cmds = commandes_restauration(actions)
    entete = "Restauration de la télé %s — %d modification(s) à annuler — généré le %s" % (
        serie, len(actions), datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
    sh = ["#!/bin/sh", "# " + entete,
          "# Usage : sh restaurer.sh   (adb doit être installé ; sinon ADB=/chemin/vers/adb sh restaurer.sh)",
          'ADB="${ADB:-adb}"', 'TV="%s"' % serie, '"$ADB" connect "$TV"']
    bat = ["@echo off", "chcp 65001 >nul", "rem " + entete,
           'if "%ADB%"=="" set ADB=adb', "set TV=%s" % serie, '"%ADB%" connect %TV%']
    for genre, c in cmds:
        if genre == "shell":
            sh.append('"$ADB" -s "$TV" shell %s' % c)
            bat.append('"%%ADB%%" -s %%TV%% shell %s' % c)
        else:
            sh.append('"$ADB" -s "$TV" uninstall %s' % c)
            bat.append('"%%ADB%%" -s %%TV%% uninstall %s' % c)
    sh += ['"$ADB" -s "$TV" shell input keyevent KEYCODE_HOME', 'echo "Restauration terminée."']
    bat += ['"%ADB%" -s %TV% shell input keyevent KEYCODE_HOME', "echo Restauration terminee.", "pause"]
    (d / "restaurer.sh").write_text("\n".join(sh) + "\n", encoding="utf-8")
    (d / "restaurer.bat").write_text("\r\n".join(bat) + "\r\n", encoding="utf-8")
    try:
        (d / "restaurer.sh").chmod(0o755)
    except OSError:
        pass


# --------------------------------------------------------------------------- 4. audit

def est_protege(p):
    if p in C.PROTEGES or p in C.ACCUEILS_ORIGINE:
        return True
    return any(m in p.lower() for m in C.MOTS_PROTEGES)


def analyser(t):
    tous = set(t.paquets())
    systeme = set(t.paquets("-s"))
    deja = t.desactives()
    actifs = tous - deja
    res = {"pubs": [], "telemetrie": [], "utiles": [], "suspects": [], "deja": sorted(deja & tous)}
    for p, d in C.PUBS.items():
        if p in actifs:
            res["pubs"].append((p, d))
    for p, d in C.TELEMETRIE.items():
        if p in actifs:
            res["telemetrie"].append((p, d))
    for p, d in C.UTILES.items():
        if p in actifs:
            res["utiles"].append((p, d))
    connus = set(C.PUBS) | set(C.TELEMETRIE) | set(C.UTILES)
    for p in sorted(actifs & systeme):
        if p in connus or est_protege(p) or not p.startswith(C.PREFIXES_FABRICANTS):
            continue
        bas = p.lower()
        if any(m in bas for m in C.MOTS_PUBS):
            res["suspects"].append((p, "fabricant — nom évoquant pubs/boutique/recommandations"))
        elif any(m in bas for m in C.MOTS_TELEMETRIE):
            res["suspects"].append((p, "fabricant — nom évoquant statistiques/rapports/télémétrie"))
    return res


def cmd_audit(_args=None):
    t = tele_connectee()
    titre("Audit (lecture seule — rien n'est modifié)")
    r = analyser(t)
    lignes = []

    def bloc(nom, liste):
        lignes.append("\n## " + nom)
        print("\n  " + nom)
        if not liste:
            print("    (rien trouvé)")
            lignes.append("(rien trouvé)")
        for p, d in liste:
            print("    - %-48s %s" % (p, d))
            lignes.append("- %s : %s" % (p, d))

    bloc("Publicités / recommandations sponsorisées", r["pubs"])
    bloc("Télémétrie / rapports", r["telemetrie"])
    bloc("Applis et fonctions que vous pourriez utiliser (question au cas par cas)", r["utiles"])
    bloc("Paquets du fabricant suspects (identifiés par leur nom — à confirmer un par un)", r["suspects"])
    print("\n  Déjà désactivés avant nous : %d paquet(s)" % len(r["deja"]))
    d = TRAVAIL / "audit.txt"
    TRAVAIL.mkdir(parents=True, exist_ok=True)
    d.write_text("Audit du %s\n%s" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "\n".join(lignes)), encoding="utf-8")
    ok("Audit enregistré : " + str(d))
    return r


# --------------------------------------------------------------------------- 5. alléger

def desactiver(t, paquet, raison, accueil_autorise=False):
    if est_protege(paquet) and not (accueil_autorise and paquet in C.ACCUEILS_ORIGINE):
        alerte("%s est protégé : ignoré." % paquet)
        return False
    if paquet in t.desactives():
        info("%s déjà désactivé." % paquet)
        return True
    sortie = t.modifier("pm disable-user --user 0 " + paquet)
    if ESSAI:
        return True
    if paquet in t.desactives():
        journaliser(t, {"type": "desactivation", "paquet": paquet, "raison": raison})
        ok("Désactivé : " + paquet)
        return True
    erreur("Refusé par le système pour %s : %s" % (paquet, sortie.splitlines()[-1] if sortie else "?"))
    return False


def cmd_alleger(_args=None):
    t = tele_connectee()
    dossier_sauvegarde()  # refuse de continuer sans sauvegarde
    r = analyser(t)
    titre("Allègement réversible (pm disable-user — jamais de désinstallation)")

    for cle, nom in (("pubs", "PUBLICITÉS / recommandations sponsorisées"), ("telemetrie", "TÉLÉMÉTRIE / rapports")):
        liste = r[cle]
        if not liste:
            info("%s : rien à désactiver sur cette télé." % nom)
            continue
        print("\n  %s — %d élément(s) :" % (nom, len(liste)))
        for p, d in liste:
            print("    - %-48s %s" % (p, d))
        if demander("Tout désactiver dans cette catégorie ?", True):
            for p, d in liste:
                desactiver(t, p, nom.split(" ")[0].lower())
        elif demander("Choisir un par un ?", False):
            for p, d in liste:
                if demander("Désactiver %s (%s) ?" % (p, d), True):
                    desactiver(t, p, nom.split(" ")[0].lower())
    capture(t, "apres_pubs_telemetrie")

    if r["utiles"]:
        print("\n  APPLIS ET FONCTIONS QUE VOUS POURRIEZ UTILISER — réponse par défaut : garder")
        for p, d in r["utiles"]:
            if demander("Désactiver « %s » (%s) ?" % (d, p), False):
                desactiver(t, p, "inutile selon vous")
        capture(t, "apres_applis")

    if r["suspects"]:
        print("\n  PAQUETS DU FABRICANT SUSPECTS — identifiés uniquement par leur nom.")
        print("  Si vous ne savez pas, répondez non : on pourra revenir dessus plus tard.")
        for p, d in r["suspects"]:
            if demander("Désactiver %s (%s) ?" % (p, d), False):
                desactiver(t, p, "fabricant (votre choix)")
                time.sleep(1)
                if t.sh("echo ok").strip() != "ok":
                    alerte("La télé ne répond plus normalement : restauration de ce paquet.")
                    t.modifier("pm enable " + p)
        capture(t, "apres_fabricant")

    print("\n  FLUIDITÉ : animations du système 2× plus rapides (0.5).")
    if demander("Accélérer les animations ?", True):
        for ns, k, v in C.REGLAGES_FLUIDITE:
            avant = t.sh("settings get %s %s" % (ns, k)).strip()
            if avant == v:
                continue
            t.modifier("settings put %s %s %s" % (ns, k, v))
            if not ESSAI:
                journaliser(t, {"type": "reglage", "ns": ns, "cle": k, "avant": avant, "apres": v})
                ok("%s = %s (avant : %s)" % (k, v, avant))

    t.modifier("input keyevent KEYCODE_HOME")
    time.sleep(3)
    capture(t, "accueil_apres_allegement")
    titre("Réglages à faire vous-même avec la télécommande (non modifiables proprement par ADB)")
    print("""    • Publicité personnalisée : Paramètres → Confidentialité → Annonces
      → « Désactiver la personnalisation des annonces » / « Supprimer l'identifiant publicitaire ».
    • Diagnostics : Paramètres → Confidentialité (ou Préférences de l'appareil)
      → « Utilisation et diagnostics » → désactiver.
    • Fabricant : désactivez aussi, si présents, « Statistiques d'utilisation », « Contenus
      recommandés » ou « Programme d'amélioration » dans les paramètres de la marque.
    (Les intitulés varient selon le modèle et la version.)""")


# --------------------------------------------------------------------------- 6. Accueil Zen

def applis_lancables(t):
    pkgs = []
    for cat in ("android.intent.category.LEANBACK_LAUNCHER", "android.intent.category.LAUNCHER"):
        s = t.sh("cmd package query-activities --brief -a android.intent.action.MAIN -c " + cat)
        for l in s.splitlines():
            l = l.strip()
            if "/" in l and " " not in l:
                p = l.split("/")[0]
                if p not in pkgs and p != PKG_ZEN:
                    pkgs.append(p)
    if not pkgs:
        pkgs = [p for p in t.paquets("-3") if p != PKG_ZEN]
    desactives = t.desactives()
    return [p for p in pkgs if p not in desactives]


def choisir_favoris(t):
    applis = applis_lancables(t)
    titre("Votre dock : choisissez vos applis préférées")
    for i, p in enumerate(applis, 1):
        print("    %2d. %-28s %s" % (i, C.NOMS_CONNUS.get(p, ""), p))
    print("\n  Tapez les numéros dans l'ordre voulu, séparés par des virgules (ex. 3,1,7).")
    print("  Entrée seule = sélection automatique (applis vidéo courantes).")
    while True:
        r = input("  ? Favoris : ").strip()
        if not r:
            return None
        try:
            choix = [applis[int(x) - 1] for x in r.replace(" ", "").split(",") if x]
            return ",".join(choix)
        except (ValueError, IndexError):
            print("    Numéros invalides, recommencez.")


def envoyer_fonds(t, dossier):
    dossier = Path(dossier).expanduser()
    images = [f for f in sorted(dossier.iterdir()) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not images:
        alerte("Aucune image .jpg/.png/.webp dans " + str(dossier))
        return
    cible = "/sdcard/Android/data/%s/files/fonds/" % PKG_ZEN
    t.modifier("mkdir -p " + cible)
    for f in images:
        if ESSAI:
            print("    [essai] adb push %s %s" % (f, cible))
            continue
        adb("push", str(f), cible, serie=t.serie, delai=300)
        ok("Fond envoyé : " + f.name)


def cmd_fonds(args):
    t = tele_connectee()
    envoyer_fonds(t, args.dossier)
    t.modifier("am start -n %s --es intervalle %d" % (ACTIVITE_ZEN, args.intervalle))
    time.sleep(4)
    capture(t, "nouveaux_fonds")


def cmd_installer(args=None):
    t = tele_connectee()
    dossier_sauvegarde()
    titre("Installation d'Accueil Zen")
    if t.sdk() < 24:
        sys.exit("Cette télé est sous Android %s : Accueil Zen nécessite Android 7 minimum." % t.prop("ro.build.version.release"))
    if not APK.exists():
        sys.exit("APK introuvable : " + str(APK))
    accueil_avant = t.accueil_actuel()
    deja = PKG_ZEN in t.paquets()
    if ESSAI:
        print("    [essai] adb install -r " + str(APK))
    else:
        sortie = adb("install", "-r", str(APK), serie=t.serie, delai=300)
        if "Success" not in sortie:
            sys.exit("Installation refusée : " + sortie)
        ok("Accueil Zen installé.")
        if not deja:
            journaliser(t, {"type": "installation", "paquet": PKG_ZEN})

    favoris = choisir_favoris(t)
    intervalle = getattr(args, "intervalle", 90) or 90
    extra = " --es intervalle %d" % intervalle
    if favoris:
        extra += " --es favoris " + favoris
    t.modifier("am start -n " + ACTIVITE_ZEN + extra)
    time.sleep(5)
    capture(t, "accueil_zen_premier_lancement")

    if demander("Ajouter vos propres photos nature depuis un dossier de cet ordinateur ?", False):
        envoyer_fonds(t, input("  ? Chemin du dossier : ").strip().strip('"'))
        t.modifier("am start -n " + ACTIVITE_ZEN + " --es intervalle %d" % intervalle)
        time.sleep(4)

    print("\n  Accueil Zen va devenir l'écran d'accueil (bouton Accueil de la télécommande).")
    if not demander("Le définir comme écran d'accueil ?", True):
        info("D'accord : il reste disponible dans la liste des applis.")
        return
    t.modifier("cmd package set-home-activity " + ACTIVITE_ZEN)
    if not ESSAI:
        journaliser(t, {"type": "accueil", "avant": accueil_avant, "apres": ACTIVITE_ZEN})
    t.modifier("input keyevent KEYCODE_HOME")
    time.sleep(4)
    capture(t, "bouton_accueil")
    premier_plan = t.activite_au_premier_plan()
    if PKG_ZEN in premier_plan:
        ok("Le bouton Accueil ouvre bien Accueil Zen.")
    else:
        alerte("Le bouton Accueil ouvre encore : " + (premier_plan or "?"))
        origine = [p for p in C.ACCUEILS_ORIGINE if p in t.paquets() and p not in t.desactives()]
        if origine:
            print("""
  Certaines télés (Google TV notamment) imposent leur accueil d'origine.
  Solution réversible : désactiver l'accueil d'origine (%s).
  Conséquences : plus de suggestions/pubs ni de profils Google TV ; les Réglages restent
  accessibles via la tuile « Réglages » d'Accueil Zen ; le bouton Sources/Input de la
  télécommande continue de fonctionner. Tout se réactive avec « restaurer ».""" % ", ".join(origine))
            if demander("Désactiver l'accueil d'origine ?", False):
                for p in origine:
                    desactiver(t, p, "remplacé par Accueil Zen", accueil_autorise=True)
                t.modifier("cmd package set-home-activity " + ACTIVITE_ZEN)
                t.modifier("input keyevent KEYCODE_HOME")
                time.sleep(4)
                capture(t, "bouton_accueil_apres_desactivation")
                pp = t.activite_au_premier_plan()
                if PKG_ZEN in pp:
                    ok("Le bouton Accueil ouvre maintenant Accueil Zen.")
                else:
                    alerte("Toujours pas : %s — lancez « restaurer » si quelque chose vous gêne." % pp)
    t.modifier("input keyevent KEYCODE_DPAD_DOWN")
    time.sleep(2)
    capture(t, "toutes_les_applis")
    t.modifier("input keyevent KEYCODE_BACK")
    time.sleep(1)


# --------------------------------------------------------------------------- 7. restaurer

def cmd_restaurer(_args=None):
    t = tele_connectee()
    d = dossier_sauvegarde()
    actions = json.loads((d / "journal.json").read_text(encoding="utf-8"))
    titre("Restauration — %d modification(s) à annuler" % len(actions))
    if not actions:
        ok("Rien à restaurer : la télé est dans l'état sauvegardé.")
        return
    for a in actions:
        info(decrire_action(a))
    if not demander("Tout annuler et revenir à l'état sauvegardé ?", True):
        return
    capture(t, "avant_restauration")
    for genre, c in commandes_restauration(actions):
        if genre == "shell":
            sortie = t.modifier(c)
        elif ESSAI:
            sortie = "[essai] adb uninstall " + c
            print("    " + sortie)
        else:
            sortie = adb("uninstall", c, serie=t.serie)
        info("%s → %s" % (c, (sortie.splitlines() or [""])[-1]))
    if ESSAI:
        return
    # Vérification : les paquets désactivés doivent correspondre exactement à l'instantané.
    instantane = json.loads((d / "instantane.json").read_text(encoding="utf-8"))
    avant = set(instantane["desactives_avant"])
    maintenant = t.desactives()
    if maintenant == avant:
        ok("Paquets désactivés : identiques à la sauvegarde.")
    else:
        alerte("Écart — en plus : %s ; en moins : %s" % (sorted(maintenant - avant), sorted(avant - maintenant)))
    t.modifier("input keyevent KEYCODE_HOME")
    time.sleep(4)
    capture(t, "apres_restauration")
    archive = d / ("journal_restaure_%s.json" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    (d / "journal.json").rename(archive)
    (d / "journal.json").write_text("[]", encoding="utf-8")
    ecrire_scripts_restauration(d, t.serie)
    ok("Restauration terminée (journal archivé : %s)." % archive.name)


# --------------------------------------------------------------------------- parcours complet

def cmd_tout(args):
    titre("Parcours complet : trouver → connecter → sauvegarder → alléger → Accueil Zen")
    e = lire_etat()
    serie = e.get("appareil")
    if not serie or adb("get-state", serie=serie).strip() != "device":
        res = cmd_trouver()
        ouverts = [h for h, p in res if 5555 in p]
        if not ouverts:
            sys.exit("Activez l'ADB sur la télé (voir ci-dessus) puis relancez « tout ».")
        ip = ouverts[0]
        if len(ouverts) > 1:
            for i, h in enumerate(ouverts, 1):
                print("    %d. %s" % (i, h))
            ip = ouverts[int(input("  ? Numéro de votre télé : ")) - 1]
        args.ip = ip
        cmd_connecter(args)
    cmd_sauvegarder()
    cmd_audit()
    if demander("Passer à l'allègement (chaque catégorie vous sera demandée) ?", True):
        cmd_alleger()
    if demander("Installer l'écran d'accueil Accueil Zen ?", True):
        cmd_installer(args)
    generer_rapport()
    titre("Terminé")
    d = dossier_sauvegarde()
    ok("Rapport illustré : " + str(TRAVAIL / "rapport.html"))
    ok("Restaurer à tout moment : python3 tv_allegement.py restaurer")
    ok("…ou sans Python : " + str(d / ("restaurer.bat" if os.name == "nt" else "restaurer.sh")))
    webbrowser.open((TRAVAIL / "rapport.html").as_uri())


def main():
    global ESSAI
    p = argparse.ArgumentParser(description="Allègement réversible d'Android TV + Accueil Zen")
    p.add_argument("--essai", action="store_true", help="affiche les modifications sans les faire")
    sp = p.add_subparsers(dest="commande", required=True)
    sp.add_parser("trouver").set_defaults(f=cmd_trouver)
    c = sp.add_parser("connecter")
    c.add_argument("ip")
    c.set_defaults(f=cmd_connecter)
    sp.add_parser("sauvegarder").set_defaults(f=cmd_sauvegarder)
    sp.add_parser("audit").set_defaults(f=cmd_audit)
    sp.add_parser("alleger").set_defaults(f=cmd_alleger)
    i = sp.add_parser("installer")
    i.add_argument("--intervalle", type=int, default=90, help="secondes entre deux fonds (défaut 90)")
    i.set_defaults(f=cmd_installer)
    f = sp.add_parser("fonds")
    f.add_argument("dossier")
    f.add_argument("--intervalle", type=int, default=90)
    f.set_defaults(f=cmd_fonds)
    k = sp.add_parser("capture")
    k.add_argument("nom", nargs="?")
    k.set_defaults(f=cmd_capture)
    sp.add_parser("restaurer").set_defaults(f=cmd_restaurer)
    sp.add_parser("rapport").set_defaults(f=cmd_rapport)
    t = sp.add_parser("tout")
    t.add_argument("--intervalle", type=int, default=90)
    t.set_defaults(f=cmd_tout, ip=None)
    a = p.parse_args()
    ESSAI = a.essai
    try:
        a.f(a)
    except KeyboardInterrupt:
        print("\nInterrompu. Rien n'est perdu : le journal et la sauvegarde sont à jour.")


if __name__ == "__main__":
    main()
