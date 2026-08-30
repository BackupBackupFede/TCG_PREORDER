"""Veille par diff de SKU sur /products.json.

Un seul mecanisme, volontairement : on telecharge le catalogue JSON de chaque
boutique Shopify de la watchlist et on le compare a la photo precedente.

  - handle absent la fois d'avant           -> NOUVEAU   (preco qui ouvre, nouveaute)
  - handle connu, indispo -> dispo          -> RESTOCK

Deux regles, pas trois. La baisse de prix a ete retiree volontairement : elle
etait relative au dernier prix vu chez CE marchand, jamais au marche, donc elle
ratait les boutiques structurellement moins cheres et bruitait sur les
promotions sans interet. Le prix reste affiche dans l'alerte, comme contexte.

Pas de selecteur CSS, pas de navigateur, pas d'anti-bot a contourner : le jour
ou une boutique refait son HTML, ca continue de marcher. Le jour ou elle ferme
son /products.json, on le voit tout de suite (compteur a zero -> alerte de
maintenance, jamais un silence).

Usage :
    python tools/skuwatch.py              # boutiques 'actif' de data/watchlist.csv
    python tools/skuwatch.py --banc       # + les boutiques du banc

Etat : data/skuwatch_state.json (une entree par boutique/handle).
Notif Telegram si TELEGRAM_TOKEN_2 / TELEGRAM_CHAT_ID_2 sont poses, sinon stdout.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# La console Windows est en cp1252 et fait planter tout print d'emoji ou
# d'ideogramme. On force l'UTF-8 en sortie plutot que d'appauvrir les messages.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
WATCHLIST = os.path.join(DATA, "watchlist.csv")
STATE = os.path.join(DATA, "skuwatch_state.json")

# Le brief exige un User-Agent identifiable ET joignable. On pointe le depot
# public plutot qu'une adresse personnelle : un admin qui voit passer ce bot
# dans ses logs peut lire exactement ce qu'il fait, sa cadence et sa liste de
# cibles. C'est plus informatif qu'un mailto, et ca n'expose rien de prive.
# CONTACT_EMAIL reste honore s'il est pose, mais il n'est pas necessaire.
DEPOT = "https://github.com/BackupBackupFede/TCG_PREORDER"
CONTACT = os.getenv("CONTACT_EMAIL", "")
IDENT = f"mailto:{CONTACT}" if CONTACT else DEPOT
UA = {"User-Agent": f"Mozilla/5.0 (compatible; FlippingResearchBot/1.0; +{IDENT})"}

PAUSE_PAR_PAGE = 1.0      # politesse intra-domaine : une page par seconde, jamais moins
# Domaines traites en meme temps. La politesse se compte PAR domaine, donc rien
# n'interdit le parallelisme cote boutiques -- c'est la connexion LOCALE qui
# plafonne. Mesure du 2026-08-30 sur 31 boutiques, en partage de connexion
# telephone :  8 fils -> 484 s et 20 echecs reseau ;  3 fils -> 637 s et 2 echecs.
# Plus lent mais fiable : on garde 3. Sur un runner GitHub (connexion datacenter)
# poser SKUWATCH_PARALLELE=8, le probleme n'existe pas la-bas.
PARALLELE = int(os.getenv("SKUWATCH_PARALLELE", "3"))
PAGES_MAX = 4             # 4 x 250 = 1000 produits, suffisant partout
TIMEOUT = 20

# Le seul filtre produit : on jette les singles et les accessoires (cf. brief).
# Pas de liste blanche de paliers - un display mal nomme doit rester.
BRUIT = re.compile(
    r"sleeve|prot[eè]ge|classeur|binder|portfolio|toploader|deckbox|deck box|"
    r"playmat|tapis|single|carte à l'unit|acryl|plexi|magnetic|\bpsa\b|\bbgs\b|"
    r"graded|folder|album|dado|dice|t-shirt|mug|figur|funko|puzzle|plush|peluche", re.I)
# "EN" en majuscules seulement : "- EN" en fin de titre est un marqueur, mais "en"
# minuscule est un mot courant en FR/ES/NL/IT et produisait des faux positifs.
EN_MAJ = re.compile(r"\bEN\b")
EN = re.compile(r"\b(eng|english|anglais|englisch|inglese|ingl[ée]s)\b|\(en\)|\[en\]", re.I)
JP = re.compile(r"\b(jp|jpn|jap|japanese|japonais|japanisch|giapponese|japones|japonés)\b|"
                r"日本語|ボックス|\(jp\)|\[jp\]", re.I)
# Franchise OU mot de produit scellé : beaucoup de boutiques nomment le set sans
# jamais écrire « Pokémon » (« Black Bolt JP Booster Box » chez biridama.pt).
TCG = re.compile(r"pok[ée]mon|one\s*piece|\bop-?\d\d\b|\bsv\d|\bme\d\d\b|"
                 r"booster|display|\betb\b|elite trainer|coffret|bundle|\btin\b|\bbox\b|ボックス", re.I)


def maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def langue(titre):
    if JP.search(titre):
        return "JP"
    if EN.search(titre) or EN_MAJ.search(titre):
        return "EN"
    return None


def lit_page(url):
    """GET avec backoff exponentiel sur 429/503. Shopify limite a la rafale ;
    un 429 isole ne doit pas etre pris pour une boutique cassee."""
    for essai in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as h:
                return json.loads(h.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or essai == 2:
                raise
            attente = float(e.headers.get("Retry-After") or 0) or (5 * 2 ** essai)
            time.sleep(min(attente, 30))
    raise RuntimeError("inatteignable")


def catalogue(domaine):
    """Retourne {handle: {...}} du scellé EN/JP. Leve si l'endpoint est mort."""
    produits, page = [], 1
    while page <= PAGES_MAX:
        lot = lit_page(f"https://{domaine}/products.json?limit=250&page={page}").get("products", [])
        if not lot:
            break
        produits += lot
        page += 1
        time.sleep(PAUSE_PAR_PAGE)

    out = {}
    for p in produits:
        titre = p.get("title", "")
        if BRUIT.search(titre) or not TCG.search(titre):
            continue
        lang = langue(titre)
        if not lang:
            continue
        variantes = p.get("variants") or []
        prix = min((float(v["price"]) for v in variantes if v.get("price")), default=None)
        out[p["handle"]] = {
            "titre": titre[:120],
            "langue": lang,
            "dispo": any(v.get("available") for v in variantes),
            "prix": prix,
            "url": f"https://{domaine}/products/{p['handle']}",
        }
    return out


def charge_cibles(avec_banc):
    statuts = {"actif", "banc"} if avec_banc else {"actif"}
    with open(WATCHLIST, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r["statut"] in statuts]


def notifie(lignes):
    texte = "\n".join(lignes)
    # Toujours tracer, meme quand on envoie sur Telegram : sinon un run GitHub
    # n'a aucune trace de ce qu'il a notifie et devient impossible a auditer.
    print(texte, flush=True)
    token, chat = os.getenv("TELEGRAM_TOKEN_2"), os.getenv("TELEGRAM_CHAT_ID_2")
    if not (token and chat):
        return
    for i in range(0, len(texte), 3500):
        data = urllib.parse.urlencode({
            "chat_id": chat, "text": texte[i:i + 3500], "disable_web_page_preview": "true"
        }).encode()
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
                timeout=TIMEOUT)
        except Exception as e:
            print(f"Telegram KO ({e}) - repli stdout\n{texte}")
            return


def main():
    avec_banc = "--banc" in sys.argv
    etat = {}
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            etat = json.load(f)
    premier_run = not etat

    evenements, pannes, coupures = [], [], []
    cibles = charge_cibles(avec_banc)

    def releve(cible):
        """Un seul appel reseau par domaine. Rien d'autre : la comparaison se
        fait apres, dans le fil principal, pour rester deterministe."""
        d = cible["domaine"]
        try:
            return d, catalogue(d), None
        except Exception as e:
            return d, None, type(e).__name__

    with ThreadPoolExecutor(max_workers=PARALLELE) as ex:
        releves = list(ex.map(releve, cibles))

    for d, actuel, erreur in releves:
        if erreur:
            # URLError / timeout = la connexion a saute de NOTRE cote aussi bien
            # que du leur. On ne peut pas trancher boutique par boutique : on
            # compte, et on decide apres la boucle (voir plus bas).
            if erreur in ("URLError", "TimeoutError", "timeout", "ConnectionResetError",
                          "ConnectionAbortedError", "RemoteDisconnected", "IncompleteRead"):
                coupures.append(d)
            else:
                pannes.append(f"⚠️ {d} injoignable ({erreur})")
            continue

        precedent = etat.get(d, {})
        # Endpoint vivant mais catalogue vide alors qu'il ne l'etait pas :
        # c'est une panne, pas une absence de stock. On ne l'ecrase pas.
        if precedent and not actuel:
            pannes.append(f"⚠️ {d} : 0 référence alors qu'il y en avait {len(precedent)} — endpoint à vérifier")
            continue

        # Boutique ajoutee a la watchlist depuis le dernier run : on pose sa photo
        # sans rien notifier. Sinon l'ajout d'une boutique noie le canal sous son
        # catalogue entier presente comme autant de nouveautes.
        nouvelle_boutique = not precedent

        for handle, p in actuel.items():
            av = precedent.get(handle)
            if av is None:
                if not premier_run and not nouvelle_boutique:
                    evenements.append(f"🆕 NOUVEAU [{p['langue']}] {d} — {p['titre']} — {p['prix']}\n{p['url']}")
            elif p["dispo"] and not av.get("dispo"):
                evenements.append(f"📦 RESTOCK [{p['langue']}] {d} — {p['titre']} — {p['prix']}\n{p['url']}")

        etat[d] = actuel
        print(f"{d:26} {len(actuel):4} réfs EN/JP", flush=True)

    # Une coupure reseau isolee vaut une alerte ; une coupure massive n'en vaut
    # qu'une seule, la notre. Sans ce regroupement un partage de connexion qui
    # tombe produit une alerte par boutique surveillee.
    if len(coupures) >= max(3, len(cibles) // 3):
        pannes.append(f"⚠️ Connexion perdue pendant le run — {len(coupures)} boutiques "
                      f"non vérifiées, aucune conclusion tirée. Relancer.")
    else:
        pannes += [f"⚠️ {d} injoignable (réseau)" for d in coupures]

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)

    if premier_run:
        total = sum(len(v) for v in etat.values())
        print(f"\nPhoto de référence posée : {total} références sur {len(etat)} boutiques. "
              f"Les alertes commencent au prochain run.")
        if pannes:
            notifie(pannes)
        return

    if evenements or pannes:
        notifie([f"TCG watch — {maintenant()}"] + evenements + pannes)
    else:
        print("\nRien de neuf.")


if __name__ == "__main__":
    main()
