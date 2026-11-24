"""
Crea il video "Offerte Impazienti" per un'offerta e lo pubblica sul canale Telegram.

Due modi di partire:
- dal bot su Cloudflare (offerta incollata in chat con la riga "video"): i dati arrivano in OFFERTA
- a mano da GitHub (Run workflow): usa la prima offerta di offerte.json

Se il video non riesce, pubblica il messaggio normale (come fa Cloudflare), così l'offerta non va persa.
Servono due Secrets su GitHub:  BOT_TOKEN  e  CHAT_ID
Prova senza inviare nulla:  PROVA=1 python invia_video.py
"""
import html
import json
import os
import re
import urllib.request

import requests

from video_offerta import crea_video

QUI = os.path.dirname(os.path.abspath(__file__))
TAG_AMAZON = "alexisclari00-21"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")


def euro(v):
    intero, dec = f"{v:.2f}".split(".")
    return f"{int(intero):,}".replace(",", ".") + "," + dec


def link_affiliato(url):
    if "amazon." in url and "tag=" not in url:
        url += ("&" if "?" in url else "?") + "tag=" + TAG_AMAZON
    return url


def asin_da_link(url):
    m = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", url or "")
    return m.group(1) if m else None


def pulisci_token(t):
    t = (t or "").strip().strip('"').strip("'").strip()
    if t.lower().startswith("bot") and t[3:4].isdigit():
        t = t[3:]
    ok = bool(re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", t))
    print(f"Controllo token: lunghezza {len(t)}, formato corretto: {'sì' if ok else 'NO'}")
    return t


def scarica(url, percorso, minimo=2000):
    """Scarica un'immagine; la scarta se è troppo piccola (Amazon a volte dà un pixel vuoto)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            dati = r.read()
        if len(dati) < minimo:
            return None
        with open(percorso, "wb") as f:
            f.write(dati)
        return percorso
    except Exception as e:
        print("Immagine non scaricata:", url[:80], "-", e)
        return None


def foto_prodotto(o, percorso):
    """Cerca la foto: 1) foto_url  2) pagina Amazon  3) link immagine dal codice ASIN."""
    if o.get("foto_url") and scarica(o["foto_url"], percorso):
        return percorso
    asin = o.get("asin") or asin_da_link(o.get("link"))
    if not asin:
        return None
    try:
        pagina = requests.get(f"https://www.amazon.it/dp/{asin}", timeout=20,
                              headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"}).text
        for schema in (r'"hiRes":"(https://[^"]+)"', r'data-old-hires="(https://[^"]+)"',
                       r'"large":"(https://[^"]+)"', r'<meta property="og:image" content="(https://[^"]+)"'):
            m = re.search(schema, pagina)
            if m and scarica(m.group(1), percorso):
                print("Foto presa dalla pagina Amazon")
                return percorso
    except Exception as e:
        print("Pagina Amazon non letta:", e)
    for url in (f"https://m.media-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg",
                f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg"):
        if scarica(url, percorso):
            print("Foto presa dal codice ASIN")
            return percorso
    return None


def scarica_logo(token, chat_id, percorso):
    """Usa come logo la foto profilo del canale Telegram (se logo.jpg non c'è già)."""
    if os.path.exists(percorso) or not token:
        return
    try:
        api = f"https://api.telegram.org/bot{token}"
        chat = requests.get(f"{api}/getChat", params={"chat_id": chat_id}, timeout=20).json()["result"]
        file_id = chat["photo"]["big_file_id"]
        path = requests.get(f"{api}/getFile", params={"file_id": file_id}, timeout=20).json()["result"]["file_path"]
        with open(percorso, "wb") as f:
            f.write(requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=30).content)
        print("Logo preso dalla foto profilo del canale")
    except Exception as e:
        print("Logo non trovato, uso lo sfondo di riserva:", e)


def didascalia(o):
    """Se arriva da Cloudflare usa lo stesso testo dei post normali, altrimenti lo costruisce."""
    if o.get("testo"):
        return o["testo"]
    righe = [f"🔥 <b>{html.escape(o.get('titolo_completo') or o['titolo'], quote=False)}</b>", ""]
    if o.get("prezzo_originale"):
        risparmio = o["prezzo_originale"] - o["prezzo_scontato"]
        sconto = round(risparmio / o["prezzo_originale"] * 100)
        righe.append(f"💰 Passa da <s>{euro(o['prezzo_originale'])}€</s> a <b>{euro(o['prezzo_scontato'])}€</b>")
        righe.append(f"ℹ️ <i>Risparmi: {euro(risparmio)}€ (-{sconto}%)</i>")
    else:
        righe.append(f"💰 <b>{euro(o['prezzo_scontato'])}€</b>")
    righe.append("")
    righe.append(f"{o['hashtag']} · #adv · link di affiliazione" if o.get("hashtag") else "#adv · link di affiliazione")
    return "\n".join(righe)


def leggi_offerta():
    """Offerta da Cloudflare (variabile OFFERTA) oppure la prima di offerte.json."""
    grezza = os.environ.get("OFFERTA", "").strip()
    if grezza and grezza not in ("null", "{}"):
        p = json.loads(grezza)
        return {
            "titolo": p["titolo"],
            "prezzo_originale": p.get("pieno"),
            "prezzo_scontato": p["scontato"],
            "link": p["link"],
            "asin": p.get("asin"),
            "testo": p.get("testo"),
            "foto_url": p.get("foto_url"),
        }
    with open(os.path.join(QUI, "offerte.json"), encoding="utf-8") as f:
        return json.load(f)[0]


def main():
    o = leggi_offerta()
    o["link"] = link_affiliato(o["link"])
    print("Offerta:", o["titolo"])

    token = pulisci_token(os.environ.get("BOT_TOKEN"))
    chat_id = (os.environ.get("CHAT_ID") or "").strip()
    api = f"https://api.telegram.org/bot{token}"
    pulsante = json.dumps({"inline_keyboard": [[{"text": "🛒 Vai all'offerta", "url": o["link"]}]]})
    testo = didascalia(o)

    try:
        logo = os.path.join(QUI, "logo.jpg")
        scarica_logo(token, chat_id, logo)
        foto = foto_prodotto(o, os.path.join(QUI, "foto_prodotto.jpg"))
        if not foto and os.path.exists(logo):
            print("Nessuna foto del prodotto: uso il logo")
            foto = logo
        video = crea_video({**o, "foto": foto}, os.path.join(QUI, "offerta.mp4"))

        if os.environ.get("PROVA"):
            print("Modalità prova: video creato, non inviato ->", video)
            return

        with open(video, "rb") as v:
            r = requests.post(f"{api}/sendVideo", timeout=120, data={
                "chat_id": chat_id, "caption": testo, "parse_mode": "HTML",
                "supports_streaming": "true", "width": 1080, "height": 1920, "reply_markup": pulsante,
            }, files={"video": ("offerta.mp4", v, "video/mp4")})
        print("Risposta Telegram:", r.status_code, r.text[:200])
        r.raise_for_status()
    except Exception as e:
        if os.environ.get("PROVA"):
            raise
        # riserva: pubblica il messaggio normale, come Cloudflare
        print("Video non riuscito, pubblico il messaggio normale:", e)
        r = requests.post(f"{api}/sendMessage", timeout=30, json={
            "chat_id": chat_id, "text": testo, "parse_mode": "HTML",
            "link_preview_options": {"url": o["link"], "prefer_large_media": True, "show_above_text": True},
            "reply_markup": json.loads(pulsante),
        })
        print("Risposta Telegram (messaggio):", r.status_code, r.text[:200])
        r.raise_for_status()


if __name__ == "__main__":
    main()
