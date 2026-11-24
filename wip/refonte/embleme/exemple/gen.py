# Exemple minimal du contrat : silhouette pleine, liseré intérieur, perle d'or.
S = open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "outils", "silhouette.txt")).read().strip()
print('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200">')
print('<g data-ordre="0"><path d="%s" fill="none" stroke="currentColor" stroke-width="14" stroke-linejoin="round"/></g>' % S)
print('<g data-ordre="1"><path d="%s" fill="none" stroke="currentColor" stroke-width="3" transform="translate(500 640) scale(0.86) translate(-500 -640)"/></g>' % S)
print('<g data-ordre="2" class="or"><circle cx="500" cy="640" r="26" fill="currentColor"/></g>')
print('</svg>')
