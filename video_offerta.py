"""
OFFERTE IMPAZIENTI - video animato per ogni offerta del canale Telegram.
Stile: logo bassotto, colori nero/ambra/giallo, barra di avanzamento ed etichette gialle come nei video AlexisView.

Requisiti: Python con Pillow + ffmpeg (GitHub Actions: sudo apt-get install -y ffmpeg, pip install pillow).
Uso:  python video_offerta.py
Nel bot: crea_video(prodotto, "offerta.mp4") e poi invia il file con sendVideo.
"""
import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# =====================================================================
#  STILE "OFFERTE IMPAZIENTI"  -> cambia solo questa parte
# =====================================================================
QUI = os.path.dirname(os.path.abspath(__file__))
BRAND = {
    "nome_1": "OFFERTE",                        # prima riga del nome (gialla)
    "nome_2": "IMPAZIENTI",                     # seconda riga (bianca)
    "logo": os.path.join(QUI, "logo.jpg"),      # immagine profilo del canale
    "ritaglio_avatar": (0.42, 0.16, 0.76, 0.50),  # parte del logo nel cerchio (testa del bassotto), in proporzione
    "giallo": (250, 208, 60),                   # lo stesso giallo dei video AlexisView
    "arancio": (242, 140, 30),
    "testo_scuro": (25, 18, 10),
    "etichetta": "OFFERTA LAMPO",
    "bottone": "ACQUISTA ORA",
    "sotto_bottone": "Link qui sotto  ↓",
}
FONT_DIR = os.path.join(QUI, "fonts")
FONT = {
    "brand": os.path.join(FONT_DIR, "Inter-BlackItalic.otf"),
    "titolo": os.path.join(FONT_DIR, "Inter-ExtraBold.otf"),
    "etichetta": os.path.join(FONT_DIR, "Inter-Bold.otf"),
    "prezzo_vecchio": os.path.join(FONT_DIR, "Anton-Regular.ttf"),
    "testo": os.path.join(FONT_DIR, "Inter-SemiBold.otf"),
}
W, H, FPS, DURATA = 1080, 1920, 30, 7.0
# =====================================================================


SISTEMA = "/usr/share/fonts/opentype/inter/"   # font Inter installati con: apt-get install fonts-inter
RISERVA = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:  # ffmpeg già pronto installato con pip (imageio-ffmpeg), altrimenti quello di sistema
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = "ffmpeg"


def f(nome, size):
    path = FONT[nome]
    if not os.path.exists(path):  # se manca nella cartella fonts, usa quello di sistema
        alt = os.path.join(SISTEMA, os.path.basename(path))
        path = alt if os.path.exists(alt) else os.path.join(SISTEMA, "Inter-Black.otf")
        if not os.path.exists(path):
            path = os.path.join(FONT_DIR, "Inter-Black.otf")
        if not os.path.exists(path):
            path = RISERVA
    return ImageFont.truetype(path, int(size))


def prog(t, inizio, durata):
    return max(0.0, min(1.0, (t - inizio) / durata))


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_back(p):
    c = 1.7
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def incolla(base, elem, cx, cy, scala=1.0, alpha=1.0):
    if scala <= 0.01 or alpha <= 0.01:
        return
    e = elem if scala == 1 else elem.resize((max(1, int(elem.width * scala)), max(1, int(elem.height * scala))), Image.LANCZOS)
    if alpha < 1:
        e = e.copy()
        e.putalpha(e.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(e, (int(cx - e.width / 2), int(cy - e.height / 2)))


def testo_brillante(testo, font, colore, bordo=(25, 18, 10), spessore=6, bagliore=None):
    """Testo con contorno scuro e alone luminoso, come la scritta del logo."""
    bb = font.getbbox(testo, stroke_width=spessore)
    pad = 40
    img = Image.new("RGBA", (bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2), (0, 0, 0, 0))
    pos = (pad - bb[0], pad - bb[1])
    if bagliore:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text(pos, testo, font=font, fill=bagliore + (200,), stroke_width=spessore + 4, stroke_fill=bagliore + (200,))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(16)))
    ImageDraw.Draw(img).text(pos, testo, font=font, fill=colore, stroke_width=spessore, stroke_fill=bordo)
    return img


def chip(testo, font, sfondo, colore, pad_x=26, pad_y=14):
    """Etichetta gialla arrotondata (come '1 · ALBANIA' nei video)."""
    bb = font.getbbox(testo)
    w, h = bb[2] + pad_x * 2, bb[3] - bb[1] + pad_y * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 12, fill=sfondo)
    d.text((pad_x, pad_y - bb[1]), testo, font=font, fill=colore)
    return img


def titolo_img(testo, font, larghezza_max):
    parole, righe, riga = testo.split(), [], ""
    for p in parole:
        prova = (riga + " " + p).strip()
        if font.getlength(prova) <= larghezza_max:
            riga = prova
        else:
            righe.append(riga)
            riga = p
    righe.append(riga)
    righe = righe[:3]
    h_riga = int(font.size * 1.22)
    img = Image.new("RGBA", (larghezza_max + 40, h_riga * len(righe) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, r in enumerate(righe):
        d.text((img.width / 2, 15 + i * h_riga + h_riga / 2), r, font=font, fill="white", anchor="mm",
               stroke_width=4, stroke_fill=(20, 12, 5))
    return img


# ---------- elementi del marchio ----------
def sfondo(logo):
    """Il logo sfocato e scurito: stessi toni ambra/nero dell'immagine profilo."""
    s = logo.resize((H, H), Image.LANCZOS).crop(((H - W) // 2, 0, (H - W) // 2 + W, H))
    s = s.filter(ImageFilter.GaussianBlur(45))
    s = ImageEnhance.Brightness(s).enhance(0.45).convert("RGBA")
    # vignettatura: più scuro in alto e in basso, così i testi si leggono bene
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(v)
    for y in range(H):
        k = abs(y - H * 0.45) / (H * 0.55)
        d.line([(0, y), (W, y)], fill=(8, 4, 0, int(200 * min(1, k) ** 1.6)))
    s.alpha_composite(v)
    return s


def scie_luminose():
    """Strisce di luce dorata (come quelle dietro il bassotto), larghe il doppio per farle scorrere."""
    L = Image.new("RGBA", (W * 2, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    for i, (amp, fase, spess, a) in enumerate([(60, 0.0, 5, 230), (45, 1.3, 3, 190), (75, 2.1, 4, 160),
                                                (35, 3.0, 2, 220), (55, 4.2, 3, 150)]):
        y0 = 120 + i * 38
        punti = [(x, y0 + amp * math.sin(x / W * 2 * math.pi * 2 + fase)) for x in range(0, W * 2 + 20, 20)]
        d.line(punti, fill=(255, 190, 80, a), width=spess)
    glow = L.filter(ImageFilter.GaussianBlur(10))
    out = Image.new("RGBA", L.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(L)
    return out


def avatar(logo, lato):
    x0, y0, x1, y1 = BRAND["ritaglio_avatar"]
    a = logo.crop((int(x0 * logo.width), int(y0 * logo.height), int(x1 * logo.width), int(y1 * logo.height))).resize((lato, lato), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (lato, lato), 0)
    ImageDraw.Draw(m).ellipse([0, 0, lato - 1, lato - 1], fill=255)
    a.putalpha(m)
    out = Image.new("RGBA", (lato + 12, lato + 12), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse([0, 0, lato + 11, lato + 11], fill=BRAND["giallo"])
    out.alpha_composite(a, (6, 6))
    return out


def intestazione(logo):
    """Avatar + nome canale in alto a sinistra (al posto di 'AlexisView')."""
    av = avatar(logo, 120)
    t1 = testo_brillante(BRAND["nome_1"], f("brand", 50), BRAND["giallo"], spessore=4)
    t2 = testo_brillante(BRAND["nome_2"], f("brand", 50), (255, 255, 255), spessore=4)
    img = Image.new("RGBA", (av.width + 20 + max(t1.width, t2.width), max(av.height, 150)), (0, 0, 0, 0))
    img.alpha_composite(av, (0, (img.height - av.height) // 2))
    img.alpha_composite(t1, (av.width - 20, img.height // 2 - t1.height + 22))
    img.alpha_composite(t2, (av.width - 20, img.height // 2 - 22))
    return img


def foto_prodotto(foto_path, lato):
    tela = Image.new("RGBA", (lato, lato), (255, 255, 255, 255))
    if foto_path and os.path.exists(foto_path):
        foto = Image.open(foto_path).convert("RGBA")
        foto.thumbnail((int(lato * 0.88), int(lato * 0.88)))
        tela.alpha_composite(foto, ((lato - foto.width) // 2, (lato - foto.height) // 2))
    else:  # segnaposto
        d = ImageDraw.Draw(tela)
        k = lato / 440
        cx, cy = lato / 2, lato / 2
        R = lambda x0, y0, x1, y1: [cx + x0 * k, cy + y0 * k, cx + x1 * k, cy + y1 * k]
        d.rounded_rectangle(R(-150, -90, 150, 110), 40 * k, fill=(230, 60, 50))
        d.rounded_rectangle(R(-110, -60, 30, 40), 16 * k, fill=(30, 30, 35))
        d.text((cx - 40 * k, cy - 10 * k), "150", font=f("titolo", 52 * k), fill=(120, 255, 160), anchor="mm")
        d.ellipse(R(55, -45, 125, 25), fill=(245, 245, 245))
        d.rounded_rectangle(R(-120, -130, 120, -95), 14 * k, fill=(60, 60, 65))
        d.arc(R(60, 60, 190, 170), 200, 340, fill=(30, 30, 35), width=int(14 * k))
        d.text((cx, lato - 40 * k), "FOTO PRODOTTO", font=f("etichetta", 26 * k), fill=(160, 160, 170), anchor="mm")
    m = Image.new("L", (lato, lato), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, lato - 1, lato - 1], 36, fill=255)
    tela.putalpha(m)
    # cornice + alone dorato dietro la card
    out = Image.new("RGBA", (lato + 160, lato + 160), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle([60, 60, lato + 100, lato + 100], 50, fill=BRAND["arancio"] + (170,))
    out = out.filter(ImageFilter.GaussianBlur(35))
    ImageDraw.Draw(out).rounded_rectangle([74, 74, lato + 86, lato + 86], 42, fill=BRAND["giallo"])
    out.alpha_composite(tela, (80, 80))
    return out


def formatta(prezzo):
    return f"{prezzo:.2f} €".replace(".", ",")


# ---------- video ----------
def crea_video(p, uscita="offerta.mp4"):
    if os.path.exists(BRAND["logo"]):
        logo = Image.open(BRAND["logo"]).convert("RGB")
    else:  # niente logo: sfondo ambra/nero di riserva
        logo = Image.new("RGB", (512, 512), (40, 20, 5))
        ImageDraw.Draw(logo).ellipse([150, 100, 500, 450], fill=(200, 110, 20))
    bg = sfondo(logo)
    scie = scie_luminose()
    testa = intestazione(logo)
    card = foto_prodotto(p.get("foto"), 640)
    sconto = round((1 - p["prezzo_scontato"] / p["prezzo_originale"]) * 100)

    etich = chip(BRAND["etichetta"], f("etichetta", 40), BRAND["giallo"], BRAND["testo_scuro"])
    t_titolo = titolo_img(p["titolo"], f("titolo", 60), W - 160)
    t_vecchio = testo_brillante(formatta(p["prezzo_originale"]), f("prezzo_vecchio", 70), (215, 205, 190), spessore=3)
    t_nuovo = testo_brillante(formatta(p["prezzo_scontato"]), f("brand", 190), BRAND["giallo"], spessore=8,
                              bagliore=BRAND["arancio"])
    t_sotto = testo_brillante(BRAND["sotto_bottone"], f("testo", 38), (255, 255, 255), spessore=2)

    bd = 240
    badge = Image.new("RGBA", (bd, bd), (0, 0, 0, 0))
    db = ImageDraw.Draw(badge)
    db.ellipse([0, 0, bd - 1, bd - 1], fill=BRAND["testo_scuro"])
    db.ellipse([8, 8, bd - 9, bd - 9], fill=BRAND["arancio"])
    db.text((bd / 2, bd / 2), f"-{sconto}%", font=f("brand", 66), fill="white", anchor="mm",
            stroke_width=4, stroke_fill=BRAND["testo_scuro"])

    bw, bh = 700, 136
    bott = Image.new("RGBA", (bw + 60, bh + 60), (0, 0, 0, 0))
    ImageDraw.Draw(bott).rounded_rectangle([30, 36, bw + 30, bh + 36], bh // 2, fill=BRAND["arancio"] + (200,))
    bott = bott.filter(ImageFilter.GaussianBlur(14))
    dbt = ImageDraw.Draw(bott)
    dbt.rounded_rectangle([30, 30, bw + 30, bh + 30], bh // 2, fill=BRAND["giallo"], outline=BRAND["testo_scuro"], width=5)
    dbt.text((30 + bw / 2, 30 + bh / 2), BRAND["bottone"] + "  ›", font=f("brand", 58), fill=BRAND["testo_scuro"], anchor="mm")

    ff = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", uscita], stdin=subprocess.PIPE)

    for i in range(int(DURATA * FPS)):
        t = i / FPS
        fr = bg.copy()
        d = ImageDraw.Draw(fr)

        # scie luminose che scorrono dietro la card (il bassotto che "corre")
        off = int((t * 900) % W)
        a_scie = ease_out(prog(t, 0.2, 0.8))
        if a_scie > 0:
            pezzo = scie.crop((W - off, 0, 2 * W - off, scie.height))
            incolla(fr, pezzo, W / 2, 900, 1.0, a_scie * 0.9)

        # barra di avanzamento in alto (come nei video AlexisView)
        d.rounded_rectangle([90, 100, W - 90, 112], 6, fill=(80, 66, 50))
        d.rounded_rectangle([90, 100, 90 + (W - 180) * (t / DURATA), 112], 6, fill=BRAND["giallo"])

        # intestazione + etichetta
        incolla(fr, testa, 80 + testa.width / 2 - 60 * (1 - ease_out(prog(t, 0, 0.5))), 210, 1.0, ease_out(prog(t, 0, 0.5)))
        pe = ease_back(prog(t, 0.3, 0.45)) if t > 0.3 else 0
        incolla(fr, etich, 90 + etich.width / 2, 340, pe)

        # card prodotto
        pf = prog(t, 0.5, 0.7)
        g = math.sin(t * 2.2) * 10 if t > 1.2 else 0
        incolla(fr, card, W / 2, 800 + g, ease_back(pf) if pf > 0 else 0)

        # badge sconto
        pg = prog(t, 2.6, 0.6)
        if pg > 0:
            rb = badge.rotate((1 - ease_out(pg)) * 200 - 12, resample=Image.BICUBIC, expand=True)
            incolla(fr, rb, 860, 500 + g, ease_back(pg))

        # titolo
        pt = ease_out(prog(t, 1.1, 0.6))
        incolla(fr, t_titolo, W / 2, 1260 + (1 - pt) * 40, 1.0, pt)

        # prezzo vecchio barrato
        pv = ease_out(prog(t, 1.7, 0.4))
        if pv > 0:
            incolla(fr, t_vecchio, W / 2, 1420, 1.0, pv)
            pl = ease_out(prog(t, 2.0, 0.35))
            if pl > 0:
                x1 = W / 2 - (t_vecchio.width - 80) / 2 - 8
                d.line([(x1, 1425), (x1 + (t_vecchio.width - 64) * pl, 1420)], fill=(230, 50, 40), width=10)

        # prezzo nuovo
        pn = prog(t, 2.3, 0.5)
        if pn > 0:
            incolla(fr, t_nuovo, W / 2, 1570, ease_back(pn))

        # bottone che pulsa + scritta sotto
        pc = prog(t, 3.5, 0.5)
        if pc > 0:
            pulsa = 1 + 0.045 * math.sin((t - 4.0) * 7) if t > 4.0 else 1
            incolla(fr, bott, W / 2, 1745, ease_back(pc) * pulsa)
            incolla(fr, t_sotto, W / 2, 1855, 1.0, ease_out(prog(t, 3.9, 0.4)))

        ff.stdin.write(fr.convert("RGB").tobytes())

    ff.stdin.close()
    ff.wait()
    return uscita


if __name__ == "__main__":
    prodotto_prova = {
        "titolo": "Compressore portatile per auto 150 PSI",
        "prezzo_originale": 49.99,
        "prezzo_scontato": 29.99,
        "foto": None,  # es. "foto.jpg" (la foto del prodotto Amazon)
    }
    print("Creato:", crea_video(prodotto_prova, "offerte_impazienti_prova.mp4"))
