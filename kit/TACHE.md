# Tâche quotidienne Amadeus

Produire une vidéo verticale (1080×1920, 30 i/s, 63 s : entre 62 et 64 s) de géopolitique et d'actualité expliquées par l'histoire, puis la pousser sur `main`. La publication sur Telegram est faite ensuite par GitHub Actions (`.github/workflows/telegram.yml`). Une fois la vidéo envoyée sur Telegram, la tâche la programme sur TikTok via Metricool (étape k).

Projet indépendant : n'utiliser que les fichiers de ce dépôt (aucune DA, règle ou fichier d'un autre projet).

## Préparation
- `git pull origin main` avant de commencer (le workflow Telegram pousse des fichiers `.telegram_ok`).
- Dépendances : `pip install edge-tts piper-tts numpy scipy playwright` ; `ffmpeg` doit être disponible. Si Chromium n'est pas trouvé par Playwright, `outils/export_mp4.py` essaie `/opt/pw-browsers/chromium`, sinon lancer `python -m playwright install chromium`.
- Date du jour au format `AAAA-MM-JJ` (ci-dessous `<date>`).
- Connecteurs requis : **Google Drive** (lecture), **Google Docs** (modification) et **Metricool** (publication TikTok, marque « Amadeus », blogId `7870985`). Le Doc des sujets : « Amadeus — Sujets géopolitiques », id `1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA`
  (https://docs.google.com/document/d/1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA/edit).

- **Rattrapage TikTok** : pour chaque dossier `videos/NNN-*/` qui a `.telegram_ok` mais pas `.tiktok_ok` (vidéo d'un jour précédent restée sans TikTok), faire l'étape k pour ce dossier avant de commencer la nouvelle vidéo.

## Étapes

a. **Lire les règles.** Lire `kit/REGLES.md`, `kit/DA.md` et `kit/reglages.json`. Si `DA.md` ou `REGLES.md` contient « À REMPLIR » : écrire `videos/ERREUR-<date>/alerte.txt` (fichier concerné et raison), commit « Amadeus — ERREUR <date> », push, **stop**.

b. **Choisir le sujet dans le Google Doc.**
   1. Lire le Doc avec Google Drive `read_file_content` (fileId `1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA`, `includeComments: true`). Si l'id ne répond pas, chercher avec `search_files` la requête `title = 'Amadeus — Sujets géopolitiques'` et prendre ce fichier (jamais un autre document).
   2. Si le Doc est introuvable ou illisible : écrire `videos/ERREUR-<date>/alerte.txt` (« Doc des sujets inaccessible » + l'erreur), commit, push, **stop**. Ne jamais choisir un sujet hors du Doc.
   3. Lister les lignes de la forme `Sxxx · À FAIRE · Région · Titre`. Ignorer toutes les lignes `FAIT`. Écarter aussi tout sujet dont le titre ou l'événement figure déjà dans « Déjà faits » de `kit/sujets.md`. S'il ne reste aucun sujet : alerte « Plus aucun sujet À FAIRE dans le Doc », commit, push, **stop**.
   4. Parmi les sujets restants, faire une recherche d'actualité (7 derniers jours) et prendre celui qui a le lien le plus fort avec un événement récent. À égalité ou sans lien net : le premier `À FAIRE` dans l'ordre du Doc. Si possible, éviter la même région que la vidéo précédente.
   5. Noter l'identifiant `Sxxx` choisi : il sert à l'étape h. Le titre du Doc est une piste ; le titre final de la vidéo peut être reformulé, mais le sujet reste le même.

c. **Créer le dossier.** Prendre le numéro suivant (plus grand `NNN` existant dans `videos/` + 1, sur 3 chiffres, `001` pour la première) et créer `videos/NNN-slug/` (slug en minuscules, sans accents, mots séparés par des tirets).

d. **Script et voix.**
   - Viser 63 s : environ 160 à 170 mots. Écrire le script parlé en suivant la structure, le hook et les règles de texte de `REGLES.md`. Vérifier chaque fait, chiffre et date par une recherche web récente ; noter les sources pour soi (elles ne vont pas dans la caption sauf crédit photo).
   - Enregistrer le script dans `videos/NNN-slug/script.txt`, puis : `python outils/voix.py videos/NNN-slug/script.txt videos/NNN-slug/` → `voix.mp3` + `voix.srt` + `voix_mode.txt`. Le script essaie dans l'ordre : edge-tts (voix de `reglages.json`), puis Piper (voix de secours hors ligne), puis le mode sans voix (audio silencieux + sous-titres calés à 2,7 mots/s). Lire `voix_mode.txt` pour savoir quel mode a été utilisé ; les erreurs des modes ratés sont dans `voix_erreurs.txt` (ne pas committer ce fichier).
   - Vérifier la fin de `voix.srt` : entre 61,5 et 63,5 s (la vidéo dure fin de la voix + au plus 0,5 s, soit 62 à 64 s). Sinon ajuster le script et régénérer.
   - Le mode utilisé ne bloque jamais la livraison : la vidéo est produite et publiée même en `piper` ou en `sans-voix`.
   - Si le mode n'est pas `edge-tts` : écrire aussi `videos/ERREUR-<date>/alerte.txt` (« Voix dégradée : <mode> » + contenu de `voix_erreurs.txt`) dans le même commit que la vidéo, pour que l'incident soit visible.
   - En mode `sans-voix`, `apercu.html` doit rendre les sous-titres plus présents (plus grands, toujours à l'écran) puisqu'ils portent seuls le récit.
   - Si `voix.py` sort avec le code 1 (cas anormal, même le mode sans voix a échoué) : `videos/ERREUR-<date>/alerte.txt` avec l'erreur, commit, push, **stop**.

e. **Image et son.**
   - Écrire `videos/NNN-slug/apercu.html` selon `DA.md` : page de 1080×1920 qui expose `window.DUREE` (durée en secondes = fin de `voix.srt` + au plus 0,5 s) et `window.seek(t)`, qui affiche l'état exact au temps t sans dépendre de l'horloge réelle (aucune animation CSS ou `requestAnimationFrame` libre ; tout est calculé à partir de t). Polices via Google Fonts ; images et textures libres de droits uniquement.
   - Ressources externes : le réseau de la tâche peut bloquer certains sites (constaté le 2026-11-04 : Wikimedia, NASA, unpkg et cdnjs bloqués ; Google Fonts accessible). Tester chaque téléchargement avec `curl -sS -o /dev/null -w '%{http_code}'`. Si une image ou une bibliothèque est inaccessible, la dessiner directement dans la page : drapeaux en SVG (formes et couleurs officielles), globe et cartes en canvas/SVG procéduraux, silhouettes stylisées au lieu de portraits. Ne jamais bloquer la vidéo pour une ressource externe.
   - Les coupes, apparitions de texte, chiffres et sous-titres se calent sur les temps de `voix.srt`. Le zoom de l'image se cale sur les kicks : `python outils/sons.py kicks --duree <D> --coupures <flash-backs>`.
   - `python outils/export_mp4.py videos/NNN-slug/apercu.html <tmp>/muette.mp4`
   - Écrire la liste des bruitages (`<tmp>/sfx.json` : whoosh sur chaque coupe, impact sur chaque chiffre ou date, riser avant chaque révélation) puis :
     `python outils/mixage.py --video <tmp>/muette.mp4 --voix videos/NNN-slug/voix.mp3 --coupures <flash-backs> --bruitages <tmp>/sfx.json --sortie videos/NNN-slug/video.mp4`
   - `video.mp4` doit faire moins de 50 Mo (limite Telegram) ; `mixage.py` recompresse automatiquement sinon. Ne pas committer les fichiers temporaires (muette.mp4, wav).

f. **Checklist.** Passer la checklist finale de `REGLES.md` point par point (durée entre 62 et 64 s avec `ffprobe`, hook ≤ 2 s, voix audible (sauf mode `sans-voix`), sous-titres synchronisés et dans la zone sûre — vérifier sur des captures `window.seek(t)` —, boucle fin → début, tous les points de vue présentés, faits vérifiés, aucun contenu sous droits, taille < 50 Mo, caption conforme). Corriger et refaire l'export tant qu'un point échoue.

g. **Caption et méta.** Écrire `videos/NNN-slug/caption.txt` selon la section « Caption » de `REGLES.md` (texte brut, hook en première ligne, 3 à 5 hashtags à la fin, 1024 caractères maximum). Puis `videos/NNN-slug/meta.json` :
   `{"numero": "NNN", "titre": "...", "date": "<date>", "theme": "...", "hook": "...", "duree_s": 63.0, "voix": "<contenu de voix_mode.txt : edge-tts, piper ou sans-voix>", "sujet_id": "Sxxx"}`

h. **Sujets.** Ajouter une ligne `| NNN | Sxxx | titre | <date> |` dans « Déjà faits » de `kit/sujets.md`, et ajouter `"sujet_id": "Sxxx"` dans `meta.json`.

i. **Livraison.** Commit « Amadeus NNN — titre », push sur `main`. Le dossier livré contient : `apercu.html`, `script.txt`, `voix.mp3`, `voix.srt`, `voix_mode.txt`, `video.mp4`, `caption.txt`, `meta.json`. La publication Telegram est déclenchée automatiquement par le push de `video.mp4`.

j. **Marquer le sujet FAIT dans le Google Doc** (seulement après un push réussi).
   - Google Docs `update_doc` (documentId `1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA`) avec une seule requête :
     `{"replaceAllText": {"containsText": {"text": "Sxxx · À FAIRE ·", "matchCase": true}, "replaceText": "Sxxx · FAIT le <date> (vidéo NNN) ·"}}`
   - La réponse doit indiquer `occurrencesChanged: 1`. Si c'est 0 : relire le Doc ; si la ligne est déjà FAIT, ne rien faire ; sinon écrire `videos/ERREUR-<date>/alerte.txt` (« Sujet Sxxx non marqué dans le Doc »), commit, push.
   - Relire le Doc avec `read_file_content` et vérifier que la ligne `Sxxx` commence bien par `Sxxx · FAIT le <date>`.
   - Ne jamais supprimer, renuméroter ou réécrire d'autres lignes du Doc.

k. **Publier sur TikTok via Metricool** (seulement si `"publication": true` et `"tiktok"` dans `plateformes` de `reglages.json`).
   1. **Attendre l'envoi Telegram** : `git pull origin main` toutes les minutes environ, jusqu'à `attente_telegram_minutes` (15 min), tant que `videos/NNN-slug/.telegram_ok` n'existe pas. S'il n'apparaît pas : ne pas publier sur TikTok, écrire `videos/ERREUR-<date>/alerte.txt` (« Telegram non confirmé, TikTok non publié pour NNN »), commit, push, stop (le rattrapage du lendemain s'en chargera).
   2. **Vérifier l'absence de doublon** : si `videos/NNN-slug/.tiktok_ok` existe, ne rien faire. Sinon appeler Metricool `getScheduledPosts` (brandId `7870985`, timezone `Europe/Paris`, de maintenant à +2 jours) : si un post TikTok contient déjà le hook de cette vidéo, ne pas en créer un second ; écrire seulement `.tiktok_ok`.
   3. **Lien public de la vidéo** (le dépôt est public) : `https://raw.githubusercontent.com/mbadra001/amadeus-videos/<sha>/videos/NNN-slug/video.mp4`, où `<sha>` = `git rev-parse HEAD` après le pull. Vérifier avec `curl -sI` qu'il répond 200.
   4. **Programmer le post** avec Metricool `createScheduledPost` :
      - `blogId` : `7870985` ; `date` : maintenant + `delai_minutes` (10 min), au format ISO 8601 avec le décalage de Europe/Paris.
      - `info` (JSON) :
        `{"autoPublish": true, "draft": false, "providers": [{"network": "tiktok"}], "text": <contenu exact de caption.txt>, "media": [<lien public>], "publicationDate": {"dateTime": "AAAA-MM-JJTHH:mm:ss", "timezone": "Europe/Paris"}, "firstCommentText": "", "descendants": [], "mediaAltText": [], "shortener": false, "smartLinkData": {"ids": []}, "hasNotReadNotes": false, "tiktokData": {"privacyOption": "PUBLIC_TO_EVERYONE", "disableComment": false, "disableDuet": false, "disableStitch": false, "commercialContentThirdParty": false, "commercialContentOwnBrand": false, "autoAddMusic": false, "isAigc": true}}`
      - La caption est celle de `caption.txt`, sans modification. `isAigc: true` déclare un contenu généré par IA (voix de synthèse, animation générée), comme TikTok le demande. Le post TikTok part aussi quand la vidéo est en mode `piper` ou `sans-voix`.
   5. **En cas d'erreur Metricool** : ne pas réessayer en boucle (une seule nouvelle tentative si l'erreur est réseau). Écrire `videos/ERREUR-<date>/alerte.txt` avec le message exact, commit, push, stop.
   6. **En cas de succès** : écrire `videos/NNN-slug/.tiktok_ok` avec la date de publication prévue, l'id du post et le `plannerUrl` renvoyés par Metricool, puis commit « Amadeus NNN — TikTok programmé », push sur `main`.
