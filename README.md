# Amadeus

Vidéos verticales courtes (1080×1920, 63 s) qui expliquent la géopolitique et l'actualité par l'histoire : un événement récent, puis ses causes passées, avec un ton objectif et sourcé. Chaque vidéo est produite entièrement à partir de ce dépôt : script, voix de synthèse (edge-tts, avec Piper hors ligne en secours, ou mode sans voix), animation HTML rendue image par image, musique et bruitages synthétisés, puis publication automatique sur Telegram.

## Arborescence

```
.
├── README.md                    ce fichier
├── .gitignore
├── .github/workflows/
│   └── telegram.yml             publication Telegram automatique (GitHub Actions)
├── kit/
│   ├── TACHE.md                 énoncé complet de la tâche quotidienne
│   ├── DA.md                    direction artistique (style « tableau d'histoire »)
│   ├── modele_apercu.html       modèle de page d'animation utilisé par outils/assembler.py
│   ├── exemples/                plans d'exemple (Ormuz)
│   ├── REGLES.md                règles vidéo, checklist et règles de caption
│   ├── reglages.json            publication, plateformes, format, fps, voix, vitesse
│   ├── sujets.md                journal des sujets déjà faits (la liste est sur Google Drive)
│   └── stats/stats.csv          statistiques par vidéo et par plateforme
├── outils/
│   ├── voix.py                  texte → voix.mp3 + voix.srt (edge-tts → Piper → sans voix)
│   ├── medias.py                images et musique libres, en lot et en parallèle (Wikipédia, Library of Congress, NASA, musées de
│   │                            Chicago, Cleveland et Copenhague, Openverse, drapeaux), tri auto, crédits, rendu peinture
│   ├── cartes.py                cartes exactes (Natural Earth) au style carte ancienne
│   ├── assembler.py             plans.js + medias/ + voix.srt → apercu.html (modèle kit/modele_apercu.html)
│   ├── export_mp4.py            apercu.html → vidéo muette, image par image, 4 navigateurs en parallèle (≈ 3 min)
│   ├── sons.py                  bruitages variés (transition, boom, tic, riser…) et musique de secours synthétisés
│   └── mixage.py                vidéo muette + voix + musique + bruitages → video.mp4 (sidechain, < 50 Mo)
└── videos/
    └── NNN-slug/                une vidéo par dossier
        ├── apercu.html          animation (générée par assembler.py), expose window.seek(t)
        ├── plans.js, cles.json  liste des plans et mots clés
        ├── medias/credits.json  crédits des images (les images elles-mêmes ne sont pas versionnées)
        ├── script.txt           texte parlé
        ├── voix.mp3, voix.srt   voix et temps de chaque mot
        ├── video.mp4            vidéo finale (< 50 Mo)
        ├── caption.txt          légende de publication (≤ 1024 caractères)
        ├── meta.json            {numero, titre, date, theme, hook, duree_s, voix, sujet_id}
        ├── .telegram_ok         ajouté par GitHub Actions une fois publiée sur Telegram
        └── .tiktok_ok           ajouté par la tâche une fois programmée sur TikTok (Metricool)
```

Les dossiers `videos/ERREUR-<date>/` contiennent un `alerte.txt` quand la tâche quotidienne a dû s'arrêter (règles incomplètes, Doc des sujets inaccessible, voix dégradée) ; ils ne sont jamais publiés.

## Liste des sujets

Les sujets sont dans le Google Doc [Amadeus — Sujets géopolitiques](https://docs.google.com/document/d/1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA/edit) : une ligne par sujet, `Sxxx · À FAIRE · Région · Titre`. La tâche quotidienne y choisit un sujet `À FAIRE`, puis le marque `FAIT le AAAA-MM-JJ (vidéo NNN)` après livraison. Pour ajouter des sujets, ajouter des lignes `S101 · À FAIRE · …` dans le Doc.

## Circuit de publication

1. **Production** : la tâche quotidienne (`kit/TACHE.md`) choisit un sujet dans le Google Doc, écrit et vérifie le script, génère la voix, l'animation et le son, passe la checklist de `kit/REGLES.md`, puis pousse le dossier `videos/NNN-slug/` sur `main`.
2. **Déclenchement** : le push d'un `video.mp4` sous `videos/` lance `.github/workflows/telegram.yml` (aussi lançable à la main depuis l'onglet Actions).
3. **Envoi** : si `kit/reglages.json` a `"publication": true` et `"telegram"` dans `plateformes`, chaque dossier `videos/NNN-*/` qui a `video.mp4` et `caption.txt` mais pas encore `.telegram_ok` est envoyé avec l'API Bot Telegram (`sendVideo`, lecture en streaming, caption = `caption.txt`).
4. **Marquage** : après un envoi réussi, le workflow crée `.telegram_ok` dans le dossier et le pousse sur `main` ; la vidéo n'est donc jamais envoyée deux fois. Un échec d'envoi fait échouer le job (visible dans l'onglet Actions).

5. **TikTok** : dès que `.telegram_ok` est présent, la tâche quotidienne programme la vidéo sur TikTok via Metricool (marque « Amadeus »), avec la même caption et le lien public GitHub de `video.mp4`, puis ajoute `.tiktok_ok` (étape k de `kit/TACHE.md`). Une vidéo restée sans TikTok est rattrapée le lendemain.

Le jeton du bot et l'identifiant du canal sont lus uniquement depuis les secrets GitHub `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.

Pour suspendre toute publication : passer `"publication"` à `false` dans `kit/reglages.json`. Pour couper seulement TikTok ou Telegram : retirer la plateforme de `"plateformes"`.

## Outils en local

```bash
pip install edge-tts numpy scipy playwright   # + ffmpeg
python outils/voix.py "Texte" videos/001-slug/
python outils/export_mp4.py videos/001-slug/apercu.html muette.mp4
python outils/mixage.py --video muette.mp4 --voix videos/001-slug/voix.mp3 --sortie videos/001-slug/video.mp4
```
