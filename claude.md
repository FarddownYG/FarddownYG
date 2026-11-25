# Notes de conception

Dépôt de profil (`FarddownYG/FarddownYG`) : le README affiché sur la page
GitHub de Yanis. Thème as de pique, public mixte développeurs et recruteurs.

## Ce qu'il y a dedans

| | |
|---|---|
| `README.md` | la page du profil : cinq images, chacune en quatre versions |
| `assets/heros-*.svg` | le héros : l'as de pique en filigrane et l'identité |
| `assets/r32-*.svg` | le garage : planche technique de la Skyline GT-R R32 |
| `assets/signature-*.svg` | le mot de la fin |
| `assets/avatar.svg`, `assets/avatar.png` | la photo de profil (à téléverser à la main, voir plus bas) |
| `tools/dessin.py` | le système de design : palettes, feuille SVG, cadre, motifs, pose de l'emblème |
| `tools/typo.py` | compose le texte en tracés à partir de l'atlas de glyphes |
| `tools/glyphes.json` | l'atlas : contours, chasses, crénages (produit par `build-glyphes.py`) |
| `tools/embleme.json` | l'as de pique en filigrane (produit par `build-embleme.py`) |
| `tools/build-assets.py` | rend les images fixes : héros, garage, signature, avatar |
| `tools/build-stats.py` | calcule les statistiques et rend les deux cartes (skyline, tableau de bord) |
| `tools/empreinte.py` | empreinte des cartes hors horodatage, pour ne publier que sur changement |
| `tools/boucle-stats.sh` | recalcule en boucle et publie |
| `tools/test-stats.py` | vérifications, exécutées avant toute publication |
| `tools/build-glyphes.py`, `tools/build-embleme.py` | outils de développement (dépendances : fonttools, uharfbuzz, numpy) — la CI ne les exécute pas |
| `tools/POLICES.md` | origine et licence des polices dont l'atlas dérive |
| `.github/workflows/records.yml` | fait tourner la boucle |
| branche `stats` | les huit cartes publiées — skyline et tableau de bord, bureau et mobile, deux thèmes (orpheline, réécrite à chaque publication) |

Suffixes des fichiers : `-m` pour la mise en page mobile, `-dark` / `-light`
pour le thème. `heros-m-light.svg` est le héros, mobile, clair.

## Règles qui ne se négocient pas

**Aucun JavaScript.** GitHub nettoie le markdown des README : `<script>` est
retiré, les images sont rendues en `<img>`, donc sans interactivité ni
scripting. Toute animation passe par du CSS dans le SVG. Rien d'autre ne tient.

**Aucune ressource externe.** Les SVG ne chargent ni police ni image distante :
un `<img>` ne suit pas ces requêtes. Le texte lui-même est dessiné en tracés
(voir « Le système de design ») ; un test refuse tout `<text>`.

**Chaque élément porte son état final en attribut.** Une animation part
d'ailleurs et y revient ; elle ne pose jamais l'état final elle-même. Un moteur
qui n'anime pas, ou un visiteur qui a demandé moins de mouvement, voit donc la
bonne aiguille, la bonne barre, le bon chiffre. La règle
`prefers-reduced-motion` vient toujours après les règles d'animation, sinon
elles l'écrasent. Et on n'anime pas en `transform` un élément qui porte déjà
un attribut `transform`, sauf si l'animation finit sur cette même valeur : le
placement va sur un groupe extérieur, l'animation sur un groupe intérieur.

**Aucun service tiers pour les statistiques.** Les instances publiques
gratuites tombent ou servent du cache, et rien ne permet alors de savoir si un
chiffre est à jour — c'est exactement ce qui s'est produit avec
`github-readme-stats`. Tout est calculé ici.

**Les cartes sont publiées sur la branche `stats`, jamais sur `main`.** GitHub
ne compte dans le graphe de contributions que les commits de la branche par
défaut et de `gh-pages`. Publier ailleurs évite qu'un commit automatique gonfle
la série. Un profil dont le message est le dépassement de soi ne peut pas
afficher une série tenue par un robot.

**Rien n'est publié si le calcul échoue.** `tools/test-stats.py` tourne avant
la génération et `build-stats.py` sort en erreur sans rien écrire si le réseau
lâche. Les cartes en ligne restent celles du dernier calcul réussi : mieux vaut
un chiffre d'il y a une heure qu'une carte vide ou fausse.

---

# Fraîcheur des chiffres

## La limite structurelle, à lire avant de rouvrir un « bug »

**Un README GitHub n'exécute rien.** Les cartes sont des images statiques. Une
image ne se rafraîchit qu'au moment où un navigateur la demande, c'est-à-dire
quand quelqu'un ouvre ou recharge la page du profil. Des chiffres qui bougent
sous les yeux d'un visiteur immobile sont impossibles — pas difficiles :
impossibles, il n'existe aucun mécanisme pour cela dans un README.

L'objectif atteignable, et celui qui est tenu, est donc : **toute visite
fraîche affiche des chiffres à quelques minutes près.** Si la page est restée
ouverte dans un onglet, l'image affichée date du moment où l'onglet a été
chargé ; c'est normal, un rechargement la met à jour.

Second point structurel : **GitHub ne notifie pas un dépôt de l'activité de son
propriétaire ailleurs.** Il n'existe aucun déclencheur « une contribution vient
d'avoir lieu ». Le seul mécanisme possible est l'interrogation régulière du
calendrier public. « Dès qu'un chiffre change » signifie donc, au mieux, « au
prochain contrôle » — d'où la période de deux minutes.

## Les couches de cache, mesurées

Mesures faites le 12 août 2026 sur ce dépôt.

| couche | valeur mesurée | maîtrisable ? |
|---|---|---|
| déclenchement planifié (`schedule`) | **écart médian 57 min, jusqu'à 90** | non — première cause, contournée |
| fraîcheur de la source lue | **grille publique gelée > 2 h**, GraphQL à jour | oui — seconde cause, corrigée |
| détection d'un changement | 120 s (période de la boucle) | oui, `PERIODE` |
| calcul des cartes + publication | ~1,5 s | oui |
| propagation sur `raw.githubusercontent.com` | de 40 s à 300 s selon le nœud de cache | non, imposé par GitHub |
| proxy d'images Camo | **absent du trajet** | sans objet |
| cache navigateur | découle du `max-age=300` ci-dessus | non |

Deux chronométrages, et il faut les lire ensemble : une publication à 09:03:35
était servie dès 09:04:12, mais une autre à 11:11 n'est apparue qu'à 11:16:39 —
soit exactement les 300 s de `max-age`. L'explication est dans l'en-tête
`x-served-by`, qui change d'une requête à l'autre : les requêtes n'atterrissent
pas sur le même nœud de cache, et chacun a son propre état. Selon celui qu'on
touche et depuis quand il a l'objet, une visite voit la nouvelle carte tout de
suite ou jusqu'à cinq minutes plus tard. C'est le plancher de GitHub, pas le
nôtre.

**Le cache-busting ne s'applique pas ici.** Non pas parce qu'il serait interdit,
mais parce qu'un README est du texte fixe : il n'existe aucun moyen d'y faire
varier une URL d'une visite à l'autre. Un `?v=` écrit dans le markdown est une
constante, donc une clé de cache constante — pas un anti-cache. Rien à gagner
de ce côté.

**Camo n'intervient pas.** C'était l'hypothèse la plus naturelle, elle est
fausse ici : dans le HTML rendu du README, les URL
`https://raw.githubusercontent.com/...` sont servies telles quelles et les
chemins relatifs deviennent `/FarddownYG/FarddownYG/raw/main/...`. Aucune URL
`camo.githubusercontent.com`. GitHub ne fait passer par Camo que les hôtes qui
ne sont pas les siens. Inutile donc de chercher à purger Camo ou à contourner
son cache : il n'est pas là.

**Première cause : le planificateur.** Le workflow demandait `*/10`, six
exécutions par heure. Sur 21 exécutions planifiées consécutives, GitHub en a
lancé une par heure. Les déclenchements `schedule` ne sont pas garantis et les
créneaux rapprochés sont abandonnés en période de charge ; le plancher
documenté de 5 minutes est une limite d'écriture, pas une promesse d'exécution.
Un cron plus serré n'y change rien — c'est la même file d'attente.

**Seconde cause : la source lue.** Une fois la cadence corrigée, le chiffre ne
bougeait toujours pas — parce qu'on interrogeait une grille périmée. Détail plus
bas, section « Le calcul lui-même ».

## Le délai obtenu, mesuré

Protocole : une vraie contribution créée à un instant connu, puis relevé de deux
étages séparément — l'arrivée sur la branche `stats` (vérité de l'origine) et
l'affichage sur une visite (CDN compris).

| instant | événement | écart depuis la contribution |
|---|---|---|
| 11:17:19 | contribution créée | — |
| 11:17:30 | publication sur la branche `stats` | +11 s |
| 11:19:34 | publication suivante, chiffre à jour | +2 min 15 s |
| 11:21:41 | **visible sur une visite fraîche** | **+4 min 22 s** |

Décomposition : la détection coûte au plus une période de boucle (120 s, ici
11 s par chance), le calcul et la publication 2 s, et le reste — un peu plus de
deux minutes ce jour-là — est le cache de `raw.githubusercontent.com`, qui
n'appartient pas à ce dépôt.

**Ordre de grandeur à retenir : deux à sept minutes**, selon l'endroit où l'on
tombe dans la période de boucle et dans le cache CDN. Avant correction, la même
mesure n'avait jamais abouti : trois contributions créées à 08h36, 08h41 et
09h05 n'apparaissaient toujours pas à 11h05.

## Comment la fraîcheur est tenue

La cadence ne vient plus du planificateur mais du run lui-même.
`tools/boucle-stats.sh` recalcule toutes les deux minutes pendant toute la
durée de vie du job, et publie sur la branche `stats` dès qu'un chiffre a bougé.

- La planification ne sert plus qu'à s'assurer qu'une boucle tourne. Une
  exécution par heure suffit à cela, ce qui tombe bien : c'est ce que GitHub
  accorde. `cancel-in-progress` fait qu'un nouveau déclenchement remplace la
  boucle en cours — c'est aussi le mécanisme de redémarrage si un run meurt.
- **La publication n'a lieu que sur changement réel.** Chaque carte porte
  l'heure de son calcul, donc deux rendus successifs diffèrent toujours ;
  `tools/empreinte.py` compare les cartes privées du groupe `<g id="maj">`
  (l'horodatage) et du bloc `<defs id="glyphes">` (les contours des caractères
  employés, donc aussi ceux des chiffres de l'heure). Sans cela la branche
  serait réécrite toutes les deux minutes pour rien.
- **Un battement horaire republie même sans changement**, pour que
  l'horodatage affiché sur les cartes prouve que la chaîne est vivante. Une
  carte figée depuis deux jours se voit ainsi immédiatement.
- **Les années de contributions déjà closes sont mises en cache** dans
  l'espace de travail du job, sinon chaque tour rejouerait quatre ans de
  lectures. Le cache est jeté à chaque redémarrage du job, donc rafraîchi au
  moins une fois par heure — ce qui rattrape d'éventuels commits antidatés.
  **L'année en cours n'est jamais mise en cache** : ce serait figer précisément
  le chiffre du jour, c'est-à-dire recréer le défaut qu'on vient de corriger.

Réglages, par variables d'environnement dans `tools/boucle-stats.sh` :
`PERIODE` (120 s entre deux recalculs), `BUDGET` (19 800 s, la limite dure d'un
job GitHub étant de 6 h), `BATTEMENT` (3 600 s).

## Le coût, assumé

Un job reste vivant en permanence au lieu de démarrer quinze secondes par
heure. C'est le prix de la fraîcheur : sans cela, la cadence dépendrait d'un
planificateur qui accorde une exécution par heure. Les minutes Actions sont
gratuites et illimitées sur les dépôts publics, et le travail produit est bien
la publication de ce dépôt.

Le volume d'appels vers GitHub reste modeste : trois requêtes par tour, soit
environ 90 par heure, contre une limite de 1 000 par heure et par dépôt. C'est
le cache des années closes qui maintient ce chiffre bas.

Si ce coût devenait un problème, deux leviers dans cet ordre : augmenter
`PERIODE` (300 s garde une fraîcheur largement suffisante), puis, seulement si
nécessaire, déplacer la génération vers une fonction serverless qui rend la
carte à la demande. Cette dernière option donne la meilleure fraîcheur par unité
de calcul, mais réintroduit exactement la dépendance externe qu'on a éliminée —
un service qui tombe, et le profil affiche des images cassées.

## Quoi vérifier si un chiffre paraît figé

1. **L'horodatage sur la carte elle-même.** Il donne l'heure du calcul. S'il
   est récent, les chiffres le sont aussi, et ce qui coince est en aval
   (navigateur, cache local) : recharger en forçant.
2. **La dernière exécution du workflow.** Onglet Actions. Si aucune boucle ne
   tourne, la relancer à la main (`workflow_dispatch`).
3. **Le journal du run.** Il imprime à chaque tour les dernières journées lues,
   les totaux calculés, et surtout **la valeur vue par chacune des deux
   sources** :

   ```
   2026 : 1 jour(s) où GraphQL (UTC) diffère de la grille du profil (fuseau)
          — 2026-08-12 grille=81 GraphQL=93
   2026 : totaux par source — grille=1706 GraphQL=1718
   ```

   C'est la ligne qui dit si un chiffre manque parce qu'on ne regarde pas assez
   souvent, ou parce que GitHub n'a pas encore publié le sien. Elle a servi
   exactement à cela.
4. **Les cinq minutes de `max-age`.** Deux visites à moins de cinq minutes
   d'intervalle peuvent afficher la même image. C'est le comportement attendu.

## Le calcul lui-même

Deux sources, dans cet ordre :

- **la grille publique du profil** (`github.com/users/<login>/contributions`),
  sans authentification. C'est exactement ce que GitHub affiche, datée dans le
  fuseau du compte ;
- **GraphQL `contributionsCollection`**, authentifié. Il découpe les journées en
  UTC, ce qui peut décaler une contribution d'un jour.

Les deux sont lues à chaque tour, puis départagées en deux temps :

1. **Garde-fou.** Un décalage de fuseau déplace quelques contributions, il ne
   change pas un total. Un écart de plus de 25 % dénonce une lecture cassée et
   fait retenir GraphQL sans discussion.
2. **La source la plus avancée gagne.** L'écart étant modéré, il ne peut venir
   que d'un retard de publication : le total le plus élevé désigne la source à
   jour. À égalité on garde la grille, qui date les journées dans le fuseau du
   compte, exactement comme le graphe du profil. Les journées que GraphQL ne
   couvre pas encore — le lendemain de l'UTC, déjà commencé dans le fuseau du
   compte — gardent la valeur de la grille.

Trois pannes déjà survenues, toutes couvertes par un test :

- **un parseur trop permissif** cherchait le nombre n'importe où dans
  l'infobulle et lisait le quantième dans « No contributions on July 11th ».
  Toutes les journées vides devenaient actives : total doublé, série continue
  depuis janvier. Le nombre est désormais ancré en tête de l'infobulle ;
- **la journée en avance sur l'UTC était jetée.** Le runner vit en UTC, la
  grille du profil est datée dans le fuseau du compte : à 23 h UTC elle
  contient déjà le lendemain parisien. Le filtre final coupait à « aujourd'hui
  en UTC » et supprimait cette journée juste après être allé la chercher — la
  série affichait 30 au lieu de 31. La limite tolère maintenant un jour
  au-delà, ce qui couvre n'importe quel fuseau de UTC-12 à UTC+14 ;
- **la grille publique de GitHub gelait sur la journée en cours.** Le 12 août,
  elle a servi 81 contributions pendant plus de deux heures — total 1 706 —
  pendant que GraphQL en comptait 93, total 1 718, l'écart portant entièrement
  sur la journée du jour. Trois contributions créées pour tester n'apparaissaient
  donc jamais, alors que la boucle recalculait bien toutes les deux minutes. Ce
  n'était pas une question de cadence : on interrogeait une source périmée.
  D'où la règle « la source la plus avancée gagne ».

## Le skyline

La carte principale est un portage de
[Contribution Skyline](https://21st.dev/@kedhareswer/components/contribution-skyline),
un composant React dessiné sur canvas. **Il ne peut pas être intégré tel quel** :
un README n'exécute aucun JavaScript, et copier le composant dans le dépôt ne
produirait que du code mort que rien n'affiche. Le coller dans `components/ui/`
comme le propose 21st.dev n'a de sens que dans une application React — un site,
pas un profil.

Ce qui a été repris, recalculé en Python dans `carte_skyline()` : la même
caméra (lacet 45°, élévation 34°), le même ordre de peinture, les trois faces
ombrées (dessus, gauche ×0,84, droite ×0,68), les niveaux aux quarts du 95e
centile, les quatre chiffres dans les coins que la diagonale laisse vides, et la
montée des barres en vague du plus ancien au plus récent.

Ce qui a été abandonné, faute de JavaScript : la rotation à la souris, le
survol d'une journée, la bascule 2D/3D, la mise en valeur d'un niveau au
survol de la légende.

Écarts voulus avec l'original :

- **Hauteurs en racine carrée**, pas en puissance 0,85. Avec un record à 322,
  l'échelle d'origine réduit une journée ordinaire à 12 % de la tour record ;
  la racine la garde à 26 %. Un test le verrouille.
- **Palette or du profil**, pas le vert GitHub.
- **Animation en CSS, pas en SMIL.** Les valeurs propres à chaque barre passent
  par des variables (`--h`, `--d`, `--t`). Chaque face latérale est un
  rectangle unité cisaillé (`skewY(±29,2°)`) dont seule la hauteur s'anime, et
  chaque élément garde sa géométrie finale en attribut. En SMIL il aurait fallu
  une jumelle immobile par barre, soit plus du triple du poids.
- **Les journées vides sont une seule dalle** réutilisée par `<use>`.
- **Sur mobile, la scène et les chiffres se séparent** : la ville en haut, les
  quatre chiffres dessous, sur deux colonnes. Sur bureau ils occupent les deux
  coins que la diagonale laisse vides, et le cadrage leur réserve cette place
  (un test y promène un record à cinq chiffres).

Le record du jour, la plus longue série et la série actuelle vivent dans le
skyline ; le tableau de bord montre le reste, pour n'afficher aucun chiffre
deux fois — à l'exception du total, qui a son compteur.

## Le tableau de bord

Les records présentés comme les compteurs d'une voiture (`carte_bord()`) : deux
grands cadrans à aiguille — meilleure semaine sur sept jours glissants,
meilleur mois —, un compteur à rouleaux pour le total, un totalisateur pour les
trente derniers jours, deux petits cadrans annulaires (part de jours actifs,
moyenne par jour actif). À l'ouverture les aiguilles balaient toute l'échelle
avant de se poser, comme le contrôle d'allumage d'un vrai tableau de bord.

- **L'échelle d'un cadran est calculée**, pas fixée : `_echelle()` choisit un
  pas rond (1, 2 ou 5 fois une puissance de dix) et de cinq à dix intervalles,
  pour que l'aiguille se pose vers les trois quarts de la course. Un test
  balaie les valeurs : avec six intervalles pour plancher, une semaine à 182
  ne trouvait aucune graduation et l'aiguille pointait n'importe où.
- **Deux façons de chiffrer l'échelle.** Le cadran de la meilleure semaine
  porte toujours le chiffre de tête et un multiplicateur (« × 10 », « × 100 »…),
  comme un compte-tours. Celui du meilleur mois porte les nombres entiers
  (0, 200, 400…) comme un compteur de vitesse, et passe au même système dès
  que son maximum atteint 10 000.
- **Les chiffres reculent de leur propre largeur.** Posés à distance fixe de
  leur graduation, « 200 » à 9 h et « 1000 » à 3 h la touchaient, et « —200 »
  se lisait « −200 ».
- **Le compteur ne tronque jamais** : un total plus long que prévu reçoit les
  rouleaux qu'il lui faut, qui rétrécissent pour tenir. Un compteur qui perd
  son chiffre de tête affiche un nombre faux ; un test le verrouille.
- **Les valeurs s'ajustent à leur place** : dans un cadran ou un anneau, le
  corps du chiffre diminue quand le nombre s'allonge, et la valeur d'un cadran
  s'arrête avant les chiffres de l'échelle qui sont à sa hauteur. La période
  inscrite sous la meilleure semaine rétrécit de même quand elle porte une
  année.

## Le système de design

Nom de code « carte noire » : noir chaud, crème, or, et un rouge vermillon —
celui des cœurs et des carreaux — réservé aux aiguilles, aux feux de la GT-R et
à la flamme de la série en cours. Les deux palettes (`SOMBRE`, `CLAIR`) vivent
dans `tools/dessin.py`, avec la feuille SVG (`Feuille`), le cadre commun
(`cadre()`) et les motifs.

**Le texte est dessiné, pas écrit.** Un `<img>` ne charge aucune police : un
`<text>` retomberait sur celle de l'appareil, avec des largeurs imprévisibles.
`tools/typo.py` compose donc chaque ligne en tracés, à partir de
`tools/glyphes.json` — contours, chasses, paires de crénage et ligatures de
Playfair Display (titres, texte, italique) et de JetBrains Mono. Chaque glyphe
employé est défini une fois dans `<defs id="glyphes">` puis rappelé par
`<use>`. Deux conséquences : le rendu est identique partout, et la largeur
d'un texte est connue au dixième de pixel avant de le poser, ce qui permet de
caler une mise en page sans marge de sécurité. Un caractère absent de l'atlas
lève une erreur plutôt que de laisser un blanc.

Pour ajouter un caractère ou une graisse : compléter `build-glyphes.py`, le
relancer sur les fichiers `.woff2` des deux familles (paquets
`@fontsource/playfair-display` et `@fontsource/jetbrains-mono`), et valider le
nouvel atlas. C'est un outil de développement (fonttools, brotli, uharfbuzz) ;
la CI ne lit que le JSON. Licences : `tools/POLICES.md`.

**Quatre versions de chaque image.** Bureau (dessin large de 900) ou mobile
(dessin large de 450, plus haut, recomposé et non rétréci), en sombre et en
clair. Le README les choisit par `<picture>` :

```html
<source media="(min-width: 1012px) and (prefers-color-scheme: dark)" srcset="…-dark.svg">
<source media="(min-width: 1012px) and (prefers-color-scheme: light)" srcset="…-light.svg">
<source media="(prefers-color-scheme: dark)" srcset="…-m-dark.svg">
<source media="(prefers-color-scheme: light)" srcset="…-m-light.svg">
```

1012 px est le seuil où GitHub passe la page de profil en pleine largeur ; en
dessous, la colonne du README fait entre 300 et 580 px et c'est la version
mobile qui est lisible. **Ce sont les sources « bureau » qui portent la
condition de largeur, et l'ordre compte.** Si la condition de largeur venait à
être ignorée — par exemple par un script qui réécrirait les requêtes de thème
quand le visiteur force un thème sur GitHub —, la première source du bon thème
l'emporterait : la version bureau, c'est-à-dire ce qu'affiche n'importe quel
profil. Dans l'ordre inverse, c'est une mise en page mobile qui s'étirerait
sur un grand écran. Ce comportement de GitHub n'a pas pu être observé d'ici ;
l'ordre a été choisi pour que l'échec éventuel soit bénin.

## L'as de pique

`tools/build-embleme.py` dessine l'emblème comme un orfèvre monte un
filigrane :

1. **le pourtour** — cordon, rang de perles, liseré — suit la silhouette à
   distance constante : ce sont des courbes de niveau d'un champ de distance ;
2. **l'ossature** — axe, médaillon, grandes volutes en C, crosses de la pointe
   et du pied — est posée à la main ;
3. **la dentelle** est un empilement glouton : à chaque tour, le plus grand
   cercle qui tient encore dans le vide restant reçoit une spirale qui part de
   son point de contact, comme une vrille naît d'une tige. Les interstices
   reçoivent des œillets, puis des grains.

Seule la moitié gauche est calculée et stockée ; la droite est son miroir,
obtenu par `<use>`. Le résultat (`tools/embleme.json`, une soixantaine de
kilo-octets) est découpé en couches — pourtour, ossature, puis huit rangs de
dentelle du cœur vers les bords — que `dessin.embleme()` pose dans une feuille.
Le héros s'en sert pour monter le filigrane dans cet ordre, puis faire
scintiller les grains d'or.

Régénérer : `python3 tools/build-embleme.py > tools/embleme.json` (numpy), puis
`python3 tools/build-assets.py assets`.

## Le garage

La Skyline GT-R R32 est dessinée à partir de ses cotes réelles (longueur
4 545 mm, largeur 1 755, hauteur 1 340, empattement 2 615) : le profil est une
liste de points en millimètres, reliés par une spline (`dessin.lisse()`). Aucun
logo de marque — le nom en toutes lettres suffit.

## Les images fixes et l'avatar

`python3 tools/build-assets.py assets` réécrit le héros, le garage, la
signature et `avatar.svg`. L'avatar PNG se rend ensuite dans un navigateur sans
tête, à 1024 px, puis s'enregistre avec Pillow en `optimize=True` : GitHub
refuse au-delà d'un mégaoctet.

**Un dépôt ne peut pas changer la photo de profil.** Elle se téléverse à la
main sur github.com/settings/profile : PNG ou JPG, opaque, recadrée en disque.
L'emblème est cadré pour ce recadrage.

## À savoir sur le rendu SVG

- **Une image hors de l'écran n'avance pas.** Chromium suspend les animations
  d'un SVG chargé en `<img>` tant qu'il n'est pas visible : l'entrée d'une
  carte se joue quand le visiteur arrive dessus en faisant défiler, pas au
  chargement de la page. Corollaire pour les captures : une capture « pleine
  page » montre les images du bas à leur première image.
- **`prefers-reduced-motion` atteint bien les images.** L'émulation de
  Playwright (`reducedMotion`) ne se transmet pas aux documents chargés en
  `<img>`, mais le réglage du système, si : lancer Chromium avec
  `--force-prefers-reduced-motion` affiche chaque image dans son état final.
  C'est ainsi que la page entière a été vérifiée.
- **Un `<use>` hérite de `color`.** Les couches de l'emblème sont peintes en
  `currentColor` ; la couleur se choisit sur le `<use>` qui les rappelle.
- Les identifiants des glyphes dérivent de la police et du caractère, pas de
  l'ordre d'écriture : deux rendus du même texte donnent le même fichier.
- Playfair Display n'a pas de chiffres tabulaires. Les rouleaux du compteur
  centrent donc chaque chiffre dans sa case (`_compteur()`) ; `typo` sait faire
  de même pour un texte courant (`tab=True`), sans appelant aujourd'hui.
- En français le premier du mois s'écrit « 1er » : `dessin.quantieme()`, dont
  se servent l'horodatage et toutes les dates des cartes.
