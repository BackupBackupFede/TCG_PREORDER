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

# Displays uniquement — la cat. 379 "booster anglais" liste les boosters à
# l'unité (~9€), sans intérêt pour le flip
ULTRAJEUX_ONE_PIECE_DISPLAYS = "https://www.ultrajeux.com/cat-0-1031-470-one-piece-card-game-boite-de-boosters-anglais.html"
ULTRAJEUX_POKEMON_DISPLAYS   = "https://www.ultrajeux.com/cat-0-4-469-pokemon-boite-de-boosters-francais.html"

# Produits scellés pertinents pour le flip (filtre Philibert, catalogue trop large)
SEALED_KEYWORDS = ["booster", "display", "boîte", "boite", "coffret",
                   "bundle", "collection", "etb", "box", "tripack",
                   "elite trainer"]

# Dealabs — veille communautaire : couvre la grande distribution (Carrefour,
# Auchan, Fnac, Leclerc...) que leurs bot-walls rendent inscrapables en direct
DEALABS_POKEMON_RSS = "https://www.dealabs.com/rss/groupe/pokemon"
DEALABS_NOUVEAUX_RSS = "https://www.dealabs.com/rss/nouveaux"

# Vinted — sourcing inversé : displays/cases de particuliers sous le prix
# retail. (Leboncoin est derrière Datadome → infaisable en requests ;
# utiliser les recherches sauvegardées de l'app à la place.)
VINTED_QUERIES = [
    ("one piece display", "One Piece"),
    ("pokemon display",   "Pokemon"),
]
VINTED_MAX_ALERTS   = 5      # cap par run (le 1er run voit tout comme nouveau)
VINTED_DISCOUNT_MIN = 0.10   # deal si ≤ 90% du meilleur prix retail connu

# Une réf. retail n'est crédible que si elle est dans la bande MSRP : sur un
# set épuisé, la seule boutique restante price au niveau collector (ex: EV02 à
# 349,90€ chez Ultrajeux) et tout prix de revente normal passerait pour un
# deal. Au-dessus du plafond (ou sans réf.) → pas d'alerte SOURCING du tout.
CREDIBLE_RETAIL_CAP = {
    ("One Piece", "display"): 160,
    ("One Piece", "case"):    1500,
    ("Pokemon",   "display"): 280,
    ("Pokemon",   "case"):    1700,
}

# Mots-clés qui indiquent un statut précommande dans les boutons/labels
PREORDER_KEYWORDS = ["précommande", "precommande", "pre-order", "preorder", "pre order", "réserver", "reserver"]

# Langues : One Piece = EN uniquement ; Pokémon = FR accepté (displays FR
# monitorés volontairement, ex. Ultrajeux EV/ME)
ALLOWED_LANGS = ["(en)", "- en", "_en"]

def is_english(name, category=None):
    n = name.lower()
    # "English Version" explicite → on garde, même si "Japanese" apparaît
    # ailleurs dans le nom (ex: "Japanese 3rd Anniversary Set English Version")
    if "english" in n or any(tag in n for tag in ALLOWED_LANGS):
        return True
    # Exclure JP et KR quel que soit le jeu ("japan/japon" couvre aussi
    # japanese/japonais/japonaise)
    if re.search(r"\((?:jp|jap|kr)\)|\bjp\b|\bjap\b|\bkr\b|japan|japon|korean|cor[ée]en", n):
        return False
    # FR taggué explicitement
    if "(fr)" in n or "- fr" in n:
        return False
    # Token "FR" nu (ex: "JCC FR", "booster FR") → exclu pour One Piece seulement
    if category == "One Piece" and re.search(r"\bfr\b", n):
        return False
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
# NORMALISATION (set / tier)
# ======================
# Le même produit existe chez plusieurs boutiques sous des noms différents
# ("Boite de 24 Boosters - OP16", "One Piece Card Game Display OP16",
# "OP-16 Case"...). On extrait un code de set normalisé + un tier (display /
# case / booster...) pour pouvoir comparer les prix entre boutiques.

SET_CODE_RE = re.compile(r"\b(OP|EB|PRB|ST|EV|ME|SV)[\s\-]?(\d{1,3})\b", re.I)

def extract_set_code(name):
    """'OP-16', 'OP16', 'op 16' → 'OP16'. None si pas de code."""
    m = SET_CODE_RE.search(name)
    if not m:
        return None
    return f"{m.group(1).upper()}{int(m.group(2)):02d}"

# Ordre important : premier motif qui matche gagne.
# - "case" avant "display" (MM : "Case ... Booster Box")
# - "double-pack" avant "display" ("Double pack - 2 boosters")
# - "display-promo" séparé : les displays avec carte promo/box topper sont
#   plus chers, les mélanger fausserait l'arbitrage
TIER_RULES = [
    ("case",          [r"\bcase\b", r"\bcarton\b"]),
    ("display-promo", [r"box\s*topper", r"avec carte promo"]),
    ("double-pack",   [r"double\s*pack", r"duo\s*packs?"]),
    ("blister",       [r"\bblisters?\b"]),
    ("display",       [r"\bdisplay\b", r"bo[iî]te de \d+\s*boosters",
                       r"bo[iî]te \d+\s*boosters", r"\b\d+\s*boosters\b",
                       r"booster\s*box", r"boosterbox"]),
    ("etb",           [r"\betb\b", r"elite trainer"]),
    ("deck",          [r"\bdeck\b", r"\bstarter\b"]),
    ("coffret",       [r"\bcoffret\b", r"\bbundle\b", r"\btripack\b",
                       r"illustration box", r"mini[\s\-]?tin",
                       r"\bcollection\b", r"anniversary set"]),
    ("booster",       [r"\bbooster\b"]),
]

# Fourchettes de prix plausibles par (catégorie, tier) — sert de fallback de
# classification ET de garde-fou arbitrage contre les prix mal parsés
PRICE_SANITY = {
    ("One Piece", "display"): (60, 300),
    ("One Piece", "case"):    (500, 2600),
    ("Pokemon",   "display"): (90, 900),
    ("Pokemon",   "case"):    (900, 6000),
}

def classify_tier(name, price=None, category=None):
    n = name.lower()
    for tier, patterns in TIER_RULES:
        if any(re.search(p, n) for p in patterns):
            return tier
    # Aucun mot-clé (ex: Mystery Media "One Piece — Royal Blood OP-10") :
    # code de set + prix dans la fourchette display → display
    p = parse_price(price)
    if extract_set_code(name) and p:
        lo, hi = PRICE_SANITY.get((category, "display"), (60, 900))
        if lo <= p <= hi:
            return "display"
    return "other"

# ======================
# ARBITRAGE CROSS-SHOP
# ======================
# Compare le prix d'un même (set, tier) entre boutiques. Alerte quand l'offre
# la moins chère (dispo ou préco) est nettement sous le prix médian des autres
# boutiques — c'est le signal d'achat.

ARBITRAGE_TIERS   = ("display", "case")
ARBITRAGE_MIN_PCT = 0.12   # écart mini vs médiane des autres boutiques
ARBITRAGE_MIN_EUR = 15     # ET écart mini en valeur absolue

def _arbitrage_groups(products):
    """Groupe les offres achetables par (catégorie, set, tier), triées par prix."""
    groups = {}
    for key, v in products.items():
        if v["stock"] not in ("disponible", "preorder"):
            continue
        code = extract_set_code(v["name"])
        if not code:
            continue
        tier = classify_tier(v["name"], v.get("price"), v.get("category"))
        if tier not in ARBITRAGE_TIERS:
            continue
        price = parse_price(v.get("price"))
        if not price:
            continue
        # Garde-fou : prix hors fourchette = probable erreur de parsing
        lo, hi = PRICE_SANITY.get((v.get("category"), tier), (0, 10**6))
        if not (lo <= price <= hi):
            continue
        groups.setdefault((v["category"], code, tier), []).append((price, key, v))
    for rows in groups.values():
        rows.sort(key=lambda r: r[0])
    return groups

def find_arbitrage_alerts(current, old):
    from statistics import median

    groups     = _arbitrage_groups(current)
    old_groups = _arbitrage_groups(old)

    alerts = []
    for (cat, code, tier), rows in groups.items():
        if len({v["boutique"] for _, _, v in rows}) < 2:
            continue
        best_price, best_key, best_v = rows[0]

        other_prices = [p for p, _, v in rows if v["boutique"] != best_v["boutique"]]
        ref = median(other_prices)
        spread = ref - best_price
        if spread < ARBITRAGE_MIN_EUR or spread / ref < ARBITRAGE_MIN_PCT:
            continue

        # Anti-répétition : on réalerte seulement si le GROUPE a changé depuis
        # le dernier run (nouvelle offre, prix ou stock modifié, boutique qui
        # rejoint/quitte) — sinon re-spam toutes les 30 min
        signature = [(k, p, v["stock"]) for p, k, v in rows]
        old_signature = [(k, p, v["stock"]) for p, k, v in old_groups.get((cat, code, tier), [])]
        if signature == old_signature:
            continue

        comparison = " · ".join(
            f"{v['boutique']} {p:.2f}€" for p, _, v in rows[1:4]
        )
        alerts.append(("ARBITRAGE", {
            **best_v,
            "set_code":   code,
            "tier":       tier,
            "ref_price":  ref,
            "spread_pct": round(100 * spread / ref),
            "comparison": comparison,
        }))

    return alerts

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

        if not is_english(name, category):
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

        if not is_english(name, category):
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

        if not is_english(name, category):
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

        # En promo, ".price" concatène ancien + nouveau prix ("24,99 ... 22,49")
        # → parse_price sort un nombre absurde. <ins> = prix soldé actuel.
        price_tag = item.select_one(".price ins .woocommerce-Price-amount") \
                    or item.select_one(".price ins") \
                    or item.select_one(".price .woocommerce-Price-amount") \
                    or item.select_one(".price")
        price = price_tag.text.strip() if price_tag else "N/A"

        item_classes = item.get("class", [])
        item_text = item.text
        if "preorder" in " ".join(item_classes).lower() or detect_preorder_from_text(item_text):
            stock = "preorder"
        elif "outofstock" in item_classes:
            stock = "rupture"
        else:
            stock = "disponible"

        if not is_english(name, category):
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

        if not is_english(name, category):
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

        if not is_english(name, cat):
            continue
        key = f"Philibert::{cat}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Philibert", "category": cat}

    return products


def scrape_dealabs(url, category):
    """RSS Dealabs. Ne garde que les deals TCG scellés (franchise + produit).
    category est ignorée : déduite du titre (le flux 'nouveaux' mélange tout)."""
    r = safe_request(url)
    if not r:
        return {}

    products = {}
    for item in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        m_title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.S)
        m_link  = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", item, re.S)
        if not m_title or not m_link:
            continue
        title = m_title.group(1).strip()
        link  = m_link.group(1).strip()
        t = title.lower()

        # Bruit : jeux vidéo (catégorie RSS) et versions japonaises
        m_cat = re.search(r"<category>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</category>", item, re.S)
        rss_cat = m_cat.group(1).lower() if m_cat else ""
        if "jeux vidéo" in rss_cat or "console" in rss_cat:
            continue
        if "japonais" in t or "(jp)" in t:
            continue

        if "one piece" in t:
            cat = "One Piece"
        elif "pokemon" in t or "pokémon" in t:
            cat = "Pokemon"
        else:
            continue
        if not any(k in t for k in SEALED_KEYWORDS):
            continue

        # Enseigne + prix fournis par le flux (pepper:merchant)
        m_merch = re.search(r'<pepper:merchant name="([^"]*)"(?:\s+price="([^"]*)")?', item)
        merchant = m_merch.group(1) if m_merch else ""
        price = (m_merch.group(2) if m_merch and m_merch.group(2) else None)
        if not price:
            m_price = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*€", title)
            price = f"{m_price.group(1)}€" if m_price else "N/A"

        key = f"Dealabs::{cat}::{title}"
        products[key] = {"name": title, "link": link, "price": price, "stock": "deal",
                         "boutique": f"Dealabs ({merchant})" if merchant else "Dealabs",
                         "category": cat}

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

        if not is_english(name, category):
            continue
        key = f"Ultrajeux::{category}::{name}"
        products[key] = {"name": name, "link": link, "price": price, "stock": stock,
                         "boutique": "Ultrajeux", "category": category}

    return products

def scrape_vinted(query, category):
    """API catalogue anonyme Vinted. Le warm-up sur /catalog fournit le cookie
    access_token_web requis (la home ne suffit pas). Filtrage strict : code de
    set + tier display/case + prix plausible — la recherche Vinted est floue
    (cartes à l'unité, produits sans rapport...)."""
    s = requests.Session()
    s.headers.update({**HEADERS, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        s.get("https://www.vinted.fr/catalog", params={"search_text": query}, timeout=15)
        r = s.get("https://www.vinted.fr/api/v2/catalog/items",
                  params={"search_text": query, "order": "newest_first", "per_page": 48},
                  headers={"Accept": "application/json"}, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception as e:
        print(f"❌ Erreur Vinted ({query}): {e}")
        return {}

    # Annonces de produits ouverts/incomplets — sans valeur pour le flip
    OPENED_RE = re.compile(r"ouvert|opened|\bvide\b|\bempty\b|sans booster|incomplet", re.I)

    products = {}
    for it in items:
        title = (it.get("title") or "").strip()
        if not title or not it.get("id"):
            continue
        if OPENED_RE.search(title):
            continue
        p = it.get("price")
        amount = p.get("amount") if isinstance(p, dict) else p
        price = f"{amount} €"

        if not is_english(title, category):
            continue
        code = extract_set_code(title)
        tier = classify_tier(title, price, category)
        if not code or tier not in ARBITRAGE_TIERS:
            continue
        pv = parse_price(price)
        lo, hi = PRICE_SANITY.get((category, tier), (0, 10**6))
        # Plancher élargi (les deals sont SOUS le retail) mais pas trop :
        # un display à -60% est un fake ou un mauvais étiquetage
        if not pv or not (lo * 0.4 <= pv <= hi):
            continue

        link = it.get("url") or f"https://www.vinted.fr/items/{it['id']}"
        key = f"Vinted::{category}::{it['id']}"
        products[key] = {"name": title, "link": link, "price": price, "stock": "vinted",
                         "boutique": "Vinted", "category": category}

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
        (scrape_ultrajeux,     ULTRAJEUX_ONE_PIECE_DISPLAYS, "One Piece"),
        (scrape_ultrajeux,     ULTRAJEUX_POKEMON_DISPLAYS,   "Pokemon"),
        (scrape_dealabs,       DEALABS_POKEMON_RSS,        "Pokemon"),
        (scrape_dealabs,       DEALABS_NOUVEAUX_RSS,       "mixte"),
    ]
    scrapers += [(scrape_vinted, q, cat) for q, cat in VINTED_QUERIES]

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

# Seuls ces types déclenchent une alerte Telegram (ordre = priorité d'affichage)
ALERT_PRIORITY = ["ARBITRAGE", "SOURCING", "NEW_PREORDER", "PREORDER", "RESTOCK", "PRICE_DROP", "DEAL"]

# Baisse de prix minimale pour alerter (vidage de stock)
PRICE_DROP_MIN = 0.10   # −10%

ALERT_CONFIG = {
    "ARBITRAGE":    {"emoji": "💱",   "label": "ARBITRAGE"},
    "SOURCING":     {"emoji": "🕵️",   "label": "SOURCING Vinted"},
    "NEW_PREORDER": {"emoji": "🆕⏳", "label": "NOUVEAU en PRÉCO"},
    "PREORDER":     {"emoji": "⏳",   "label": "PASSÉ en PRÉCO"},
    "RESTOCK":      {"emoji": "🔥",   "label": "RETOUR EN STOCK"},
    "PRICE_DROP":   {"emoji": "📉",   "label": "BAISSE DE PRIX"},
    "DEAL":         {"emoji": "🛒",   "label": "BON PLAN Dealabs"},
}

def build_alert_block(alert_type, product):
    cfg = ALERT_CONFIG[alert_type]
    p = product
    price_line = f"💰 {p['price']}"
    if alert_type == "PRICE_DROP" and p.get("old_price"):
        price_line = f"💰 {p['old_price']} → <b>{p['price']}</b>"
    if alert_type == "SOURCING":
        vs = f" (retail mini : {p['retail_ref']:.2f}€)"
        return (
            f"{cfg['emoji']} <b>{cfg['label']} {p.get('set_code', '')} ({p.get('tier', '')})</b>\n"
            f"📦 {p['name']}\n"
            f"💰 <b>{p['price']}</b>{vs}\n"
            f"🔗 {p['link']}"
        )
    if alert_type == "ARBITRAGE":
        return (
            f"{cfg['emoji']} <b>{cfg['label']} {p['set_code']} ({p['tier']}) "
            f"−{p['spread_pct']}% vs marché</b>\n"
            f"📦 {p['name']}\n"
            f"🏪 {p['boutique']} [{p['stock']}]\n"
            f"💰 <b>{p['price']}</b> (médiane autres boutiques : {p['ref_price']:.2f}€)\n"
            f"📊 {p['comparison']}\n"
            f"🔗 {p['link']}"
        )
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
        arbs    = len(cat_alerts.get("ARBITRAGE", []))
        sourcing = len(cat_alerts.get("SOURCING", []))
        precos  = len(cat_alerts.get("NEW_PREORDER", [])) + len(cat_alerts.get("PREORDER", []))
        restocks = len(cat_alerts.get("RESTOCK", []))
        drops = len(cat_alerts.get("PRICE_DROP", []))
        deals = len(cat_alerts.get("DEAL", []))
        summary_parts = []
        if arbs:
            summary_parts.append(f"💱 {arbs} arbitrage{'s' if arbs > 1 else ''}")
        if sourcing:
            summary_parts.append(f"🕵️ {sourcing} vinted")
        if precos:
            summary_parts.append(f"⏳ {precos} préco{'s' if precos > 1 else ''}")
        if restocks:
            summary_parts.append(f"🔥 {restocks} restock{'s' if restocks > 1 else ''}")
        if drops:
            summary_parts.append(f"📉 {drops} baisse{'s' if drops > 1 else ''}")
        if deals:
            summary_parts.append(f"🛒 {deals} deal{'s' if deals > 1 else ''}")

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

    # Vinted en panne (403/Cloudflare) → on conserve les clés précédentes pour
    # éviter de purger l'état et de re-alerter en rafale au retour
    if not any(k.startswith("Vinted::") for k in current):
        current.update({k: v for k, v in old.items() if k.startswith("Vinted::")})

    print(f"\n{len(current)} produits detectes au total\n")

    alerts = []
    sourcing_candidates = []

    for k, v in current.items():
        if k not in old:
            if v["stock"] == "preorder":
                alerts.append(("NEW_PREORDER", v))
            elif v["stock"] == "deal":
                alerts.append(("DEAL", v))
            elif v["stock"] == "vinted":
                sourcing_candidates.append(v)
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

    # Comparaison de prix cross-boutiques sur les displays/cases normalisés
    alerts.extend(find_arbitrage_alerts(current, old))

    # Sourcing Vinted : nouvelle annonce sous le meilleur prix retail connu
    # (nos propres scrapers servent de référence de marché). Réf. crédible
    # exigée : sans boutique qui vende le set à un prix MSRP-plausible, on ne
    # peut pas juger un deal → silence plutôt que fausses alertes.
    if sourcing_candidates:
        retail_groups = _arbitrage_groups(current)
        picked = []
        for v in sourcing_candidates:
            code = extract_set_code(v["name"])
            tier = classify_tier(v["name"], v.get("price"), v.get("category"))
            pv = parse_price(v["price"])
            rows = retail_groups.get((v["category"], code, tier))
            if not rows:
                continue
            retail_min = min(p for p, _, _ in rows)
            cap = CREDIBLE_RETAIL_CAP.get((v["category"], tier))
            if not cap or retail_min > cap:
                continue  # set épuisé pricé collector → réf. non crédible
            if pv > retail_min * (1 - VINTED_DISCOUNT_MIN):
                continue  # pas moins cher que le retail → pas un deal
            picked.append((pv, {**v, "set_code": code, "tier": tier,
                                "retail_ref": retail_min}))
        picked.sort(key=lambda x: x[0])
        alerts.extend(("SOURCING", v) for _, v in picked[:VINTED_MAX_ALERTS])

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
