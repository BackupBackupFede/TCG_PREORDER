import requests
from bs4 import BeautifulSoup
import json
import os

# ======================
# CONFIG
# ======================

# Nom du fichier dans le Gist
GIST_FILENAME = "tcg_saved_products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

FS_ONE_PIECE = "https://www.fantasysphere.net/jeux-de-cartes-a-collectionner/one-piece-tcg/boite-de-boosters-one-piece/"
FS_POKEMON   = "https://www.fantasysphere.net/jeux-de-cartes-a-collectionner/pokemon/boite-de-booster-pokemon/"

AIALA_POKEMON   = "https://aialaocio.com/en/collections/cartas-pokemon"
AIALA_ONE_PIECE = "https://aialaocio.com/en/collections/one-piece"

TCGPOWER_POKEMON   = "https://www.tcgpower.nl/pokemon/sealed-items/boosterboxen"
TCGPOWER_ONE_PIECE = "https://www.tcgpower.nl/one-piece/boosterbox"

MYSTERYMEDIA_ONE_PIECE   = "https://mysterymedia.nl/product-categorie/trading-card-games/one-piece/"
MYSTERYMEDIA_ONE_PIECE_D = "https://mysterymedia.nl/product-categorie/trading-card-games/one-piece/page/2/"

LUDISPHERE_ONE_PIECE = "https://ludisphere.fr/collections/one-piece-card-game-precommande"

# Mots-clés qui indiquent un statut précommande dans les boutons/labels
PREORDER_KEYWORDS = ["précommande", "precommande", "pre-order", "preorder", "pre order", "réserver", "reserver"]

# ======================
# TELEGRAM
# ======================

def send_telegram(message):
    token   = os.getenv("TELEGRAM_TOKEN_2")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_2")

    if not token or not chat_id:
        print("⚠️ Telegram non configuré (TELEGRAM_TOKEN_2 / TELEGRAM_CHAT_ID_2)")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram error: {e}")

# ======================
# UTILS
# ======================

def safe_request(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"❌ Erreur réseau sur {url}: {e}")
        return None

def detect_preorder_from_text(text):
    """Retourne True si le texte contient un mot-clé de précommande."""
    t = text.lower()
    return any(kw in t for kw in PREORDER_KEYWORDS)

# ======================
# STORAGE — GitHub Gist
# ======================

def _gist_headers():
    token = os.getenv("GIST_TOKEN")
    if not token:
        raise RuntimeError("GIST_TOKEN non défini")
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

def load_saved():
    gist_id = os.getenv("GIST_ID")
    if not gist_id:
        print("[storage] GIST_ID non défini, démarrage à vide")
        return {}
    try:
        r = requests.get(f"https://api.github.com/gists/{gist_id}",
                         headers=_gist_headers(), timeout=10)
        r.raise_for_status()
        content = r.json()["files"][GIST_FILENAME]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[storage] Impossible de lire le Gist : {e}")
        return {}

def save(products, old):
    if old == products:
        print("[storage] Aucun changement")
        return False

    gist_id = os.getenv("GIST_ID")
    payload = {"files": {GIST_FILENAME: {"content": json.dumps(products, indent=2, ensure_ascii=False)}}}

    try:
        if gist_id:
            r = requests.patch(f"https://api.github.com/gists/{gist_id}",
                               headers=_gist_headers(), json=payload, timeout=10)
        else:
            # Premier run : crée le Gist et affiche son ID
            payload["description"] = "TCG Preorder Bot — état des produits"
            payload["public"] = False
            r = requests.post("https://api.github.com/gists",
                              headers=_gist_headers(), json=payload, timeout=10)
            r.raise_for_status()
            new_id = r.json()["id"]
            print(f"[storage] Gist créé ! Ajoute ce GIST_ID dans tes secrets : {new_id}")
            return True

        r.raise_for_status()
        print("[storage] Gist mis à jour")
        return True
    except Exception as e:
        print(f"[storage] Erreur sauvegarde Gist : {e}")
        return False

# ======================
# SCRAPERS
# ======================

def scrape_fantasysphere(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for article in soup.select("article.product-item-list"):
        link_tag = article.select_one(".product-item-name a")
        if not link_tag:
            continue

        name = link_tag.get("title") or link_tag.text.strip()
        link = "https://www.fantasysphere.net" + link_tag["href"]

        price_tag = article.select_one(".product-item-price.promo") \
                    or article.select_one(".product-item-price.base")
        price = price_tag.text.strip() if price_tag else "N/A"

        # Détection préco via bouton ou badge
        button = article.select_one("button, .add-to-cart, .product-item-actions")
        btn_text = button.text.strip() if button else ""
        if detect_preorder_from_text(btn_text) or detect_preorder_from_text(article.text):
            stock = "preorder"
        elif article.select_one(".outofstock"):
            stock = "rupture"
        else:
            stock = "disponible"

        key = f"Fantasysphere::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Fantasysphere", "category": category}

    return products


def scrape_aiala(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for card in soup.select(".product-item, .grid__item, li.grid__item"):
        a_tag = card.select_one("a.full-unstyled-link") or card.select_one("a[href*='/products/']")
        if not a_tag:
            continue

        name = a_tag.text.strip()
        href = a_tag.get("href", "")

        if not name or "/products/" not in href:
            continue
        if not any(k in name.lower() for k in ["booster", "display", "box", "etb"]):
            continue

        link = "https://aialaocio.com" + href

        # Prix
        price_tag = card.select_one(".price-item--regular") or card.select_one(".price")
        price = price_tag.text.strip() if price_tag else "N/A"

        # Détection préco
        badge = card.select_one(".badge, .product-badge, .label")
        badge_text = badge.text.strip() if badge else ""
        card_text = card.text
        if detect_preorder_from_text(badge_text) or detect_preorder_from_text(card_text):
            stock = "preorder"
        else:
            sold_out = card.select_one(".sold-out, .soldout")
            stock = "rupture" if sold_out else "disponible"

        key = f"Aiala::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Aiala Ocio", "category": category}

    return products


def scrape_tcgpower(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for item in soup.select("li.product-gallery__item"):
        container = item.select_one(".js-product-container")
        if not container:
            continue

        data = container.get("data-webshop-product")
        if not data:
            continue

        try:
            pj = json.loads(data)
        except Exception:
            continue

        name = pj.get("title")
        link = "https://www.tcgpower.nl" + pj.get("url", "")

        price_tag = item.select_one(".product__price__price")
        price = price_tag.text.strip() if price_tag else "N/A"

        # Détection préco via label ou données JSON
        availability = str(pj.get("availability", "")).lower()
        item_text = item.text
        if "preorder" in availability or detect_preorder_from_text(item_text):
            stock = "preorder"
        else:
            variants = pj.get("variants", [])
            qty = variants[0].get("stock", 0) if variants else 0
            stock = "disponible" if qty > 0 else "rupture"

        key = f"TCGPower::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "TCG Power", "category": category}

    return products


def scrape_mysterymedia(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for item in soup.select("li.product"):
        link_tag = item.select_one("a.woocommerce-LoopProduct-link")
        name_tag = item.select_one("h2.woocommerce-loop-product__title")
        if not link_tag or not name_tag:
            continue

        name = name_tag.text.strip()
        link = link_tag["href"]

        price_tag = item.select_one(".price")
        price = price_tag.text.strip() if price_tag else "N/A"

        item_classes = item.get("class", [])
        item_text = item.text
        if "preorder" in " ".join(item_classes).lower() or detect_preorder_from_text(item_text):
            stock = "preorder"
        elif "outofstock" in item_classes:
            stock = "rupture"
        else:
            stock = "disponible"

        key = f"MysteryMedia::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Mystery Media", "category": category}

    return products


def scrape_ludisphere(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for item in soup.select("li.grid__item"):
        link_tag = item.select_one("a.full-unstyled-link")
        if not link_tag:
            continue

        name = link_tag.text.strip()
        link = "https://ludisphere.fr" + link_tag.get("href", "").split("?")[0]

        price_tag = item.select_one(".price-item--regular") or item.select_one(".price-item--sale")
        price = price_tag.text.strip() if price_tag else "N/A"

        # Ludisphere a une collection dédiée préco — on détecte aussi via badge/bouton
        badge = item.select_one(".badge, .product-badge")
        badge_text = badge.text.strip() if badge else ""
        button = item.select_one("button")
        btn_text = button.text.strip() if button else ""

        if detect_preorder_from_text(badge_text) or detect_preorder_from_text(btn_text) or detect_preorder_from_text(item.text):
            stock = "preorder"
        elif button and button.has_attr("disabled"):
            stock = "rupture"
        else:
            stock = "disponible"

        key = f"Ludisphere::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Ludisphere", "category": category}

    return products

# ======================
# AGGREGATION
# ======================

def get_all_products():
    products = {}

    scrapers = [
        (scrape_fantasysphere, FS_ONE_PIECE,           "One Piece"),
        (scrape_fantasysphere, FS_POKEMON,             "Pokemon"),
        (scrape_aiala,         AIALA_ONE_PIECE,        "One Piece"),
        (scrape_aiala,         AIALA_POKEMON,          "Pokemon"),
        (scrape_tcgpower,      TCGPOWER_ONE_PIECE,     "One Piece"),
        (scrape_tcgpower,      TCGPOWER_POKEMON,       "Pokemon"),
        (scrape_mysterymedia,  MYSTERYMEDIA_ONE_PIECE,   "One Piece"),
        (scrape_mysterymedia,  MYSTERYMEDIA_ONE_PIECE_D, "One Piece"),
        (scrape_ludisphere,    LUDISPHERE_ONE_PIECE,   "One Piece"),
    ]

    for fn, url, cat in scrapers:
        try:
            data = fn(url, cat)
            products.update(data)
            print(f"✅ {fn.__name__} ({cat}) → {len(data)} produits")
        except Exception as e:
            print(f"❌ Erreur {fn.__name__}: {e}")

    return products

# ======================
# ALERTING
# ======================

STOCK_EMOJI = {
    "preorder":   "⏳",
    "disponible": "✅",
    "rupture":    "❌",
    "unknown":    "❓",
}

def build_alert(alert_type, product):
    emojis = {
        "NEW_PREORDER": "🆕⏳",
        "NEW":          "🆕",
        "PREORDER":     "⏳",
        "RESTOCK":      "🔥",
    }
    labels = {
        "NEW_PREORDER": "NOUVEAU en PRÉCO",
        "NEW":          "NOUVEAU",
        "PREORDER":     "PASSÉ en PRÉCO",
        "RESTOCK":      "RETOUR EN STOCK",
    }
    e = emojis.get(alert_type, "❗")
    l = labels.get(alert_type, alert_type)
    p = product
    stock_e = STOCK_EMOJI.get(p["stock"], "❓")
    return (
        f"{e} <b>{l}</b>\n"
        f"📦 {p['name']}\n"
        f"🏪 {p['boutique']} · {p['category']}\n"
        f"💰 {p['price']}   {stock_e} {p['stock']}\n"
        f"🔗 {p['link']}"
    )

# ======================
# MAIN
# ======================

def main():
    print("🔍 Scan des produits...")

    old     = load_saved()
    current = get_all_products()

    print(f"\n📊 {len(current)} produits détectés au total\n")

    alerts = []

    for k, v in current.items():
        if k not in old:
            # Produit tout nouveau
            if v["stock"] == "preorder":
                alerts.append(("NEW_PREORDER", v))
            else:
                alerts.append(("NEW", v))
        else:
            prev_stock = old[k]["stock"]
            curr_stock = v["stock"]
            if prev_stock != curr_stock:
                if curr_stock == "preorder":
                    alerts.append(("PREORDER", v))
                elif curr_stock == "disponible":
                    alerts.append(("RESTOCK", v))

    if alerts:
        msg = "🚨 <b>ALERTES TCG</b> 🚨\n\n"
        msg += "\n\n─────────────────\n\n".join(build_alert(t, p) for t, p in alerts)
        print(msg)
        send_telegram(msg)
        print(f"\n[alert] {len(alerts)} alerte(s) envoyee(s) sur Telegram")
    else:
        print("[alert] Rien de nouveau")

    save(current, old)


if __name__ == "__main__":
    main()
