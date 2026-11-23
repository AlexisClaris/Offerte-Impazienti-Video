"""
Ogni ora: prende un'offerta da offerte.json (in ordine di sconto, una diversa ogni ora),
crea il video "Offerte Impazienti" e lo pubblica sul canale Telegram.

Servono due Secrets su GitHub:  BOT_TOKEN  e  CHAT_ID
Prova senza inviare nulla:  PROVA=1 python invia_video.py
"""
import json
import os
import time
import urllib.request

import requests

from video_offerta import crea_video

QUI = os.path.dirname(os.path.abspath(__file__))


def formatta(prezzo):
    return f"{prezzo:.2f} €".replace(".", ",")


def scegli_offerta(offerte):
    """Ordina per sconto (dal più alto) e ne sceglie una diversa ogni ora."""
    offerte = sorted(offerte, key=lambda o: 1 - o["prezzo_scontato"] / o["prezzo_originale"], reverse=True)
    ora = int(time.time() // 3600)
    return offerte[ora % len(offerte)]


def scarica_foto(url, percorso):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r, open(percorso, "wb") as f:
            f.write(r.read())
        return percorso
    except Exception as e:
        print("Foto non scaricata, uso il segnaposto:", e)
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
    sconto = round((1 - o["prezzo_scontato"] / o["prezzo_originale"]) * 100)
    return (
        f"🔥 <b>{o['titolo']}</b>\n\n"
        f"❌ Prima: <s>{formatta(o['prezzo_originale'])}</s>\n"
        f"✅ Ora: <b>{formatta(o['prezzo_scontato'])}</b>  (-{sconto}%)\n\n"
        f"⚡ Offerte Impazienti"
    )


def main():
    with open(os.path.join(QUI, "offerte.json"), encoding="utf-8") as f:
        offerte = json.load(f)
    o = scegli_offerta(offerte)
    print("Offerta scelta:", o["titolo"])

    token, chat_id = os.environ.get("BOT_TOKEN"), os.environ.get("CHAT_ID")
    scarica_logo(token, chat_id, os.path.join(QUI, "logo.jpg"))
    foto = scarica_foto(o.get("foto_url"), os.path.join(QUI, "foto_prodotto.jpg"))
    video = crea_video({**o, "foto": foto}, os.path.join(QUI, "offerta.mp4"))

    if os.environ.get("PROVA"):
        print("Modalità prova: video creato, non inviato ->", video)
        return

    with open(video, "rb") as v:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={
                "chat_id": chat_id,
                "caption": didascalia(o),
                "parse_mode": "HTML",
                "supports_streaming": "true",
                "width": 1080,
                "height": 1920,
                "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 Acquista Ora", "url": o["link"]}]]}),
            },
            files={"video": ("offerta.mp4", v, "video/mp4")},
            timeout=120,
        )
    print("Risposta Telegram:", r.status_code, r.text[:300])
    r.raise_for_status()


if __name__ == "__main__":
    main()
