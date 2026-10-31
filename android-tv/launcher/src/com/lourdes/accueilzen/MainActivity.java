package com.lourdes.accueilzen;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ObjectAnimator;
import android.animation.PropertyValuesHolder;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewOutlineProvider;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.LinearInterpolator;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.InputStream;
import java.text.Collator;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

/**
 * Accueil Zen : écran d'accueil minimaliste pour Android TV.
 * Fond nature qui tourne en fondu, horloge, dock d'applis favorites
 * et grille "Toutes les applis". Aucune publicité, aucune connexion réseau.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "accueil_zen";
    private static final String CLE_FAVORIS = "favoris";
    private static final String CLE_INTERVALLE = "intervalle_s";
    private static final long INTERVALLE_DEFAUT_S = 90;
    private static final int COLONNES = 6;

    /** Applis proposées dans le dock au premier lancement, si elles sont installées. */
    private static final String[] FAVORIS_PAR_DEFAUT = {
            "com.netflix.ninja",
            "com.google.android.youtube.tv",
            "com.amazon.amazonvideo.livingroom",
            "com.disney.disneyplus",
            "com.spotify.tv.android",
            "com.plexapp.android",
            "org.xbmc.kodi",
    };

    static final class Appli {
        String pkg;
        String nom;
        Drawable banniere;
        Drawable icone;
        Intent lancement;
    }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Random hasard = new Random();
    private SharedPreferences prefs;

    private ImageView fondA, fondB;
    private boolean fondAVisible = true;
    private TextView horloge, date, nomFocus, aide;
    private LinearLayout dock;
    private HorizontalScrollView dockDefilement;
    private FrameLayout calqueApplis;
    private LinearLayout grilleApplis;
    private ScrollView grilleDefilement;

    private final Map<String, Appli> applis = new LinkedHashMap<String, Appli>();
    private final List<String> fonds = new ArrayList<String>();
    private int indexFond = -1;
    private ObjectAnimator zoom;
    private boolean actif;

    private final BroadcastReceiver paquetsModifies = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            chargerApplis();
        }
    };

    // ------------------------------------------------------------------ cycle de vie

    @Override
    protected void onCreate(Bundle etat) {
        super.onCreate(etat);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        appliquerExtras(getIntent());
        setContentView(construireInterface());
        chargerApplis();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (appliquerExtras(intent)) {
            chargerApplis();
        }
        masquerToutesApplis();
    }

    @Override
    protected void onResume() {
        super.onResume();
        actif = true;
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_PACKAGE_ADDED);
        f.addAction(Intent.ACTION_PACKAGE_REMOVED);
        f.addAction(Intent.ACTION_PACKAGE_CHANGED);
        f.addDataScheme("package");
        registerReceiver(paquetsModifies, f);
        majHorloge();
        listerFonds();
        fondSuivant();
        chargerApplis();
    }

    @Override
    protected void onPause() {
        super.onPause();
        actif = false;
        handler.removeCallbacksAndMessages(null);
        if (zoom != null) zoom.cancel();
        try {
            unregisterReceiver(paquetsModifies);
        } catch (IllegalArgumentException ignore) {
        }
    }

    /** Réglages transmis par le script d'installation (adb shell am start ... --es favoris ...). */
    private boolean appliquerExtras(Intent intent) {
        if (intent == null || intent.getExtras() == null) return false;
        boolean modifie = false;
        SharedPreferences.Editor e = prefs.edit();
        if (intent.getBooleanExtra("reinitialiser", false)) {
            e.clear();
            modifie = true;
        }
        String favoris = intent.getStringExtra("favoris");
        if (favoris != null) {
            e.putString(CLE_FAVORIS, favoris.trim());
            modifie = true;
        }
        String intervalle = intent.getStringExtra("intervalle");
        if (intervalle != null) {
            try {
                long s = Long.parseLong(intervalle.trim());
                if (s >= 10) {
                    e.putLong(CLE_INTERVALLE, s);
                    modifie = true;
                }
            } catch (NumberFormatException ignore) {
            }
        }
        e.apply();
        return modifie;
    }

    // ------------------------------------------------------------------ interface

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics()));
    }

    private TextView texte(float sp, int couleur, boolean leger) {
        TextView t = new TextView(this);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(couleur);
        t.setTypeface(Typeface.create(leger ? "sans-serif-light" : "sans-serif", Typeface.NORMAL));
        t.setShadowLayer(dp(6), 0, dp(1), 0x99000000);
        return t;
    }

    private View construireInterface() {
        FrameLayout racine = new FrameLayout(this);
        racine.setBackgroundColor(Color.BLACK);

        fondA = new ImageView(this);
        fondB = new ImageView(this);
        for (ImageView iv : new ImageView[]{fondA, fondB}) {
            iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
            racine.addView(iv, new FrameLayout.LayoutParams(-1, -1));
        }
        fondB.setAlpha(0f);

        // Voile dégradé pour la lisibilité du dock et de l'horloge.
        View voile = new View(this);
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0x55000000, 0x00000000, 0x00000000, 0xAA000000});
        voile.setBackground(g);
        racine.addView(voile, new FrameLayout.LayoutParams(-1, -1));

        // Horloge et date en haut à droite.
        LinearLayout coin = new LinearLayout(this);
        coin.setOrientation(LinearLayout.VERTICAL);
        coin.setGravity(Gravity.END);
        horloge = texte(64, Color.WHITE, true);
        date = texte(20, 0xDDFFFFFF, false);
        coin.addView(horloge);
        coin.addView(date);
        FrameLayout.LayoutParams lpCoin = new FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.END);
        lpCoin.setMargins(0, dp(36), dp(56), 0);
        racine.addView(coin, lpCoin);

        // Dock en bas, centré.
        LinearLayout bas = new LinearLayout(this);
        bas.setOrientation(LinearLayout.VERTICAL);
        bas.setGravity(Gravity.CENTER_HORIZONTAL);
        bas.setClipChildren(false);
        bas.setClipToPadding(false);

        nomFocus = texte(18, Color.WHITE, false);
        nomFocus.setGravity(Gravity.CENTER);
        nomFocus.setAlpha(0f);
        bas.addView(nomFocus, new LinearLayout.LayoutParams(-2, -2));

        dockDefilement = new HorizontalScrollView(this);
        dockDefilement.setHorizontalScrollBarEnabled(false);
        dockDefilement.setClipChildren(false);
        dockDefilement.setClipToPadding(false);
        dockDefilement.setFillViewport(false);
        dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setClipChildren(false);
        dock.setClipToPadding(false);
        dock.setPadding(dp(24), dp(20), dp(24), dp(20));
        dockDefilement.addView(dock);
        bas.addView(dockDefilement, new LinearLayout.LayoutParams(-2, -2));

        aide = texte(13, 0x99FFFFFF, false);
        aide.setText("▼ Toutes les applis   ·   appui long sur OK : options");
        bas.addView(aide);

        FrameLayout.LayoutParams lpBas = new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM);
        lpBas.bottomMargin = dp(28);
        racine.addView(bas, lpBas);

        // Calque "Toutes les applis".
        calqueApplis = new FrameLayout(this);
        calqueApplis.setBackgroundColor(0xD9101418);
        calqueApplis.setVisibility(View.GONE);
        LinearLayout colonne = new LinearLayout(this);
        colonne.setOrientation(LinearLayout.VERTICAL);
        colonne.setPadding(dp(56), dp(36), dp(56), dp(16));
        TextView titre = texte(30, Color.WHITE, true);
        titre.setText("Toutes les applis");
        colonne.addView(titre);
        TextView sousTitre = texte(14, 0x99FFFFFF, false);
        sousTitre.setText("OK : ouvrir   ·   appui long sur OK : ajouter au dock / retirer   ·   Retour : fermer");
        colonne.addView(sousTitre);
        grilleDefilement = new ScrollView(this);
        grilleDefilement.setVerticalScrollBarEnabled(false);
        grilleDefilement.setClipChildren(false);
        grilleDefilement.setClipToPadding(false);
        grilleApplis = new LinearLayout(this);
        grilleApplis.setOrientation(LinearLayout.VERTICAL);
        grilleApplis.setClipChildren(false);
        grilleApplis.setClipToPadding(false);
        grilleApplis.setPadding(dp(16), dp(20), dp(16), dp(40));
        grilleDefilement.addView(grilleApplis);
        LinearLayout.LayoutParams lpG = new LinearLayout.LayoutParams(-1, 0, 1f);
        lpG.topMargin = dp(8);
        colonne.addView(grilleDefilement, lpG);
        calqueApplis.addView(colonne, new FrameLayout.LayoutParams(-1, -1));
        racine.addView(calqueApplis, new FrameLayout.LayoutParams(-1, -1));

        return racine;
    }

    /** Tuile arrondie façon Apple TV : bannière 16:9 ou icône centrée sur fond givré. */
    private View tuile(final Appli a, Drawable symbole, String nomSymbole, int largeurDp, final boolean dansDock) {
        final int largeur = dp(largeurDp);
        final int hauteur = largeur * 9 / 16;
        final FrameLayout t = new FrameLayout(this);
        GradientDrawable fondTuile = new GradientDrawable();
        fondTuile.setCornerRadius(dp(10));
        fondTuile.setColor(0x40FFFFFF);
        t.setBackground(fondTuile);
        t.setClipToOutline(true);
        t.setOutlineProvider(ViewOutlineProvider.BACKGROUND);
        t.setElevation(dp(2));
        t.setFocusable(true);
        t.setFocusableInTouchMode(true);

        final String nom = a != null ? a.nom : nomSymbole;
        if (a != null && a.banniere != null) {
            ImageView iv = new ImageView(this);
            iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
            iv.setImageDrawable(a.banniere);
            t.addView(iv, new FrameLayout.LayoutParams(-1, -1));
        } else {
            LinearLayout centre = new LinearLayout(this);
            centre.setOrientation(LinearLayout.VERTICAL);
            centre.setGravity(Gravity.CENTER);
            ImageView iv = new ImageView(this);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            iv.setImageDrawable(a != null ? a.icone : symbole);
            int c = hauteur * 46 / 100;
            centre.addView(iv, new LinearLayout.LayoutParams(c, c));
            TextView l = texte(11, Color.WHITE, false);
            l.setText(nom);
            l.setSingleLine(true);
            l.setEllipsize(TextUtils.TruncateAt.END);
            l.setGravity(Gravity.CENTER);
            l.setPadding(dp(6), dp(4), dp(6), 0);
            centre.addView(l, new LinearLayout.LayoutParams(-1, -2));
            t.addView(centre, new FrameLayout.LayoutParams(-1, -1));
        }

        t.setOnFocusChangeListener(new View.OnFocusChangeListener() {
            @Override
            public void onFocusChange(View v, boolean focus) {
                float s = focus ? 1.14f : 1f;
                v.animate().scaleX(s).scaleY(s).translationZ(focus ? dp(14) : 0)
                        .setDuration(160).setInterpolator(new DecelerateInterpolator()).start();
                if (focus && dansDock) {
                    nomFocus.setText(nom);
                    nomFocus.animate().alpha(1f).setDuration(160).start();
                }
            }
        });

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(largeur, hauteur);
        int marge = dp(dansDock ? 10 : 10);
        lp.setMargins(marge, marge, marge, marge);
        t.setLayoutParams(lp);
        return t;
    }

    // ------------------------------------------------------------------ applis

    private void chargerApplis() {
        new Thread(new Runnable() {
            @Override
            public void run() {
                final Map<String, Appli> res = lireApplisInstallees();
                handler.post(new Runnable() {
                    @Override
                    public void run() {
                        applis.clear();
                        applis.putAll(res);
                        construireDock();
                        if (calqueApplis.getVisibility() == View.VISIBLE) construireGrille();
                    }
                });
            }
        }).start();
    }

    private Map<String, Appli> lireApplisInstallees() {
        PackageManager pm = getPackageManager();
        Map<String, Appli> res = new HashMap<String, Appli>();
        String[] categories = {"android.intent.category.LEANBACK_LAUNCHER", Intent.CATEGORY_LAUNCHER};
        for (String cat : categories) {
            Intent i = new Intent(Intent.ACTION_MAIN);
            i.addCategory(cat);
            List<ResolveInfo> liste = pm.queryIntentActivities(i, 0);
            for (ResolveInfo ri : liste) {
                String pkg = ri.activityInfo.packageName;
                if (pkg.equals(getPackageName()) || res.containsKey(pkg)) continue;
                Appli a = new Appli();
                a.pkg = pkg;
                CharSequence n = ri.loadLabel(pm);
                a.nom = n != null ? n.toString() : pkg;
                try {
                    a.banniere = ri.activityInfo.loadBanner(pm);
                    if (a.banniere == null) a.banniere = ri.activityInfo.applicationInfo.loadBanner(pm);
                } catch (Exception ignore) {
                }
                a.icone = ri.loadIcon(pm);
                Intent l = pm.getLeanbackLaunchIntentForPackage(pkg);
                if (l == null) l = pm.getLaunchIntentForPackage(pkg);
                if (l == null) {
                    l = new Intent(Intent.ACTION_MAIN);
                    l.addCategory(cat);
                    l.setComponent(new ComponentName(pkg, ri.activityInfo.name));
                }
                l.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                a.lancement = l;
                res.put(pkg, a);
            }
        }
        final Collator coll = Collator.getInstance(Locale.FRENCH);
        List<Appli> tri = new ArrayList<Appli>(res.values());
        Collections.sort(tri, new Comparator<Appli>() {
            @Override
            public int compare(Appli x, Appli y) {
                return coll.compare(x.nom, y.nom);
            }
        });
        Map<String, Appli> ordonne = new LinkedHashMap<String, Appli>();
        for (Appli a : tri) ordonne.put(a.pkg, a);
        return ordonne;
    }

    private List<String> favoris() {
        List<String> res = new ArrayList<String>();
        String s = prefs.getString(CLE_FAVORIS, null);
        if (s == null) {
            for (String p : FAVORIS_PAR_DEFAUT) if (applis.containsKey(p)) res.add(p);
            if (res.isEmpty()) {
                for (String p : applis.keySet()) {
                    if (res.size() >= 5) break;
                    res.add(p);
                }
            }
            return res;
        }
        for (String p : s.split(",")) {
            p = p.trim();
            if (p.length() > 0 && !res.contains(p)) res.add(p);
        }
        return res;
    }

    private void enregistrerFavoris(List<String> liste) {
        prefs.edit().putString(CLE_FAVORIS, TextUtils.join(",", liste)).apply();
    }

    private void construireDock() {
        View focusAvant = getCurrentFocus();
        int indexFocus = focusAvant != null && focusAvant.getParent() == dock ? dock.indexOfChild(focusAvant) : 0;
        dock.removeAllViews();
        for (String p : favoris()) {
            final Appli a = applis.get(p);
            if (a == null) continue; // désactivée ou désinstallée : on la garde en mémoire, sans tuile
            View t = tuile(a, null, null, 136, true);
            t.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    lancer(a);
                }
            });
            t.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View v) {
                    optionsDock(a);
                    return true;
                }
            });
            dock.addView(t);
        }
        View tApplis = tuile(null, new Pictogramme(Pictogramme.GRILLE), "Applis", 136, true);
        tApplis.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                afficherToutesApplis();
            }
        });
        dock.addView(tApplis);
        View tReglages = tuile(null, new Pictogramme(Pictogramme.ENGRENAGE), "Réglages", 136, true);
        tReglages.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                ouvrir(new Intent(Settings.ACTION_SETTINGS));
            }
        });
        dock.addView(tReglages);

        if (calqueApplis.getVisibility() != View.VISIBLE) {
            View cible = dock.getChildAt(Math.min(Math.max(indexFocus, 0), dock.getChildCount() - 1));
            if (cible != null) cible.requestFocus();
        }
    }

    private void construireGrille() {
        grilleApplis.removeAllViews();
        LinearLayout ligne = null;
        int n = 0;
        for (final Appli a : applis.values()) {
            if (n % COLONNES == 0) {
                ligne = new LinearLayout(this);
                ligne.setOrientation(LinearLayout.HORIZONTAL);
                ligne.setClipChildren(false);
                ligne.setClipToPadding(false);
                grilleApplis.addView(ligne);
            }
            View t = tuile(a, null, null, 128, false);
            t.setTag(n / COLONNES);
            t.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    lancer(a);
                }
            });
            t.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View v) {
                    basculerFavori(a);
                    return true;
                }
            });
            ligne.addView(t);
            n++;
        }
        if (grilleApplis.getChildCount() > 0) {
            ViewGroup premiere = (ViewGroup) grilleApplis.getChildAt(0);
            if (premiere.getChildCount() > 0) premiere.getChildAt(0).requestFocus();
        }
    }

    private void basculerFavori(Appli a) {
        List<String> fav = favoris();
        if (fav.contains(a.pkg)) {
            fav.remove(a.pkg);
            Toast.makeText(this, a.nom + " retirée du dock", Toast.LENGTH_SHORT).show();
        } else {
            fav.add(a.pkg);
            Toast.makeText(this, a.nom + " ajoutée au dock", Toast.LENGTH_SHORT).show();
        }
        enregistrerFavoris(fav);
        construireDock();
    }

    private void optionsDock(final Appli a) {
        final String[] choix = {"Déplacer vers la gauche", "Déplacer vers la droite", "Retirer du dock", "Infos sur l'appli"};
        new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle(a.nom)
                .setItems(choix, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int quel) {
                        List<String> fav = favoris();
                        int i = fav.indexOf(a.pkg);
                        if (quel == 0 && i > 0) {
                            Collections.swap(fav, i, i - 1);
                        } else if (quel == 1 && i >= 0 && i < fav.size() - 1) {
                            Collections.swap(fav, i, i + 1);
                        } else if (quel == 2) {
                            fav.remove(a.pkg);
                        } else if (quel == 3) {
                            ouvrir(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:" + a.pkg)));
                            return;
                        }
                        enregistrerFavoris(fav);
                        construireDock();
                    }
                })
                .show();
    }

    private void lancer(Appli a) {
        ouvrir(a.lancement);
    }

    private void ouvrir(Intent i) {
        try {
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "Impossible d'ouvrir cette appli", Toast.LENGTH_SHORT).show();
        }
    }

    private void afficherToutesApplis() {
        if (calqueApplis.getVisibility() == View.VISIBLE) return;
        calqueApplis.setAlpha(0f);
        calqueApplis.setVisibility(View.VISIBLE);
        calqueApplis.animate().alpha(1f).setDuration(200).setListener(null).start();
        construireGrille();
        grilleDefilement.scrollTo(0, 0);
    }

    private void masquerToutesApplis() {
        if (calqueApplis.getVisibility() != View.VISIBLE) return;
        calqueApplis.animate().alpha(0f).setDuration(180).setListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                calqueApplis.setVisibility(View.GONE);
                grilleApplis.removeAllViews();
            }
        }).start();
        if (dock.getChildCount() > 0) dock.getChildAt(0).requestFocus();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent e) {
        if (e.getAction() == KeyEvent.ACTION_DOWN) {
            int k = e.getKeyCode();
            boolean grille = calqueApplis.getVisibility() == View.VISIBLE;
            if (k == KeyEvent.KEYCODE_BACK) {
                if (grille) masquerToutesApplis();
                return true; // l'accueil ne se ferme jamais
            }
            if (k == KeyEvent.KEYCODE_DPAD_DOWN && !grille) {
                afficherToutesApplis();
                return true;
            }
            if (k == KeyEvent.KEYCODE_DPAD_UP && grille) {
                View f = getCurrentFocus();
                if (f != null && Integer.valueOf(0).equals(f.getTag())) {
                    masquerToutesApplis();
                    return true;
                }
            }
            if (k == KeyEvent.KEYCODE_MENU) {
                View f = getCurrentFocus();
                if (f != null) {
                    f.performLongClick();
                    return true;
                }
            }
        }
        if (e.getKeyCode() == KeyEvent.KEYCODE_BACK) return true;
        return super.dispatchKeyEvent(e);
    }

    // ------------------------------------------------------------------ horloge

    private final Runnable tic = new Runnable() {
        @Override
        public void run() {
            majHorloge();
        }
    };

    private void majHorloge() {
        Date d = new Date();
        horloge.setText(new SimpleDateFormat("HH:mm", Locale.FRANCE).format(d));
        String j = new SimpleDateFormat("EEEE d MMMM", Locale.FRANCE).format(d);
        date.setText(j.substring(0, 1).toUpperCase(Locale.FRANCE) + j.substring(1));
        long attente = 60000 - (System.currentTimeMillis() % 60000) + 50;
        handler.removeCallbacks(tic);
        if (actif) handler.postDelayed(tic, attente);
    }

    // ------------------------------------------------------------------ fonds d'écran

    /** Fonds intégrés (assets/fonds) + photos perso déposées dans Android/data/com.lourdes.accueilzen/files/fonds. */
    private void listerFonds() {
        fonds.clear();
        try {
            String[] a = getAssets().list("fonds");
            if (a != null) for (String n : a) if (estImage(n)) fonds.add("asset:fonds/" + n);
        } catch (Exception ignore) {
        }
        File dossier = getExternalFilesDir("fonds");
        if (dossier != null) {
            File[] f = dossier.listFiles();
            if (f != null) for (File x : f) if (x.isFile() && estImage(x.getName())) fonds.add(x.getAbsolutePath());
        }
        Collections.shuffle(fonds, hasard);
    }

    private static boolean estImage(String n) {
        String l = n.toLowerCase(Locale.ROOT);
        return l.endsWith(".jpg") || l.endsWith(".jpeg") || l.endsWith(".png") || l.endsWith(".webp");
    }

    private final Runnable rotation = new Runnable() {
        @Override
        public void run() {
            fondSuivant();
        }
    };

    private void fondSuivant() {
        handler.removeCallbacks(rotation);
        if (fonds.isEmpty()) return;
        indexFond = (indexFond + 1) % fonds.size();
        final String source = fonds.get(indexFond);
        final int l = getResources().getDisplayMetrics().widthPixels;
        final int h = getResources().getDisplayMetrics().heightPixels;
        new Thread(new Runnable() {
            @Override
            public void run() {
                final Bitmap b = decoder(source, Math.max(l, 1280), Math.max(h, 720));
                handler.post(new Runnable() {
                    @Override
                    public void run() {
                        if (b != null) afficherFond(b);
                        long s = prefs.getLong(CLE_INTERVALLE, INTERVALLE_DEFAUT_S);
                        if (actif) handler.postDelayed(rotation, s * 1000);
                    }
                });
            }
        }).start();
    }

    private Bitmap decoder(String source, int lCible, int hCible) {
        try {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            ouvrirFlux(source, o);
            int echantillon = 1;
            while (o.outWidth / (echantillon * 2) >= lCible && o.outHeight / (echantillon * 2) >= hCible) {
                echantillon *= 2;
            }
            BitmapFactory.Options o2 = new BitmapFactory.Options();
            o2.inSampleSize = echantillon;
            return ouvrirFlux(source, o2);
        } catch (Throwable t) {
            return null;
        }
    }

    private Bitmap ouvrirFlux(String source, BitmapFactory.Options o) throws Exception {
        InputStream in = source.startsWith("asset:")
                ? getAssets().open(source.substring(6))
                : new java.io.FileInputStream(source);
        try {
            return BitmapFactory.decodeStream(in, null, o);
        } finally {
            in.close();
        }
    }

    /** Fondu enchaîné + lent zoom (effet Ken Burns). */
    private void afficherFond(Bitmap b) {
        final ImageView entrant = fondAVisible ? fondB : fondA;
        final ImageView sortant = fondAVisible ? fondA : fondB;
        fondAVisible = !fondAVisible;
        long duree = prefs.getLong(CLE_INTERVALLE, INTERVALLE_DEFAUT_S) * 1000 + 3000;

        if (zoom != null) zoom.cancel();
        entrant.animate().cancel();
        entrant.setImageBitmap(b);
        entrant.setScaleX(1f);
        entrant.setScaleY(1f);
        entrant.setAlpha(0f);
        // Les deux fonds occupent les positions 0 et 1 : l'entrant passe au-dessus du sortant,
        // le voile et l'interface restent au-dessus des deux.
        ViewGroup racine = (ViewGroup) entrant.getParent();
        racine.removeView(entrant);
        racine.addView(entrant, 1);

        entrant.animate().alpha(1f).setDuration(2200).setInterpolator(new LinearInterpolator())
                .setListener(new AnimatorListenerAdapter() {
                    @Override
                    public void onAnimationEnd(Animator animation) {
                        sortant.setAlpha(0f);
                        sortant.setImageDrawable(null);
                    }
                }).start();
        zoom = ObjectAnimator.ofPropertyValuesHolder(entrant,
                PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, 1.08f),
                PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, 1.08f));
        zoom.setDuration(duree);
        zoom.setInterpolator(new LinearInterpolator());
        zoom.start();
    }
}
