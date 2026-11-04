# Tâche quotidienne Amadeus

Produire une vidéo verticale (1080×1920, 30 i/s, 61 à 85 s) de géopolitique et d'actualité expliquées par l'histoire, puis la pousser sur `main`. La publication sur Telegram est faite ensuite par GitHub Actions (`.github/workflows/telegram.yml`), jamais par la tâche.

Projet indépendant : n'utiliser que les fichiers de ce dépôt (aucune DA, règle ou fichier d'un autre projet).

## Préparation
- `git pull origin main` avant de commencer (le workflow Telegram pousse des fichiers `.telegram_ok`).
- Dépendances : `pip install edge-tts numpy scipy playwright` ; `ffmpeg` doit être disponible. Si Chromium n'est pas trouvé par Playwright, `outils/export_mp4.py` essaie `/opt/pw-browsers/chromium`, sinon lancer `python -m playwright install chromium`.
- Date du jour au format `AAAA-MM-JJ` (ci-dessous `<date>`).

## Étapes

a. **Lire les règles.** Lire `kit/REGLES.md`, `kit/DA.md` et `kit/reglages.json`. Si `DA.md` ou `REGLES.md` contient « À REMPLIR » : écrire `videos/ERREUR-<date>/alerte.txt` (fichier concerné et raison), commit « Amadeus — ERREUR <date> », push, **stop**.

b. **Choisir le sujet.** Partir d'un événement récent (recherche web d'actualité) et de ses causes historiques. Le sujet doit être absent de la section « Déjà faits » de `kit/sujets.md` (ni même événement, ni même angle). Les « Idées à venir » sont des pistes, à confirmer par l'actualité.

c. **Créer le dossier.** Prendre le numéro suivant (plus grand `NNN` existant dans `videos/` + 1, sur 3 chiffres, `001` pour la première) et créer `videos/NNN-slug/` (slug en minuscules, sans accents, mots séparés par des tirets).

d. **Script et voix.**
   - Écrire le script parlé en suivant la structure, le hook et les règles de texte de `REGLES.md`. Vérifier chaque fait, chiffre et date par une recherche web récente ; noter les sources pour soi (elles ne vont pas dans la caption sauf crédit photo).
   - Enregistrer le script dans `videos/NNN-slug/script.txt`, puis : `python outils/voix.py videos/NNN-slug/script.txt videos/NNN-slug/` → `voix.mp3` + `voix.srt` (un sous-titre par mot, voix et vitesse de `reglages.json`).
   - Si `voix.py` sort avec le code 1 (edge-tts en échec) : écrire `videos/ERREUR-<date>/alerte.txt` avec le message d'erreur complet, commit, push, **stop**. Ne jamais livrer une vidéo sans voix (pas de voix de remplacement, pas de vidéo muette).

e. **Image et son.**
   - Écrire `videos/NNN-slug/apercu.html` selon `DA.md` : page de 1080×1920 qui expose `window.DUREE` (durée en secondes = fin de `voix.srt` + au plus 0,5 s) et `window.seek(t)`, qui affiche l'état exact au temps t sans dépendre de l'horloge réelle (aucune animation CSS ou `requestAnimationFrame` libre ; tout est calculé à partir de t). Polices via Google Fonts ; images et textures libres de droits uniquement.
   - Les coupes, apparitions de texte, chiffres et sous-titres se calent sur les temps de `voix.srt`. Le zoom de l'image se cale sur les kicks : `python outils/sons.py kicks --duree <D> --coupures <flash-backs>`.
   - `python outils/export_mp4.py videos/NNN-slug/apercu.html <tmp>/muette.mp4`
   - Écrire la liste des bruitages (`<tmp>/sfx.json` : whoosh sur chaque coupe, impact sur chaque chiffre ou date, riser avant chaque révélation) puis :
     `python outils/mixage.py --video <tmp>/muette.mp4 --voix videos/NNN-slug/voix.mp3 --coupures <flash-backs> --bruitages <tmp>/sfx.json --sortie videos/NNN-slug/video.mp4`
   - `video.mp4` doit faire moins de 50 Mo (limite Telegram) ; `mixage.py` recompresse automatiquement sinon. Ne pas committer les fichiers temporaires (muette.mp4, wav).

f. **Checklist.** Passer la checklist finale de `REGLES.md` point par point (durée avec `ffprobe`, hook ≤ 2 s, voix audible, sous-titres synchronisés et dans la zone sûre — vérifier sur des captures `window.seek(t)` —, boucle fin → début, tous les points de vue présentés, faits vérifiés, aucun contenu sous droits, taille < 50 Mo, caption conforme). Corriger et refaire l'export tant qu'un point échoue.

g. **Caption et méta.** Écrire `videos/NNN-slug/caption.txt` selon la section « Caption » de `REGLES.md` (texte brut, hook en première ligne, 3 à 5 hashtags à la fin, 1024 caractères maximum). Puis `videos/NNN-slug/meta.json` :
   `{"numero": "NNN", "titre": "...", "date": "<date>", "theme": "...", "hook": "...", "duree_s": 72.4, "voix": "fr-FR-HenriNeural"}`

h. **Sujets.** Ajouter une ligne `| NNN | titre | <date> |` dans « Déjà faits » de `kit/sujets.md` et retirer l'idée correspondante des « Idées à venir » si elle y figurait.

i. **Livraison.** Commit « Amadeus NNN — titre », push sur `main`. Le dossier livré contient : `apercu.html`, `script.txt`, `voix.mp3`, `voix.srt`, `video.mp4`, `caption.txt`, `meta.json`. La publication Telegram est déclenchée automatiquement par le push de `video.mp4`.
