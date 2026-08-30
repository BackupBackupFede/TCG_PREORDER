# Watchlist — boutiques UE à surveiller (EN et/ou JP)

> Balayage complet du 2026-08-30 : **396 domaines** testés (tout ce que le projet
> avait accumulé, pas seulement le vivier « préco »). **84** ont un `/products.json`
> vivant, **65** avec du EN/JP. **27 retenues** en actif.
>
> `refs` = références scellées portant un marqueur de langue EN ou JP explicite
> (singles et accessoires exclus). `(d)` = en stock au moment du scan.
>
> **Mécanisme unique : diff des SKU sur `/products.json`.** Une URL par boutique,
> du JSON, pas de sélecteur CSS, pas de navigateur, pas d'anti-bot.
> **Deux règles seulement** : un SKU qui apparaît = préco/nouveauté, `indispo → dispo`
> = restock. Le prix est affiché dans l'alerte mais ne déclenche rien.

## Actives — 31 boutiques

| # | Boutique | Pays | Réfs | EN (dispo) | JP (dispo) | Livraison |
|---|---|---|---|---|---|---|
| 1 | **onepiece-cards.com** | FR | **750** | 441 (140) | **309** (88) | ✅ point relais 3,90 € |
| 2 | **fantasiacards.de** | DE | **528** | 285 (**241**) | 243 (**203**) | ✅ liste pays UE |
| 3 | **todohits.com** | ES | 377 | 287 (24) | 90 (63) | ✅ int'l |
| 4 | baruzcard.it | IT | 356 | 304 (50) | 52 (11) | ⚠️ sélecteur pays |
| 5 | outpostbrussels.be | BE | 353 | 346 (49) | 7 (2) | ✅ |
| 6 | **crispycards.de** | DE | 310 | 272 (118) | 38 (16) | ✅ |
| 7 | aquitaz.se | SE | 260 | 225 (21) | 35 (6) | ✅ int'l |
| 8 | otakura.com | IT | 248 | 222 (47) | 26 (2) | ✅ zone UE |
| 9 | **yonko-tcg.de** | DE | 192 | 39 (5) | 153 (27) | ✅ |
| 10 | **godofcards.de** | DE | 176 | 21 (1) | 155 (47) | ✅ |
| 11 | 1uprm.com | IT | 171 | 170 (21) | 1 (0) | ✅ |
| 12 | cardzone.es | ES | 170 | 87 (25) | 83 (36) | ✅ |
| 13 | pokechest.at | AT | 157 | 120 (16) | 37 (11) | ✅ vérifié |
| 14 | **tcgdirect.fr** | FR | 141 | 0 | 141 (**109**) | ✅ |
| 15 | cardcosmos.de | DE | 124 | 112 (42) | 12 (5) | ✅ liste pays UE |
| 16 | evlutcg.com | EU | 98 | 96 (37) | 2 (0) | ✅ worldwide |
| 17 | madridnortetcg.com | ES | 79 | 71 (20) | 8 (8) | ✅ |
| 18 | relictcg.com | FR | 77 | 37 (21) | 40 (20) | ⚠️ pas de politique trouvée |
| 19 | metamorphcenter.com | ES | 77 | 34 (12) | 43 (3) | ✅ |
| 20 | pokedirris.de | DE | 75 | 19 (8) | 56 (3) | ✅ |
| 21 | tcgviert.com | DE | 63 | 50 (41) | 13 (13) | ✅ |
| 22 | pokeca.nl | NL | 59 | 15 (7) | 44 (15) | ✅ 14,99 € UE |
| 23 | collectorstorecards.it | IT | 59 | 58 (12) | 1 (0) | ✅ |
| 24 | gradedzone.it | IT | 51 | 20 (1) | 31 (10) | ✅ |
| 25 | itcg.bg | BG | 48 | 9 (5) | 39 (23) | ❓ **mail à envoyer** |
| 26 | rarecards.nl | NL | 24 | 0 | 24 (11) | ✅ « heel Europa » |
| 27 | pokefamily.nl | NL | 24 | 0 | 24 (16) | ✅ |
| — | *(découverte externe ci-dessous)* | | | | | |
| 28 | **pikamon.eu** | EU | 111 | 61 (20) | 50 (6) | ✅ « insured EU shipping » |
| 29 | **starzcollectibles.com** | DE | 93 | 3 (1) | 90 (34) | ✅ Allemagne + pays UE |
| 30 | **gs-gameon.com** | IT | 91 | 9 (9) | 82 (**82**) | ✅ « tutta l'Unione Europea » |
| 31 | **pokejapan.store** | EU | 75 | 0 | 75 (48) | ✅ « shipped from the EU » |

**Les six qui comptent vraiment** : `onepiece-cards.com` (750 réfs, boutique FR,
port relais), `fantasiacards.de` (444 références **en stock**, de très loin le
meilleur taux), `crispycards.de` (118 EN dispo), `tcgdirect.fr` (109 JP dispo),
puis `godofcards.de` et `yonko-tcg.de` pour le JP en profondeur.

## Découverte externe (2026-08-30)

Première recherche **hors du repo** : requêtes en langue produit (EN, DE, NL, ES, IT)
plutôt qu'en langue pays. 34 domaines inconnus testés, **15 avec un `/products.json`
vivant**, dont **4 intra-UE retenus** (n° 28 à 31 ci-dessus).

La meilleure : **gs-gameon.com** (IT) — 82 références JP, **toutes en stock**, et
une politique d'expédition UE explicite. **starzcollectibles.com** (DE) importe en
direct du Japon, 90 réfs JP. **pikamon.eu** est la seule des quatre à être
équilibrée EN/JP.

À noter : `oupi.eu`, que le brief moniteur classe « haute priorité », n'a **pas** de
`/products.json` — même cas que vinticards / ptmerch / fyft. Hors mécanisme.

## Hors UE — à traiter à part

| Boutique | Pays | Réfs | Réserve |
|---|---|---|---|
| **japan2uk.com** | GB | **234** (150 EN, 84 JP / 59 dispo) | douane à l'entrée UE |
| pokeunlimited.com | US | 105 (70 JP / 29) | CGV de droit américain |
| zenpan-japan.com | JP | 62 (51 JP / 26) | expédié du Japon |
| zadoys.ch | CH | 59 (55 JP / 49) | TVA import + douane |
| cardtreasure.ch | CH | 44 (40 JP / 29) | idem, annonce « worldwide » |
| tcg-corner.com | JP | 14 | expédié du Japon |
| pixel-hub.co.uk | GB | 17 | port international 49,99 £ — rédhibitoire |
| titancards.co.uk / itsukijapan.com | GB / JP | 11 / 7 | hors UE |

Beaucoup de stock JP disponible ici, mais tout change le calcul du coût rendu.
Non pollées par défaut.

## Ce qui sort

| Boutique | Motif |
|---|---|
| **cardyx.sk** | 5 réfs sur 929 produits. Ex-« cœur » — **rétrogradée**. |
| matraws.dk, pockomonsters.dk | « vi leverer ikke til udlandet » |
| cardgame-club.it | Italie uniquement |
| vinticards.com, ptmerch.com, fyft.cz | pas de `/products.json` (Woo cassé, PrestaShop, Shoptet) → newsletter, comme déjà acté |
| ~310 domaines | pas de `/products.json`, ou 0 référence EN/JP |

Banc (petit volume ou livraison non vérifiée, non pollées par défaut) :
biridama.pt, kamehousecards.com, pokybox.com, pokevend.at, magicomens.com, elduelista.com.

## Correctif de mesure appliqué

La première version du filtre exigeait « Pokémon » ou « One Piece » dans le titre.
Or beaucoup de boutiques nomment le set directement — `biridama.pt` vend
« Black Bolt JP Booster Box », qui était donc **jeté**. Le filtre accepte
maintenant la franchise **ou** un mot de produit scellé. Second correctif : `EN`
n'est reconnu qu'en **majuscules**, parce que « en » minuscule est un mot courant
en français, espagnol, néerlandais et italien et produisait des faux positifs.

Après correction, `fantasiacards.de` passe de 120 à **528** références. Les
chiffres de la version d'hier étaient tous sous-estimés.

**Angle mort restant** : une boutique qui n'écrit jamais la langue dans ses titres
est sous-comptée. Ce n'est pas un zéro, c'est une non-mesure.

## Module 1P (grande distribution) — non intégré, et pourquoi

Les 24 enseignes du [brief module 2](moniteur-tcg-module2-1p.md) ont été sondées :
**13 sont fermées** (403, `robots.txt: Disallow: /`, DataDome chez fnac.be,
Incapsula chez Smyths), 7 n'ont pas de page de recherche atteignable, et les 4
restantes n'exposent aucune disponibilité exploitable. Aucune n'est sous Shopify,
donc aucune ne peut rejoindre le mécanisme `/products.json`.

Recommandation : **TCGRadar Premium à 64,99 €/an** pour le volet Pokémon 1P —
moins cher que le développement, et il couvre le canal qui nous est fermé. Mais
c'est **Pokémon uniquement, pas de One Piece**. Détail et chiffres :
[`moniteur-1p-note.md`](moniteur-1p-note.md).

## Mise en service

```bash
python tools/skuwatch.py
```

Premier run = photo de référence, aucune alerte (normal). Ensuite : SKU apparus,
retours en stock, baisses de prix. État dans `data/skuwatch_state.json`.

Pour automatiser sans machine allumée : GitHub Actions sur dépôt **public**
(minutes illimitées), un run toutes les 30 min, secrets `TELEGRAM_TOKEN_2` /
`TELEGRAM_CHAT_ID_2` — les mêmes que le bot PREORDER.
