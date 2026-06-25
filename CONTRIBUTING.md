# Contributing

Merci de l'intérêt porté au projet.

Le projet reste volontairement simple : une application Windows portable pour parcourir et télécharger des images Windows Spotlight depuis `windows10spotlight.com`.

## Avant de proposer une modification

Lancer les vérifications locales :

```powershell
python -m py_compile spotlight_downloader.py tests\test_core.py
python -m unittest discover -s tests
```

## Style de contribution

- Garder les changements ciblés.
- Éviter les refontes larges sans discussion.
- Ne pas ajouter de dépendance si la bibliothèque standard suffit.
- Ne pas inclure d'images téléchargées, d'archives, de builds locaux ou de fichiers de configuration personnels.

## Releases

Les releases sont préparées manuellement.

La checklist de build et de release est dans [BUILD.md](BUILD.md).
