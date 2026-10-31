package com.lourdes.accueilzen;

import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;

/** Pictogrammes blancs dessinés en code (pas de ressource à embarquer). */
public class Pictogramme extends Drawable {

    static final int GRILLE = 0;
    static final int ENGRENAGE = 1;

    private final int type;
    private final Paint pinceau = new Paint(Paint.ANTI_ALIAS_FLAG);

    Pictogramme(int type) {
        this.type = type;
        pinceau.setColor(0xFFFFFFFF);
        pinceau.setStyle(Paint.Style.FILL);
    }

    @Override
    public void draw(Canvas c) {
        Rect b = getBounds();
        float t = Math.min(b.width(), b.height());
        float x0 = b.centerX() - t / 2f, y0 = b.centerY() - t / 2f;
        if (type == GRILLE) {
            float pas = t / 3f, cote = pas * 0.62f, r = cote * 0.28f;
            for (int i = 0; i < 3; i++) {
                for (int j = 0; j < 3; j++) {
                    float x = x0 + i * pas + (pas - cote) / 2f;
                    float y = y0 + j * pas + (pas - cote) / 2f;
                    c.drawRoundRect(new RectF(x, y, x + cote, y + cote), r, r, pinceau);
                }
            }
        } else {
            float cx = b.centerX(), cy = b.centerY();
            float rExt = t * 0.48f, rInt = t * 0.36f, rTrou = t * 0.15f;
            int dents = 8;
            Path p = new Path();
            for (int i = 0; i < dents * 2; i++) {
                double a0 = Math.PI * 2 * i / (dents * 2);
                double a1 = Math.PI * 2 * (i + 1) / (dents * 2);
                float r = (i % 2 == 0) ? rExt : rInt;
                float x1 = cx + (float) Math.cos(a0) * r, y1 = cy + (float) Math.sin(a0) * r;
                float x2 = cx + (float) Math.cos(a1) * r, y2 = cy + (float) Math.sin(a1) * r;
                if (i == 0) p.moveTo(x1, y1); else p.lineTo(x1, y1);
                p.lineTo(x2, y2);
            }
            p.close();
            p.addCircle(cx, cy, rTrou, Path.Direction.CCW);
            p.setFillType(Path.FillType.EVEN_ODD);
            c.drawPath(p, pinceau);
        }
    }

    @Override
    public void setAlpha(int a) {
        pinceau.setAlpha(a);
    }

    @Override
    public void setColorFilter(ColorFilter f) {
        pinceau.setColorFilter(f);
    }

    @Override
    public int getOpacity() {
        return PixelFormat.TRANSLUCENT;
    }

    @Override
    public int getIntrinsicWidth() {
        return 96;
    }

    @Override
    public int getIntrinsicHeight() {
        return 96;
    }
}
