# Security

Windows Spotlight Downloader est un petit projet personnel distribué avec un exécutable Windows portable.

## Vérifier une release

Chaque release doit indiquer le SHA256 de `WindowsSpotlightDownloader.exe`.

Après téléchargement, vous pouvez vérifier le fichier avec PowerShell :

```powershell
Get-FileHash -Algorithm SHA256 .\WindowsSpotlightDownloader.exe
```

Le hash affiché doit correspondre à celui indiqué dans la release GitHub.

## Windows SmartScreen

Windows peut afficher un avertissement SmartScreen parce que l'exécutable n'est pas signé numériquement.

Cet avertissement ne signifie pas automatiquement que l'application est malveillante. Il indique surtout que l'exécutable n'a pas encore de réputation suffisante auprès de Microsoft.

## Signaler un problème

Pour signaler un problème de sécurité, ouvrez une issue GitHub avec un titre clair, par exemple :

```text
Security: description courte du problème
```

N'incluez pas de données personnelles, de tokens, de mots de passe ou d'informations privées dans une issue publique.
