# Refonte du profil — notes de reprise

Travail interrompu volontairement le 24 nov. 2026 vers 23h UTC (crédits épuisés),
à reprendre automatiquement. Ce dossier `wip/` vit sur la branche de travail
uniquement : **il ne doit pas arriver sur `main`**.

## La demande

« Refais mon profil, montre-moi ce dont tu es capable. » Refonte complète, en
gardant le fond déjà validé par Yanis, et avec deux exigences ajoutées en cours
de route :

1. **Garder la GT-R R32** (sa voiture de rêve), en version nettement améliorée —
   une vraie illustration soignée, plus le petit filaire actuel du séparateur.
   Toujours sans logo de marque.
2. **De belles stats** : très graphiques, « sexy », ultra agréables à regarder,
   faites pour flex.

Fond à conserver (décisions antérieures de Yanis) :
- thème as de pique = dépassement de soi ; bio courte « Pourquoi l'as de pique ? » ;
- ingénieur cybersécurité, fondateur de Classor (lien classor.fr), dev de jeux,
  logiciels, outils ; « depuis toujours : coder des outils, en vivre » ;
- credo : « celui qui tire doit être prêt à recevoir la balle » — Lelouch, Code Geass ;
- flamme pour la série en cours ; record en une journée ; le skyline (demandé
  explicitement) ; stats toujours à jour, sans intervention ;
- **l'as de pique en filigrane orné, crème sur noir chaud** : demandé il y a
  des mois (« voilà celle que je veux »), jamais livré. L'image de référence est
  perdue ; première tentative jugée « trop aérée ».
- fusion sur `main` autorisée sans demander.

Inaccessibles depuis la session : classor.fr et le pin Pinterest (proxy). Ne
rien inventer sur ce que fait Classor.

## État en ligne au moment de l'arrêt

Sain. `main` = 13aca97. La boucle de stats tourne (3 984 contributions, record
338, mise à jour toutes les 2 min). Rien de cette refonte n'est publié.

## Décisions de design prises

**Système « carte noire »** — noir chaud, crème, or.
- sombre : fond `#100E0B`, encre crème `#EFE4CB`, or `#D2AE6D`, discret `#8C8372`, filet `#2A251D`
- clair : papier `#F6EFE0`, encre `#1B1712`, or `#9A7430`

**Typographie réelle, convertie en tracés** (plus de `<text>` dépendant des
polices du téléphone : aujourd'hui un iPhone retombe sur Courier).
- Playfair Display : 800 pour le nom et les grands chiffres, 500 italique pour
  le credo, 600 pour les libellés ; JetBrains Mono 400/500 pour la voix « code ».
- Polices OFL, récupérées par npm : `npm pack @fontsource/playfair-display
  @fontsource/jetbrains-mono` (fichiers `files/*-latin-<graisse>-<style>.woff2`).
- `outils/typo.py` : HarfBuzz (mise en forme, `tnum`/`lnum`) + fontTools
  (contours) → `d` SVG + largeur exacte. Dépendances de dev :
  `pip install fonttools brotli uharfbuzz` (et `pip install --ignore-installed pillow`).
- À faire : un **atlas de glyphes JSON** commité (contours, chasses, paires de
  crénage) pour que `tools/build-stats.py` compose le texte en pur Python dans
  la CI, sans dépendance, avec des largeurs exactes (fin de la table `CHASSE`).

**Structure visée du README**
1. Héros : carte as de pique (emblème en filigrane, liseré or, indices A♠),
   « YANIS », rôle, credo. Entrée animée une fois (tracé de la gravure, reflet
   d'or), puis calme. Mise en page adaptée aux petites largeurs par media
   queries internes au SVG (largeur rendue) ; tester aussi si GitHub conserve
   `<source media="(max-width: …)">` dans `<picture>`.
2. Bio courte en texte (inchangée).
3. Skyline restylé au nouveau système.
4. « Carré d'as » : les records présentés comme des cartes à jouer, chiffres en
   Playfair, compteurs qui défilent (bandes de chiffres translatées sous un
   clipPath). Idée bonus : clin d'œil « Skyline » = la R32 garée au pied du skyline.
5. La GT-R R32, en grande illustration.
6. Signature / pied de page ; avatar PNG assorti à l'emblème (à téléverser à la main).

**Règles inchangées** : zéro JavaScript, aucune ressource externe, état final
porté par les attributs (l'animation part d'ailleurs et y revient),
`prefers-reduced-motion` respecté, chaque carte peint son propre fond, cartes
de stats publiées sur la branche `stats`, tests avant publication, empreinte de
référence à régénérer, publication en deux temps (cartes d'abord, README ensuite).

## Le concours de l'emblème

Workflow multi-agents lancé puis **arrêté au bout de quelques minutes** : quatre
stratégies de construction en parallèle, deux jurés, polissage du gagnant.
- Script : `embleme/concours-embleme.workflow.js` (à relancer tel quel ; les
  chemins pointent vers le brouillon de la session — recopier `embleme/` et
  `outils/shoot.js` dans le scratchpad d'abord, `shoot.js` à sa racine).
- Contrat et vérificateur : `embleme/outils/apercu.py` (aperçus sombre / clair /
  planche de tailles, couverture d'encre, débord, symétrie).
- Silhouette de référence : `embleme/outils/silhouette.txt`.
- Les dossiers `A-rinceaux`, `B-croissance`, `C-gravure`, `D-reserve` contiennent
  ce que chaque agent avait écrit à l'arrêt (peut être vide ou partiel).

## Étapes restantes

1. Relancer le concours de l'emblème (ou le terminer à partir des ébauches).
2. Atlas de glyphes + bascule de `build-stats.py` sur les tracés.
3. Héros, R32, carré d'as, skyline restylé, pied de page, avatar.
4. Aperçu fidèle : HTML rendu par GitHub + `github-markdown-css`, bureau et
   mobile, deux thèmes.
5. Relecture adverse multi-agents, corrections, tests.
6. Publication : PR, fusion, vérification en ligne ; retirer `wip/` avant.
7. `claude.md` : système de design, typographie, licences des polices.
