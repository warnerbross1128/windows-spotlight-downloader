# Windows Spotlight Downloader

<p align="center">
  <img src="assets/logo.png" width="120" alt="Windows Spotlight Downloader logo">
</p>

Petit logiciel local pour choisir et télécharger les images de `windows10spotlight.com` en qualité originale.

Source des images: [windows10spotlight.com](https://windows10spotlight.com/)

Version actuelle: `0.2.6`

## Installation

Télécharger la version portable depuis la page des releases GitHub, puis lancer `WindowsSpotlightDownloader.exe`.

1. Cliquer sur le bouton `Releases` du dépôt GitHub.

   Capture à ajouter: `docs/screenshots/install-releases.png`

   <!-- ![Bouton Releases](docs/screenshots/install-releases.png) -->

2. Dans la dernière release, télécharger [WindowsSpotlightDownloader.exe](https://github.com/warnerbross1128/windows-spotlight-downloader/releases/download/v0.2.6/WindowsSpotlightDownloader.exe).

   Capture à ajouter: `docs/screenshots/install-download-exe.png`

   <!-- ![Bouton WindowsSpotlightDownloader.exe](docs/screenshots/install-download-exe.png) -->

## Screenshots

### Parcourir les images

![Vue Images](docs/screenshots/images.png)

### Configurer la bibliothèque

![Vue Config](docs/screenshots/config.png)

## Lancer

Version portable: double-cliquer sur `WindowsSpotlightDownloader.exe`.

Version source: double-cliquer sur `Lancer le telechargeur.bat`.

Une fenêtre Windows s'ouvre avec l'interface de l'application. Les fichiers sélectionnés sont enregistrés dans `Images telechargees`.

Depuis `0.2.0`, l'application utilise PyWebView: fermer la fenêtre ferme aussi le processus.

Depuis `0.2.2`, une seule instance de l'application peut être ouverte à la fois pour éviter les tests avec une ancienne copie encore active.

## Configurer la bibliothèque

Ouvrir l'onglet `Config`, choisir ou saisir le dossier de bibliothèque, puis cliquer sur `Enregistrer`.

Les prochains téléchargements seront enregistrés dans ce dossier. La configuration est gardée dans `config.json`.

## Mises à jour

Au démarrage, l'application vérifie la dernière release GitHub publique. Si une version plus récente existe, une notification apparaît avec un lien direct pour télécharger le nouvel exécutable.

Pour publier une mise à jour, incrémenter la version dans `spotlight_downloader.py`, créer une nouvelle release GitHub, puis joindre `WindowsSpotlightDownloader.exe`.

## Notes

- Les vignettes WordPress comme `image-1024x576.jpg` sont converties vers l'URL originale `image.jpg`.
- Le bouton `Original` ouvre l'image finale dans un nouvel onglet.
- Les images déjà présentes dans la bibliothèque sont signalées dans la grille et ignorées au téléchargement, y compris les variantes `-2`, `-3`, etc.
- Le scan et le téléchargement affichent une barre de progression.
- Le chargement se fait par lots. `Scanner` repart depuis la page de début, et `Charger plus` ajoute le lot suivant sans effacer les images déjà affichées.
- Chaque lot est limité à 20 pages pour éviter de marteler le site.
