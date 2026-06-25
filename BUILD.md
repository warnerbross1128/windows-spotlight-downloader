# Build

Ce document décrit le build local de `WindowsSpotlightDownloader.exe`.

## Prérequis

- Windows
- Python 3.11 ou plus récent
- `pip`

Installer les dépendances de l'application et PyInstaller :

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

## Générer l'exécutable

```powershell
pyinstaller --clean --noconfirm WindowsSpotlightDownloader.spec
```

L'exécutable est créé ici :

```text
dist\WindowsSpotlightDownloader.exe
```

## Calculer le SHA256

```powershell
Get-FileHash -Algorithm SHA256 .\dist\WindowsSpotlightDownloader.exe
```

Copier ce SHA256 dans la description de la release GitHub.

Un script peut aussi générer `dist\SHA256SUMS.txt` :

```powershell
.\scripts\update-release-hash.ps1
```

## Checklist de release

- Vérifier que `APP_VERSION` dans `spotlight_downloader.py` correspond au tag prévu.
- Lancer les tests :

```powershell
python -m unittest discover -s tests
```

- Générer `WindowsSpotlightDownloader.exe`.
- Calculer le SHA256 ou générer `dist\SHA256SUMS.txt`.
- Créer la release GitHub.
- Joindre `WindowsSpotlightDownloader.exe`.
- Ajouter le SHA256 dans la description de la release.
