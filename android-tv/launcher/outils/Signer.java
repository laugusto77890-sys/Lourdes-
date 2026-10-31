import com.android.apksig.ApkSigner;

import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.util.Collections;

/** Signe un APK (schéma v2, Android 7+) avec la bibliothèque officielle apksig. */
public class Signer {
    public static void main(String[] a) throws Exception {
        String magasin = a[0], mdp = a[1], alias = a[2];
        File entree = new File(a[3]), sortie = new File(a[4]);
        KeyStore ks = KeyStore.getInstance("PKCS12");
        try (FileInputStream in = new FileInputStream(magasin)) {
            ks.load(in, mdp.toCharArray());
        }
        PrivateKey cle = (PrivateKey) ks.getKey(alias, mdp.toCharArray());
        X509Certificate cert = (X509Certificate) ks.getCertificate(alias);
        ApkSigner.SignerConfig conf = new ApkSigner.SignerConfig.Builder(
                "ZEN", cle, Collections.singletonList(cert)).build();
        sortie.getParentFile().mkdirs();
        new ApkSigner.Builder(Collections.singletonList(conf))
                .setInputApk(entree)
                .setOutputApk(sortie)
                .setMinSdkVersion(24)
                .setV1SigningEnabled(false) // v1 inutile à partir d'Android 7 (et apksig 2.3.0 ne la gère plus sous JDK 17+)
                .setV2SigningEnabled(true)
                .build()
                .sign();
        System.out.println("Signé : " + sortie);
    }
}
