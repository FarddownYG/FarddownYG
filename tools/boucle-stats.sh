#!/usr/bin/env bash
# Recalcule les cartes en continu et les publie dès qu'un chiffre change.
#
# Pourquoi une boucle et non un cron serré. Le workflow demandait « */10 »,
# soit six exécutions par heure. Mesuré sur 21 exécutions planifiées : GitHub
# en a lancé une par heure (écart médian 57 min, jusqu'à 90). Les
# déclenchements planifiés ne sont pas garantis, et GitHub abandonne les
# créneaux rapprochés en période de charge — c'était là toute la latence
# constatée sur le profil. La fraîcheur ne peut donc pas venir du
# planificateur : elle vient de ce que l'exécution, une fois lancée, reste
# vivante et se recalcule elle-même.
#
# Réglages (surchargeables par l'environnement) :
#   PERIODE    secondes entre deux recalculs
#   BUDGET     durée de vie du run ; la limite dure d'un job GitHub est de 6 h
#   BATTEMENT  publication forcée même sans changement, pour que l'horodatage
#              affiché sur les cartes prouve que la chaîne est vivante
set -euo pipefail

PERIODE=${PERIODE:-120}
BUDGET=${BUDGET:-19800}     # 5 h 30
BATTEMENT=${BATTEMENT:-3600}

export CACHE_ANNEES="${CACHE_ANNEES:-$PWD/.cache-annees}"

depart=$(date +%s)
empreinte=""
publie=0

# Une publication ratée ne doit jamais tuer la boucle : le run mourrait, et la
# fraîcheur retomberait sur la planification — c'est-à-dire sur le défaut qu'on
# vient de corriger. On réessaie, puis on rend la main à la boucle, qui
# retentera au tour suivant puisque l'empreinte publiée n'aura pas bougé.
publier() {
  local essai
  for essai in 1 2 3; do
    rm -rf out/.git
    if (
      cd out
      git init -q -b stats
      git config user.name "github-actions[bot]"
      git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
      git add -A
      git commit -q -m "Statistiques au $(date -u '+%Y-%m-%d %H:%M UTC')"
      git push -q --force \
        "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" \
        stats:refs/heads/stats
    ); then
      return 0
    fi
    echo "== publication en échec (essai $essai/3)"
    sleep 10
  done
  return 1
}

while :; do
  maintenant=$(date +%s)
  reste=$(( BUDGET - (maintenant - depart) ))
  if [ "$reste" -le 0 ]; then
    echo "== budget de $BUDGET s épuisé, fin du run (la planification en relancera un)"
    break
  fi

  rm -rf out
  if ! python tools/build-stats.py out; then
    # Rien n'est publié : les cartes en ligne restent celles du dernier calcul
    # réussi. Mieux vaut un chiffre d'il y a dix minutes qu'une carte vide.
    echo "== calcul en échec, cartes en ligne inchangées, nouvel essai dans ${PERIODE}s"
    sleep "$PERIODE"
    continue
  fi

  if ! nouvelle=$(python tools/empreinte.py out); then
    echo "== empreinte illisible, on republie par prudence"
    nouvelle="?"
  fi

  if [ "$nouvelle" = "$empreinte" ] && [ $(( maintenant - publie )) -lt "$BATTEMENT" ]; then
    echo "== aucun chiffre modifié ($nouvelle), prochain contrôle dans ${PERIODE}s"
  elif publier; then
    [ "$nouvelle" = "$empreinte" ] \
      && echo "== battement : republication pour rafraîchir l'horodatage" \
      || echo "== chiffres modifiés ($empreinte -> $nouvelle), publié"
    empreinte=$nouvelle
    publie=$maintenant
  else
    echo "== publication impossible, empreinte inchangée : nouvel essai au tour suivant"
  fi

  sleep "$(( PERIODE < reste ? PERIODE : reste ))"
done
