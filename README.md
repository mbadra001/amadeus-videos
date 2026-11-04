# Amadeus

Vidéos verticales courtes (1080×1920, 61 à 85 s) qui expliquent la géopolitique et l'actualité par l'histoire : un événement récent, puis ses causes passées, avec un ton objectif et sourcé. Chaque vidéo est produite entièrement à partir de ce dépôt : script, voix de synthèse (edge-tts), animation HTML rendue image par image, musique et bruitages synthétisés, puis publication automatique sur Telegram.

## Arborescence

```
.
├── README.md                    ce fichier
├── .gitignore
├── .github/workflows/
│   └── telegram.yml             publication Telegram automatique (GitHub Actions)
├── kit/
│   ├── TACHE.md                 énoncé complet de la tâche quotidienne
│   ├── DA.md                    direction artistique
│   ├── REGLES.md                règles vidéo, checklist et règles de caption
│   ├── reglages.json            publication, plateformes, format, fps, voix, vitesse
│   ├── sujets.md                sujets déjà faits + idées à venir (anti-doublons)
│   └── stats/stats.csv          statistiques par vidéo et par plateforme
├── outils/
│   ├── voix.py                  texte → voix.mp3 + voix.srt (un sous-titre par mot)
│   ├── export_mp4.py            apercu.html → vidéo muette, image par image (Playwright)
│   ├── sons.py                  musique trap/phonk 140 BPM et bruitages synthétisés
│   └── mixage.py                vidéo muette + voix + musique + bruitages → video.mp4
└── videos/
    └── NNN-slug/                une vidéo par dossier
        ├── apercu.html          animation, expose window.seek(t) et window.DUREE
        ├── script.txt           texte parlé
        ├── voix.mp3, voix.srt   voix et temps de chaque mot
        ├── video.mp4            vidéo finale (< 50 Mo)
        ├── caption.txt          légende de publication (≤ 1024 caractères)
        ├── meta.json            {numero, titre, date, theme, hook, duree_s, voix}
        └── .telegram_ok         ajouté par GitHub Actions une fois publiée
```

Les dossiers `videos/ERREUR-<date>/` contiennent un `alerte.txt` quand la tâche quotidienne a dû s'arrêter (règles incomplètes, voix indisponible) ; ils ne sont jamais publiés.

## Circuit de publication

1. **Production** : la tâche quotidienne (`kit/TACHE.md`) choisit un sujet, écrit et vérifie le script, génère la voix, l'animation et le son, passe la checklist de `kit/REGLES.md`, puis pousse le dossier `videos/NNN-slug/` sur `main`.
2. **Déclenchement** : le push d'un `video.mp4` sous `videos/` lance `.github/workflows/telegram.yml` (aussi lançable à la main depuis l'onglet Actions).
3. **Envoi** : si `kit/reglages.json` a `"publication": true` et `"telegram"` dans `plateformes`, chaque dossier `videos/NNN-*/` qui a `video.mp4` et `caption.txt` mais pas encore `.telegram_ok` est envoyé avec l'API Bot Telegram (`sendVideo`, lecture en streaming, caption = `caption.txt`).
4. **Marquage** : après un envoi réussi, le workflow crée `.telegram_ok` dans le dossier et le pousse sur `main` ; la vidéo n'est donc jamais envoyée deux fois. Un échec d'envoi fait échouer le job (visible dans l'onglet Actions).

Le jeton du bot et l'identifiant du canal sont lus uniquement depuis les secrets GitHub `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.

Pour suspendre la publication : passer `"publication"` à `false` dans `kit/reglages.json`.

## Outils en local

```bash
pip install edge-tts numpy scipy playwright   # + ffmpeg
python outils/voix.py "Texte" videos/001-slug/
python outils/export_mp4.py videos/001-slug/apercu.html muette.mp4
python outils/mixage.py --video muette.mp4 --voix videos/001-slug/voix.mp3 --sortie videos/001-slug/video.mp4
```
