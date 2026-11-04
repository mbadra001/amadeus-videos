# Règles vidéo Amadeus
Durée : 63 secondes exactement visées (tolérance 62 à 64 s, jamais hors de cet intervalle). Format 1080×1920, 30 i/s. Script parlé d'environ 160 à 170 mots ; si voix.srt ne finit pas entre 61,5 et 63,5 s, raccourcir ou allonger le script et régénérer la voix (ne pas étirer l'audio).
Hook : dans les 2 premières secondes, une phrase choc avec un chiffre ou un fait concret, sans introduction.
Structure : hook → l'événement actuel → l'impact concret sur le spectateur → retour dans le passé (dates clés) → les points de vue des différentes parties, présentés à égalité → la situation aujourd'hui → dernière phrase qui enchaîne sur la première (boucle).
Rythme : une coupe toutes les 1 à 2 secondes, aucun plan fixe de plus de 2,5 secondes.
Texte : phrases courtes, tutoiement ou vouvoiement constant, un chiffre ou une date toutes les 5 à 10 secondes.
Sous-titres : mot par mot, synchronisés sur voix.srt, dans la zone sûre TikTok (centre vers y = 1320, largeur ≤ 860 px, rien au-delà de x = 940 ni sous y = 1500).
Boucle : la dernière image doit se fondre dans la première.
Faits : chaque fait, chiffre et date est vérifié par une recherche web récente ; les sujets en cours sont datés dans la caption (« Situation au JJ mois AAAA »).
Interdits : opinion personnelle sur un sujet politique, parti pris pour un camp, contenu sous droits (musique, photos de presse, logos, personnages), images violentes réalistes, chiffres non sourcés.
Checklist finale : durée entre 62 et 64 s ; sujet pris dans le Google Doc des sujets et marqué FAIT ; hook ≤ 2 s ; voix présente et audible (ou mode sans voix assumé, voir « Voix ») ; sous-titres synchronisés et dans la zone sûre ; boucle fin → début ; tous les points de vue présentés ; faits vérifiés ; aucun contenu sous droits ; video.mp4 < 50 Mo ; caption conforme.

## Voix
- Voix principale : edge-tts, voix de `reglages.json`.
- Si edge-tts échoue : voix de secours Piper (hors ligne, voix française SIWIS, licence CC BY 4.0). La caption doit alors contenir la ligne « Voix : Piper, SIWIS (CC BY 4.0) » juste avant les hashtags.
- Si Piper échoue aussi : vidéo sans voix (musique, bruitages et sous-titres mot à mot), publiée normalement.
- Dans tous les cas la vidéo est publiée ; un mode dégradé est signalé par une alerte dans `videos/ERREUR-<date>/`.

## Sujets (Google Drive)
- La seule liste de sujets est le Google Doc « Amadeus — Sujets géopolitiques » (id `1qvAKlDfhOXX-JwwoqF2txn5lupwbmnW7c50tfr49qAA`, aussi dans `kit/reglages.json` → `sujets_drive`).
- Chaque ligne a la forme `Sxxx · STATUT · Région · Titre`. Statut `À FAIRE` = disponible ; `FAIT le AAAA-MM-JJ (vidéo NNN)` = déjà traité, interdit.
- Un sujet ne se fait qu'une fois : jamais un sujet marqué FAIT, ni un sujet déjà présent dans « Déjà faits » de `kit/sujets.md` (même événement ou même angle).
- Après livraison, marquer le sujet FAIT dans le Doc par un remplacement exact du texte `Sxxx · À FAIRE ·` (aucune autre modification du Doc).
- Si le Doc est inaccessible ou ne contient plus aucun sujet À FAIRE : ne pas inventer de sujet, écrire une alerte et s'arrêter (voir kit/TACHE.md).

## Caption
La même caption sert pour Telegram et TikTok (via Metricool).
- Texte brut, sans Markdown (ni `*`, ni `_`, ni `#` de titre, ni liens formatés).
- Aucun commentaire sur la vidéo ni sur sa fabrication, aucune mention de Claude.
- Première ligne : le hook.
- Si le sujet est en cours : une ligne « Situation au JJ mois AAAA ».
- Crédits des photos libres de droits utilisées, le cas échéant (auteur, licence).
- Fin : 3 à 5 hashtags pertinents.
- 1024 caractères maximum, espaces et hashtags compris (limite Telegram).
