"""Catalogue des paquets Android TV connus, utilisé par tv_allegement.py.

IMPORTANT — honnêteté :
* Les noms de paquets ci-dessous sont des noms connus d'Android TV / Google TV. Le script ne
  propose QUE ceux qui sont réellement présents sur la télé, et vérifie l'état après chaque action.
* Les applis des fabricants (TCL, Sony, Philips, Hisense, Xiaomi…) varient selon le modèle et le
  firmware : elles ne sont PAS listées en dur. Le script les repère par mots-clés dans leur nom
  (ex. « promo », « recommend », « analytics ») et vous demande pour CHACUNE avant d'agir.
* Méthode utilisée : « pm disable-user » = désactivation réversible. Jamais de désinstallation.
"""

# Publicités / contenus sponsorisés : proposés par lot (vous validez la liste).
PUBS = {
    "com.google.android.tvrecommendations": "Recommandations TV : contenus sponsorisés et suggestions sur l'accueil",
    "com.google.android.leanbacklauncher.recommendations": "Recommandations de l'ancien accueil Android TV",
}

# Télémétrie / rapports envoyés au fabricant ou à Google : proposés par lot.
TELEMETRIE = {
    "com.google.android.feedback": "Envoi de rapports de plantage et d'avis à Google",
}

# Applis et fonctions que vous pourriez utiliser : question au cas par cas, réponse par défaut = GARDER.
UTILES = {
    "com.google.android.katniss": "Recherche vocale / Assistant Google (bouton micro de la télécommande)",
    "com.google.android.apps.mediashell": "Chromecast intégré (diffuser depuis votre téléphone)",
    "com.google.android.youtube.tv": "YouTube",
    "com.google.android.youtube.tvmusic": "YouTube Music",
    "com.google.android.youtube.tvkids": "YouTube Kids",
    "com.google.android.videos": "Google TV / Play Films (location et achat de films)",
    "com.google.android.play.games": "Google Play Jeux",
    "com.google.android.apps.tv.dreamx": "Mode Ambiant Google TV (écran de veille photos/infos, peut afficher des suggestions)",
    "com.google.android.backdrop": "Mode Ambiant / écran de veille Android TV",
    "com.google.android.tv": "Chaînes en direct (Live Channels)",
    "com.google.android.music": "Google Play Musique (service arrêté par Google)",
    "com.netflix.ninja": "Netflix",
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.disney.disneyplus": "Disney+",
    "com.spotify.tv.android": "Spotify",
    "com.plexapp.android": "Plex",
    "com.apple.atve.androidtv.appletv": "Apple TV+",
    "com.facebook.katana": "Facebook",
}

# Accueils d'origine : jamais touchés pendant l'allègement. Proposés UNIQUEMENT à l'étape
# d'installation d'Accueil Zen, après qu'il fonctionne, et avec votre accord.
ACCUEILS_ORIGINE = {
    "com.google.android.apps.tv.launcherx": "Accueil Google TV",
    "com.google.android.tvlauncher": "Accueil Android TV",
    "com.google.android.leanbacklauncher": "Ancien accueil Android TV",
}

# Jamais désactivés, quoi qu'il arrive.
PROTEGES = {
    "android", "com.android.systemui", "com.android.settings", "com.android.tv.settings",
    "com.google.android.gms", "com.google.android.gsf", "com.android.vending",
    "com.android.providers.settings", "com.android.providers.tv", "com.android.providers.media",
    "com.android.providers.downloads", "com.android.providers.contacts",
    "com.android.packageinstaller", "com.google.android.packageinstaller",
    "com.android.permissioncontroller", "com.google.android.permissioncontroller",
    "com.google.android.leanback.ime", "com.google.android.inputmethod.latin",
    "com.google.android.tv.remote.service", "com.google.android.tvsetup",
    "com.google.android.tungsten.setupwraith", "com.android.bluetooth",
    "com.android.shell", "com.android.webview", "com.google.android.webview",
    "com.google.android.ext.services", "com.android.externalstorage",
    "com.android.tv.frameworkpackagestubs", "com.android.inputdevices",
    "com.android.keychain", "com.android.certinstaller", "com.android.networkstack",
    "com.google.android.networkstack", "com.android.wifi.resources",
    "com.lourdes.accueilzen",
}

# Mots qui, dans un nom de paquet, signalent un composant système à ne jamais proposer.
MOTS_PROTEGES = (
    "setting", "systemui", "input", ".ime", "keyboard", "remote", "bluetooth", "hdmi", "cec",
    "tvinput", "tuner", "provider", "ota", "update", "upgrade", "setup", "audio", "sound",
    "picture", "display", "power", "framework", "launcher", "wifi", "network", "factory",
    "permission", "installer", "webview", "media.", "mediaprovider", "storage", "security",
    "keychain", "certinstaller", "inputmethod", "accessib", "voice.interaction", "pq",
)

# Espaces de noms des fabricants / fondeurs de puces.
PREFIXES_FABRICANTS = (
    "com.tcl.", "com.sony.", "com.tpvision.", "com.philips.", "com.hisense.", "com.jamdeo.",
    "com.mitv.", "com.xiaomi.", "com.miui.", "com.skyworth.", "com.sharp.", "com.nvidia.",
    "com.mediatek.", "com.droidlogic.", "com.realtek.", "com.amlogic.", "com.toshiba.",
    "com.panasonic.", "com.thomson.", "com.metz.", "com.haier.", "com.changhong.",
    "com.vestel.", "com.sei.", "com.walton.", "com.onn.", "com.chromecast.",
)

# Mots-clés suspects (pubs / télémétrie) chez les fabricants. Question au cas par cas.
MOTS_PUBS = ("promo", "advert", ".ad.", ".ads", "adservice", "adsdk", "recommend", "sponsor",
             "shop", "store", "market", "select", "partner", "channelfeed", "banner", "deal")
MOTS_TELEMETRIE = ("analytic", "statist", "report", "track", "logger", "logcollect", "log.",
                   "diagnos", "crash", "feedback", "survey", "dataservice", "collect", "usage")

# Réglages de fluidité proposés (valeur d'origine sauvegardée et restaurable).
REGLAGES_FLUIDITE = [
    ("global", "window_animation_scale", "0.5"),
    ("global", "transition_animation_scale", "0.5"),
    ("global", "animator_duration_scale", "0.5"),
]

# Noms lisibles pour le choix des favoris du dock.
NOMS_CONNUS = {
    **{k: v.split(" (")[0] for k, v in UTILES.items()},
    "com.google.android.youtube.tv": "YouTube",
    "com.canal.android.canal": "CANAL+",
    "fr.francetv.pluzz": "france.tv",
    "tv.arte.plus7": "ARTE",
    "fr.m6.m6replay": "M6+",
    "fr.tf1.mytf1": "TF1+",
    "tv.molotov.app": "Molotov",
    "org.xbmc.kodi": "Kodi",
    "com.google.android.apps.youtube.kids": "YouTube Kids",
    "com.deezer.android.tv": "Deezer",
    "com.android.vending": "Play Store",
}
