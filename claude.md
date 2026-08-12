# Notes de conception

Dépôt de profil (`FarddownYG/FarddownYG`) : le README affiché sur la page
GitHub de Yanis. Thème as de pique, public mixte développeurs et recruteurs.

## Ce qu'il y a dedans

| | |
|---|---|
| `README.md` | la page du profil |
| `assets/header-*.svg`, `assets/divider-*.svg` | bannière animée et séparateur, deux thèmes |
| `tools/build-header.py` | génère la bannière (les deux thèmes depuis une seule source) |
| `tools/build-stats.py` | calcule les statistiques et rend les trois cartes |
| `tools/empreinte.py` | empreinte des cartes hors horodatage, pour ne publier que sur changement |
| `tools/boucle-stats.sh` | recalcule en boucle et publie |
| `tools/test-stats.py` | vérifications, exécutées avant toute publication |
| `.github/workflows/records.yml` | fait tourner la boucle |
| branche `stats` | les six cartes publiées (orpheline, réécrite à chaque publication) |

## Règles qui ne se négocient pas

**Aucun JavaScript.** GitHub nettoie le markdown des README : `<script>` est
retiré, les images sont rendues en `<img>`, donc sans interactivité ni
scripting. Toute animation passe par du SVG pur — SMIL (`<animate>`,
`<animateTransform>`) et CSS en ligne. Rien d'autre ne tient.

**Aucune ressource externe.** Les SVG ne chargent ni police ni image distante :
un `<img>` ne suit pas ces requêtes. Tout est vectorisé ou dessiné.

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
| déclenchement planifié (`schedule`) | **écart médian 57 min, jusqu'à 90** | non — c'était la cause |
| calcul + publication | 14 s | oui |
| `raw.githubusercontent.com` | `cache-control: max-age=300` (5 min) | non, imposé par GitHub |
| proxy d'images Camo | **absent du trajet** | sans objet |
| cache navigateur | découle du `max-age=300` ci-dessus | non |

**Camo n'intervient pas.** C'était l'hypothèse la plus naturelle, elle est
fausse ici : dans le HTML rendu du README, les URL
`https://raw.githubusercontent.com/...` sont servies telles quelles et les
chemins relatifs deviennent `/FarddownYG/FarddownYG/raw/main/...`. Aucune URL
`camo.githubusercontent.com`. GitHub ne fait passer par Camo que les hôtes qui
ne sont pas les siens. Inutile donc de chercher à purger Camo ou à contourner
son cache : il n'est pas là.

**La cause était le planificateur.** Le workflow demandait `*/10`, six
exécutions par heure. Sur 21 exécutions planifiées consécutives, GitHub en a
lancé une par heure. Les déclenchements `schedule` ne sont pas garantis et les
créneaux rapprochés sont abandonnés en période de charge ; le plancher
documenté de 5 minutes est une limite d'écriture, pas une promesse d'exécution.
Un cron plus serré n'y change rien — c'est la même file d'attente.

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
  `tools/empreinte.py` compare les cartes privées de cette ligne. Sans cela la
  branche serait réécrite toutes les deux minutes pour rien.
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
3. **Le journal du run.** Il imprime à chaque tour les dernières journées lues
   et les totaux calculés, ainsi que les écarts entre les deux sources. Un
   chiffre faux se diagnostique là, sans deviner.
4. **Les cinq minutes de `max-age`.** Deux visites à moins de cinq minutes
   d'intervalle peuvent afficher la même image. C'est le comportement attendu.

## Le calcul lui-même

Deux sources, dans cet ordre :

- **la grille publique du profil** (`github.com/users/<login>/contributions`),
  sans authentification. C'est exactement ce que GitHub affiche, datée dans le
  fuseau du compte ;
- **GraphQL `contributionsCollection`**, en filet. Il découpe les journées en
  UTC, ce qui peut décaler une contribution d'un jour et casser une série : à
  n'utiliser que si la première source échoue ou paraît aberrante.

Un garde-fou compare les deux : un décalage de fuseau déplace quelques
contributions, il ne change pas un total. Un écart de plus de 25 % dénonce une
lecture cassée et fait retenir GraphQL.

Deux pannes déjà survenues, toutes deux couvertes par un test :

- **un parseur trop permissif** cherchait le nombre n'importe où dans
  l'infobulle et lisait le quantième dans « No contributions on July 11th ».
  Toutes les journées vides devenaient actives : total doublé, série continue
  depuis janvier. Le nombre est désormais ancré en tête de l'infobulle ;
- **la journée en avance sur l'UTC était jetée.** Le runner vit en UTC, la
  grille du profil est datée dans le fuseau du compte : à 23 h UTC elle
  contient déjà le lendemain parisien. Le filtre final coupait à « aujourd'hui
  en UTC » et supprimait cette journée juste après être allé la chercher — la
  série affichait 30 au lieu de 31. La limite tolère maintenant un jour
  au-delà, ce qui couvre n'importe quel fuseau de UTC-12 à UTC+14.

## À savoir sur le rendu SVG

- `textLength` avec `lengthAdjust="spacingAndGlyphs"` fixe la largeur d'un
  texte sans police embarquée. WebKit répartit mal `textLength` entre des
  `<tspan>` : découper en `<text>` frères.
- `calcMode="discrete"` : les `keyTimes` doivent commencer à 0 ; en linéaire ou
  spline la dernière valeur doit atteindre 1. Firefox ignore silencieusement
  des `keyTimes` invalides.
- SVG supprime les espaces en fin de `<text>` : deux segments de couleurs
  différentes ont besoin d'un `x` explicite, sinon ils se collent.
- `prefers-reduced-motion` ne peut être traité qu'en CSS ; SMIL ne répond pas
  aux media queries. On neutralise la géométrie avec `!important` et
  `display:none`.
- Les avatars GitHub n'acceptent pas le SVG : PNG ou JPG, opaque, 1 Mo maximum,
  recadré en cercle, et cela se règle sur github.com/settings/profile — un
  dépôt ne peut pas le faire.
