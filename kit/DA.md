# Direction artistique Amadeus

Thème : géopolitique et actualité expliquées par l'histoire (un événement récent + ses causes passées), ton objectif et sourcé.

## Style : tableau d'histoire
Esthétique de peinture et de photographie ancienne : vraies images liées au sujet, passées en rendu peinture à l'huile légère (touches de pinceau, ombres brunes, lumières dorées, grain de toile), cartes au style carte ancienne, cadres dorés de musée. Le flash-back historique passe en sépia. Réaliste, jamais abstrait : on doit reconnaître ce qu'on voit.

## Images : vraies, précises, nombreuses
- **Au moins 25 visuels différents** par vidéo (cartes et drapeaux compris), chacun utilisé **au plus 2 fois**.
- Chaque plan montre ce que dit la voix à ce moment : le lieu, le navire, la personne, l'événement, la date. Une recherche par fait du script et par nom propre, jamais de recherche vague.
- Sources, dans cet ordre de préférence (outil `outils/medias.py`) :
  1. **Cartes exactes** générées avec `outils/cartes.py` (Natural Earth : vraies côtes et frontières) : le lieu en gros plan, la région, le pays surligné, les routes. 5 à 8 cartes par vidéo, à des échelles différentes.
  2. **Bibliothèque du Congrès** (`loc`) : photos historiques (révolutions, guerres, dirigeants, foules).
  3. **NASA** (`nasa`) : le lieu vu de l'espace, villes de nuit, reliefs.
  4. **Art Institute of Chicago** (`aic`) : tableaux et gravures anciennes du domaine public pour l'histoire longue.
  5. **Openverse** (`openverse`) : photos modernes génériques (pétroliers, ports, villes, armées).
  6. **Pexels** (`pexels`) si une clé est configurée.
  7. **Drapeaux officiels** (`drapeau`, flag-icons) : jamais dessinés à la main.
- Tri obligatoire : `medias.py planche` puis regarder la planche et **éliminer** toute image hors sujet, floue, trop sombre, anachronique (ex. un croiseur de 1940 pour un événement de 1988) ou montrant une scène violente réaliste.
- Rendu : `medias.py peinture` sur chaque photo ; `--doux` pour les gravures, tableaux et cartes anciennes (étalonnage seul).
- Portraits de personnes réelles : uniquement des photos libres de droits (domaine public, CC0, CC BY, CC BY-SA, « no known restrictions »), créditées.

## Mise en page
- `plein` : image plein écran recadrée en 9:16 (photos verticales ou carrées, cartes, vues NASA en haute résolution). Ne jamais recadrer à moins de 55 % de la hauteur d'une image de moins de 1 500 px (sinon pixels visibles).
- `cadre` : image paysage **entière** dans un cadre doré de musée, sur fond flou de la même image. C'est le choix par défaut pour les photos et tableaux horizontaux.
- Drapeaux qui flottent sur fond flou ; face-à-face de deux drapeaux pour les points de vue opposés.
- Fonds de chiffres : image du plan précédent floutée et teintée rouge sang (`fondRouge`).

## Palette et typographie
- Palette : or #E5B547, or foncé #A07828, crème #F0E8D6, rouge #D62C30, gris #78746C ; ombres brunes, lumières dorées.
- Sous-titres en Archivo Black majuscules, blancs avec contour noir, mot par mot ; mots clés en or ou en rouge, soulignés.
- Gros chiffres et dates en Abril Fatface, tremblement et flash chaud à l'apparition.
- Titres en DM Serif Display or. Petites mentions en Space Mono.
- Habillage : grain de toile sur toute l'image, vignette brune, fin cadre doré, particules dorées discrètes, tampons inclinés rouges (« FERMÉ », « PAR ERREUR », « AUCUN ACCORD »).

## Rythme et animation
- **Un plan toutes les 0,9 à 1,5 s** (moyenne visée : 1,1 s ; jamais plus de 2 s).
- Chaque plan pousse nettement dans l'image (Ken Burns), avec de légères dérives latérales.
- Zoom-punch de toute l'image sur chaque mot clé (automatique avec les mots de `cles.json`).
- Transitions variées en alternance sur 4 images : zoom traversant, whip flou, flash chaud, passage au noir, glissé de page.
- Effet REWIND (bandes VHS + sépia) pour entrer dans le passé.

## Son
- Musique : un morceau libre trouvé avec `medias.py musique` (Openverse/Jamendo, CC BY ou CC0, jamais généré par IA), style bande-annonce ou cinématique, adapté au ton du sujet. Crédit obligatoire dans la caption. Volume musique 0,85 (paramètre par défaut de `mixage.py`), baissée sous la voix par sidechain. Si aucune musique n'est trouvée : musique générée par `outils/sons.py`.
- Bruitages discrets et variés (`outils/sons.py`) : `transition` sur environ une coupe sur deux (tire au hasard whoosh, page, déclic, souffle), `boom` sur les gros chiffres, `tic` avant les dates, `riser` avant les révélations et le REWIND. Jamais le même son à chaque coupe.

## Boîte à outils (plans.js, voir outils/assembler.py)
Chaque ligne : `plan(t0,(lt,u,t)=>{ ... });` avec `lt` = temps depuis le début du plan, `u` = avancement 0→1.
`plein(nom,u,[cx,cy,h],[cx,cy,h])`, `cadre(nom,u,y)`, `drapeau(code,x,y,largeur,t)`, `fondRouge(nom)`, `fondDrapeau(nom)`,
`grosChiffre(txt,lt,y,taille,coul,sous)`, `titre(txt,lt,y)`, `mot(txt,lt,y,taille,coul)`, `tampon(txt,lt,x,y,coul,rot)`,
`mention(txt,y,coul)`, `sepiaTon(a)`, `avion(x,y,s)`, `missile(x0,y0,x1,y1,lt)`, `eclat(x,y,lt)` ; option `{rewind:true}`.
Exemple de référence complet (58 plans, Ormuz) : `kit/exemples/plans_ormuz.js` et `kit/exemples/cles_ormuz.json`. Les noms d’images y sont ceux du test (c_ormuz = carte, n_… = NASA, drapeau(ir) = drapeau_ir.svg).
