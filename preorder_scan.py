import requests
from bs4 import BeautifulSoup
import json
import os
import re

# ======================
# CONFIG
# ======================

DATA_FILE = "saved_products.json"

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

PHILIBERT_ONE_PIECE = "https://www.philibertnet.com/fr/15860-one-piece-le-jeu-de-cartes"
PHILIBERT_POKEMON   = "https://www.philibertnet.com/fr/212-pokemon"
PHILIBERT_PRECO_TCG = "https://www.philibertnet.com/fr/578-precommandes/s-3/categorie-jeux_de_cartes_a_collectionner_et_jeux_de_cartes_evolutifs"

ULTRAJEUX_ONE_PIECE_EN      = "https://www.ultrajeux.com/cat-0-1031-379-one-piece-card-game-booster-anglais.html"
ULTRAJEUX_POKEMON_DISPLAYS  = "https://www.ultrajeux.com/cat-0-4-469-pokemon-boite-de-boosters-francais.html"

# Produits scellés pertinents pour le flip (filtre Philibert, catalogue trop large)
SEALED_KEYWORDS = ["booster", "display", "boîte", "boite", "coffret",
                   "bundle", "collection", "etb", "box", "tripack"]

# Mots-clés qui indiquent un statut précommande dans les boutons/labels
PREORDER_KEYWORDS = ["précommande", "precommande", "pre-order", "preorder", "pre order", "réserver", "reserver"]

# Langues autorisées — on ignore tout ce qui n'est pas EN
ALLOWED_LANGS = ["(en)", "- en", "_en"]

def is_english(name):
    n = name.lower()
    # Exclure explicitement FR et JP
    if "(fr)" in n or "- fr" in n or "(jp)" in n or "- jp" in n:
        return False
    # Si la langue est explicitement EN, on garde
    if any(tag in n for tag in ALLOWED_LANGS):
        return True
    # Pas de tag langue → on garde (boutiques NL/ES qui ne taguent pas)
    return True

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

def parse_price(price_str):
    """'99,00 €' / '€ 1.299,95' / '89.95' → float, sinon None."""
    if not price_str:
        return None
    s = re.sub(r"[^\d,.]", "", str(price_str))
    if not s:
        return None
    if "," in s and "." in s:      # format 1.299,95
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None

# ======================
# STORAGE
# ======================

def load_saved():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # État corrompu (ex: marqueurs de conflit git) → on repart de zéro
        # plutôt que de tuer le run. Coût: une rafale d'alertes "nouveau".
        print(f"⚠️ {DATA_FILE} illisible ({e}) — état réinitialisé")
        return {}

def save(products, old):
    if old == products:
        print("[storage] Aucun changement")
        return False
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print("[storage] Sauvegarde OK")
    return True

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

        if not is_english(name):
            continue
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

        if not is_english(name):
            continue
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

        if not is_english(name):
            continue
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

        if not is_english(name):
            continue
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

        if not is_english(name):
            continue
        key = f"Ludisphere::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Ludisphere", "category": category}

    return products

def scrape_philibert(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}
    is_preco_page = "precommandes" in url

    for card in soup.select(".product-card"):
        title_tag = card.select_one("a.product-card__title")
        if not title_tag:
            continue
        name = title_tag.get_text(strip=True)
        link = "https://www.philibertnet.com" + title_tag.get("href", "")

        # La page préco TCG mélange tous les jeux → rattachement via le nom
        cat = category
        if is_preco_page:
            n = name.lower()
            if "one piece" in n:
                cat = "One Piece"
            elif "pok" in n:
                cat = "Pokemon"
            else:
                continue

        # Scellé uniquement (le catalogue Philibert est très large)
        if not any(k in name.lower() for k in SEALED_KEYWORDS):
            continue

        # Langue explicite sur la carte : OP = anglais, Pokémon = français, JP exclu
        lang_tag = card.select_one(".product-card__feature")
        lang = lang_tag.get_text(strip=True) if lang_tag else ""
        if lang == "Japonais":
            continue
        if cat == "One Piece" and lang == "Français":
            continue

        price_tag = card.select_one(".product-card__price")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        stock_tag  = card.select_one("p.stock-label")
        stock_txt  = stock_tag.get_text(strip=True).lower() if stock_tag else ""
        labels_tag = card.select_one(".product-card__labels")
        labels_txt = labels_tag.get_text(" ", strip=True).lower() if labels_tag else ""
        if is_preco_page or detect_preorder_from_text(stock_txt + " " + labels_txt):
            stock = "preorder"
        elif "indisponible" in stock_txt:
            stock = "rupture"
        elif card.select_one("[data-action='add']"):
            stock = "disponible"
        else:
            stock = "rupture"

        if not is_english(name):
            continue
        key = f"Philibert::{cat}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Philibert", "category": cat}

    return products


def scrape_ultrajeux(url, category):
    r = safe_request(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

    for block in soup.select(".block_produit"):
        title_tag = block.select_one("p.titre a")
        if not title_tag:
            continue
        name = (title_tag.get("title") or title_tag.get_text(strip=True)).strip()
        link = "https://www.ultrajeux.com/" + title_tag.get("href", "")

        price_tag = block.select_one("span.prix")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        dispo = block.select_one("p.disponibilite")
        d = dispo.get_text(" ", strip=True).lower() if dispo else ""
        if detect_preorder_from_text(d):
            stock = "preorder"
        elif "indisponible" in d or "rupture" in d or "épuisé" in d:
            stock = "rupture"
        elif "disponible" in d:
            stock = "disponible"
        else:
            stock = "rupture"

        if not is_english(name):
            continue
        key = f"Ultrajeux::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Ultrajeux", "category": category}

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
        (scrape_philibert,     PHILIBERT_ONE_PIECE,    "One Piece"),
        (scrape_philibert,     PHILIBERT_POKEMON,      "Pokemon"),
        (scrape_philibert,     PHILIBERT_PRECO_TCG,    "One Piece"),  # cat déduite du nom
        (scrape_ultrajeux,     ULTRAJEUX_ONE_PIECE_EN,     "One Piece"),
        (scrape_ultrajeux,     ULTRAJEUX_POKEMON_DISPLAYS, "Pokemon"),
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

# Seuls ces types déclenchent une alerte Telegram
ALERT_PRIORITY = ["NEW_PREORDER", "PREORDER", "RESTOCK", "PRICE_DROP"]

# Baisse de prix minimale pour alerter (vidage de stock)
PRICE_DROP_MIN = 0.10   # −10%

ALERT_CONFIG = {
    "NEW_PREORDER": {"emoji": "🆕⏳", "label": "NOUVEAU en PRÉCO"},
    "PREORDER":     {"emoji": "⏳",   "label": "PASSÉ en PRÉCO"},
    "RESTOCK":      {"emoji": "🔥",   "label": "RETOUR EN STOCK"},
    "PRICE_DROP":   {"emoji": "📉",   "label": "BAISSE DE PRIX"},
}

def build_alert_block(alert_type, product):
    cfg = ALERT_CONFIG[alert_type]
    p = product
    price_line = f"💰 {p['price']}"
    if alert_type == "PRICE_DROP" and p.get("old_price"):
        price_line = f"💰 {p['old_price']} → <b>{p['price']}</b>"
    return (
        f"{cfg['emoji']} <b>{cfg['label']}</b>\n"
        f"📦 {p['name']}\n"
        f"🏪 {p['boutique']}\n"
        f"{price_line}\n"
        f"🔗 {p['link']}"
    )

def build_telegram_message(alerts):
    # Grouper par catégorie puis par type
    from collections import defaultdict
    by_cat = defaultdict(lambda: defaultdict(list))
    for t, p in alerts:
        by_cat[p["category"]][t].append(p)

    lines = ["🚨 <b>ALERTES TCG</b> 🚨"]

    for cat in ["One Piece", "Pokemon"]:
        if cat not in by_cat:
            continue

        # Résumé de la catégorie
        cat_alerts = by_cat[cat]
        precos  = len(cat_alerts.get("NEW_PREORDER", [])) + len(cat_alerts.get("PREORDER", []))
        restocks = len(cat_alerts.get("RESTOCK", []))
        drops = len(cat_alerts.get("PRICE_DROP", []))
        summary_parts = []
        if precos:
            summary_parts.append(f"⏳ {precos} préco{'s' if precos > 1 else ''}")
        if restocks:
            summary_parts.append(f"🔥 {restocks} restock{'s' if restocks > 1 else ''}")
        if drops:
            summary_parts.append(f"📉 {drops} baisse{'s' if drops > 1 else ''}")

        lines.append(f"\n<b>── {cat} ──</b>  {' · '.join(summary_parts)}")

        # Détail par type (précos d'abord, restocks, puis baisses de prix)
        for alert_type in ALERT_PRIORITY:
            for p in cat_alerts.get(alert_type, []):
                lines.append("\n" + build_alert_block(alert_type, p))
                lines.append("─────────────────")

    return "\n".join(lines).rstrip("─────────────────").strip()

# ======================
# MAIN
# ======================

def main():
    print("Scan des produits...")

    old     = load_saved()
    current = get_all_products()

    print(f"\n{len(current)} produits detectes au total\n")

    alerts = []

    for k, v in current.items():
        if k not in old:
            if v["stock"] == "preorder":
                alerts.append(("NEW_PREORDER", v))
            # Les simples nouveaux disponibles sont ignorés (trop de bruit)
        else:
            prev_stock = old[k]["stock"]
            curr_stock = v["stock"]
            if prev_stock != curr_stock:
                if curr_stock == "preorder":
                    alerts.append(("PREORDER", v))
                elif curr_stock == "disponible":
                    alerts.append(("RESTOCK", v))
            # Vidage de stock : baisse de prix sur un produit achetable
            if curr_stock != "rupture":
                old_p = parse_price(old[k].get("price"))
                new_p = parse_price(v.get("price"))
                if old_p and new_p and new_p <= old_p * (1 - PRICE_DROP_MIN):
                    alerts.append(("PRICE_DROP", {**v, "old_price": old[k]["price"]}))

    if alerts:
        msg = build_telegram_message(alerts)
        print(msg)
        send_telegram(msg)
        print(f"\n[alert] {len(alerts)} alerte(s) envoyee(s) sur Telegram")
    else:
        print("[alert] Rien de nouveau")

    save(current, old)


if __name__ == "__main__":
    main()
