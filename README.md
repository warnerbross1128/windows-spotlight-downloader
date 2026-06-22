# Windows Spotlight Downloader

Petit logiciel local pour choisir et télécharger les images de `windows10spotlight.com` en qualité originale.

## Lancer

Version portable: double-cliquer sur `WindowsSpotlightDownloader.exe`.

Version source: double-cliquer sur `Lancer le telechargeur.bat`.

Le navigateur s'ouvre sur l'interface locale. Les fichiers sélectionnés sont enregistrés dans `Images telechargees`.

## Configurer la bibliothèque

Ouvrir l'onglet `Config`, choisir ou saisir le dossier de bibliothèque, puis cliquer sur `Enregistrer`.

Les prochains téléchargements seront enregistrés dans ce dossier. La configuration est gardée dans `config.json`.

## Notes

- Les vignettes WordPress comme `image-1024x576.jpg` sont converties vers l'URL originale `image.jpg`.
- Le bouton `Original` ouvre l'image finale dans un nouvel onglet.
- Le chargement se fait par lots. `Scanner` repart depuis la page de début, et `Charger plus` ajoute le lot suivant sans effacer les images déjà affichées.
- Chaque lot est limité à 20 pages pour éviter de marteler le site.
