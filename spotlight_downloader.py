from __future__ import annotations

import html
import json
import mimetypes
import msvcrt
import os
import re
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path


BASE_URL = "https://windows10spotlight.com"
APP_VERSION = "0.2.4"
GITHUB_REPO = "warnerbross1128/windows-spotlight-downloader"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DEFAULT_LIBRARY_DIR = APP_DIR / "Images telechargees"
CONFIG_PATH = APP_DIR / "config.json"
INSTANCE_LOCK_PATH = Path(tempfile.gettempdir()) / "WindowsSpotlightDownloader.lock"
INSTANCE_LOCK_FILE = None
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def load_config() -> dict[str, str]:
    config = {"libraryDir": str(DEFAULT_LIBRARY_DIR)}
    if not CONFIG_PATH.exists():
        return config
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    library_dir = str(data.get("libraryDir", "")).strip()
    if library_dir:
        config["libraryDir"] = library_dir
    return config


def save_config(config: dict[str, str]) -> dict[str, str]:
    library_dir = Path(config.get("libraryDir", "")).expanduser()
    if not str(library_dir).strip():
        raise ValueError("Le dossier de bibliothèque est vide.")
    if not library_dir.is_absolute():
        library_dir = APP_DIR / library_dir
    library_dir.mkdir(parents=True, exist_ok=True)
    normalized = {"libraryDir": str(library_dir.resolve())}
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def library_dir() -> Path:
    return Path(load_config()["libraryDir"])


def show_message(title: str, message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    except Exception:
        print(f"{title}: {message}")


def acquire_single_instance_lock() -> bool:
    global INSTANCE_LOCK_FILE
    INSTANCE_LOCK_FILE = INSTANCE_LOCK_PATH.open("a+b")
    try:
        INSTANCE_LOCK_FILE.seek(0)
        msvcrt.locking(INSTANCE_LOCK_FILE.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        INSTANCE_LOCK_FILE.close()
        INSTANCE_LOCK_FILE = None
        return False


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Referer": BASE_URL + "/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 15) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json, application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def version_parts(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("vV")
    parts = []
    for part in cleaned.split("."):
        match = re.match(r"\d+", part)
        parts.append(int(match.group(0)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_update() -> dict[str, object]:
    latest = fetch_json(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
    latest_version = str(latest.get("tag_name", "")).lstrip("vV") or APP_VERSION
    asset_url = ""
    for asset in latest.get("assets", []):
        if asset.get("name") == "WindowsSpotlightDownloader.exe":
            asset_url = asset.get("browser_download_url", "")
            break

    update_available = version_parts(latest_version) > version_parts(APP_VERSION)
    return {
        "currentVersion": APP_VERSION,
        "latestVersion": latest_version,
        "updateAvailable": update_available,
        "releaseUrl": latest.get("html_url", ""),
        "downloadUrl": asset_url or latest.get("html_url", ""),
    }


def page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL + "/"
    return f"{BASE_URL}/page/{page}"


def normalize_original_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(html.unescape(url))
    clean_path = re.sub(r"-\d+x\d+(?=\.(?:jpe?g|png|webp)$)", "", parsed.path, flags=re.I)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, clean_path, "", ""))


def best_srcset_url(srcset: str) -> str | None:
    best: tuple[int, str] | None = None
    for chunk in html.unescape(srcset).split(","):
        parts = chunk.strip().split()
        if not parts:
            continue
        url = parts[0]
        width = 0
        if len(parts) > 1 and parts[1].endswith("w"):
            try:
                width = int(parts[1][:-1])
            except ValueError:
                width = 0
        normalized = normalize_original_url(url)
        if best is None or width > best[0]:
            best = (width, normalized)
    return best[1] if best else None


def first_match(pattern: str, text: str, flags: int = re.I | re.S) -> str:
    match = re.search(pattern, text, flags)
    return html.unescape(match.group(1)).strip() if match else ""


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def slugify(value: str, fallback: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"[^\w\s.-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value).strip(".- ")
    return value[:120] or fallback


def parse_images(document: str) -> list[dict[str, str]]:
    articles = re.findall(r"<article\b.*?</article>", document, flags=re.I | re.S)
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for article in articles:
        image_tag = first_match(r"(<img\b[^>]+>)", article)
        if not image_tag:
            continue

        src = first_match(r'\bsrc=["\']([^"\']+)["\']', image_tag)
        srcset = first_match(r'\bsrcset=["\']([^"\']+)["\']', image_tag)
        final_url = best_srcset_url(srcset) if srcset else None
        final_url = final_url or normalize_original_url(src)
        if not final_url or final_url in seen:
            continue
        seen.add(final_url)

        title = strip_tags(first_match(r'<span[^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>(.*?)</span>', article))
        date = strip_tags(first_match(r'<span[^>]*class=["\'][^"\']*date[^"\']*["\'][^>]*>(.*?)</span>', article))
        post_url = first_match(r'<a\b[^>]*href=["\']([^"\']+/images/\d+)["\']', article)
        file_name = Path(urllib.parse.urlsplit(final_url).path).name

        items.append(
            {
                "id": Path(file_name).stem,
                "title": title or Path(file_name).stem,
                "date": date,
                "thumbUrl": normalize_original_url(src) if src else final_url,
                "previewUrl": src or final_url,
                "finalUrl": final_url,
                "postUrl": post_url,
                "fileName": file_name,
            }
        )
    return items


def scan_pages(start: int, pages: int, query: str = "", delay: float = 1.0) -> list[dict[str, str]]:
    all_items: list[dict[str, str]] = []
    seen: set[str] = set()
    query_folded = query.casefold().strip()

    for offset in range(max(1, pages)):
        if offset:
            time.sleep(max(0, delay))
        url = page_url(start + offset)
        for item in parse_images(fetch_text(url)):
            searchable = " ".join([item["title"], item["date"], item["finalUrl"]]).casefold()
            if query_folded and query_folded not in searchable:
                continue
            if item["finalUrl"] in seen:
                continue
            seen.add(item["finalUrl"])
            all_items.append(item)
    return all_items


def target_path_for_item(item: dict[str, str], target_dir: Path | None = None) -> Path:
    url = item.get("finalUrl", "")
    target_dir = target_dir or library_dir()
    extension = Path(urllib.parse.urlsplit(url).path).suffix or ".jpg"
    date = slugify(item.get("date", ""), "spotlight")
    title = slugify(item.get("title", ""), Path(urllib.parse.urlsplit(url).path).stem)
    file_name = f"{date}-{title}{extension}" if date else f"{title}{extension}"
    return target_dir / file_name


def library_match_for_item(item: dict[str, str], target_dir: Path | None = None) -> Path | None:
    target_dir = target_dir or library_dir()
    target = target_path_for_item(item, target_dir)
    if target.exists():
        return target

    url_name = Path(urllib.parse.urlsplit(item.get("finalUrl", "")).path).name
    original = target_dir / url_name
    if original.exists():
        return original

    if not target_dir.exists():
        return None

    target_stem = re.escape(target.stem)
    target_suffix = re.escape(target.suffix)
    target_variant = re.compile(rf"^{target_stem}(?:-\d+)?{target_suffix}$", re.I)
    original_stem = Path(url_name).stem.casefold()

    for existing in target_dir.iterdir():
        if not existing.is_file():
            continue
        if target_variant.match(existing.name):
            return existing
        if original_stem and original_stem in existing.stem.casefold() and existing.suffix.casefold() == target.suffix.casefold():
            return existing
    return None


def mark_library_status(items: list[dict[str, str]]) -> list[dict[str, str]]:
    target_dir = library_dir()
    for item in items:
        target = library_match_for_item(item, target_dir)
        item["inLibrary"] = target is not None
        item["libraryPath"] = str(target) if target else ""
    return items


def download_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    target_dir = library_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in items:
        url = item.get("finalUrl", "")
        if not url.startswith(BASE_URL + "/wp-content/uploads/"):
            results.append({"ok": False, "url": url, "error": "URL refusée"})
            continue

        existing = library_match_for_item(item, target_dir)
        if existing:
            results.append({"ok": True, "skipped": True, "url": url, "path": str(existing), "name": existing.name})
            continue
        target = target_path_for_item(item, target_dir)

        try:
            target.write_bytes(fetch_bytes(url))
            results.append({"ok": True, "skipped": False, "url": url, "path": str(target), "name": target.name})
        except Exception as exc:
            results.append({"ok": False, "url": url, "error": str(exc)})
    return results


def pick_library_folder() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("La sélection graphique de dossier n'est pas disponible.") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title="Choisir la bibliothèque Windows Spotlight",
            initialdir=str(library_dir()),
            mustexist=False,
        )
    finally:
        root.destroy()
    return selected


INDEX_HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Windows Spotlight Downloader</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f4ef;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #667085;
      --line: #d8dee4;
      --accent: #0f766e;
      --accent-ink: #ffffff;
      --soft: #e7f4f1;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      position: sticky;
      top: 0;
      z-index: 3;
      border-bottom: 1px solid var(--line);
      background: rgba(246, 244, 239, .94);
      backdrop-filter: blur(10px);
    }
    .bar {
      max-width: 1280px;
      margin: 0 auto;
      padding: 16px 20px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: end;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    .source-link {
      width: fit-content;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .source-link:hover {
      color: var(--accent);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .app-logo {
      width: 54px;
      height: 54px;
      flex: 0 0 auto;
    }
    .title-block {
      display: grid;
      gap: 10px;
    }
    .title-line {
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 8px 12px;
    }
    .tabs {
      display: flex;
      gap: 6px;
    }
    .app-version {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .tab {
      min-height: 34px;
      padding: 6px 10px;
      background: transparent;
      color: var(--ink);
      border-color: var(--line);
    }
    .tab.active {
      background: var(--accent);
      color: var(--accent-ink);
      border-color: var(--accent);
    }
    .controls {
      display: flex;
      gap: 8px;
      align-items: end;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    label {
      display: grid;
      gap: 4px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }
    input {
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: var(--panel);
    }
    input[type="number"] { width: 86px; }
    input[type="search"] { width: min(38vw, 320px); }
    button {
      min-height: 38px;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 8px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: var(--accent);
      color: var(--accent-ink);
    }
    button.secondary {
      background: var(--panel);
      color: var(--ink);
      border-color: var(--line);
    }
    button:disabled { opacity: .55; cursor: wait; }
    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px 20px 40px;
    }
    .update-notice {
      margin-bottom: 14px;
      padding: 12px 14px;
      border: 1px solid #f5c044;
      border-radius: 8px;
      background: #fff7d6;
      color: var(--ink);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 14px;
    }
    .update-notice[hidden] { display: none; }
    .update-notice a {
      flex: 0 0 auto;
      color: #7a4d00;
    }
    .status {
      min-height: 26px;
      color: var(--muted);
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .progress-wrap {
      height: 8px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--line);
      margin: -4px 0 14px;
    }
    .progress-bar {
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      transition: width .18s ease;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }
    .load-more-wrap {
      display: flex;
      justify-content: center;
      padding: 22px 0 0;
    }
    .page[hidden] { display: none; }
    .config-panel {
      max-width: 780px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      display: grid;
      gap: 14px;
    }
    .config-panel h2 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }
    .config-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: end;
    }
    .wide-input { width: 100%; }
    .tile {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr;
      cursor: pointer;
      transition: border-color .12s ease, box-shadow .12s ease, transform .12s ease;
    }
    .tile:hover {
      border-color: var(--accent);
    }
    .tile.in-library {
      cursor: default;
      opacity: .78;
    }
    .tile.in-library:hover {
      border-color: var(--line);
    }
    .image-wrap {
      position: relative;
      aspect-ratio: 16 / 9;
      background: #d9e3e1;
    }
    .image-wrap img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .check {
      position: absolute;
      top: 10px;
      left: 10px;
      width: 26px;
      height: 26px;
      accent-color: var(--accent);
    }
    .library-badge {
      position: absolute;
      top: 10px;
      right: 10px;
      max-width: calc(100% - 56px);
      padding: 5px 8px;
      border-radius: 6px;
      background: rgba(31, 41, 51, .88);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.2;
    }
    .meta {
      padding: 10px 12px 12px;
      display: grid;
      gap: 8px;
    }
    .title {
      font-size: 14px;
      line-height: 1.35;
      min-height: 38px;
    }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    a { color: var(--accent); text-decoration: none; font-weight: 700; }
    .selected {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--soft);
    }
    .error { color: var(--danger); }
    @media (max-width: 760px) {
      .bar { grid-template-columns: 1fr; align-items: stretch; }
      .brand { align-items: flex-start; }
      .app-logo { width: 48px; height: 48px; }
      .title-line { align-items: flex-start; }
      .controls { justify-content: stretch; }
      label, button { flex: 1 1 130px; }
      input[type="search"] { width: 100%; }
      .config-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="brand">
        <img class="app-logo" src="/assets/logo.svg" alt="" aria-hidden="true">
        <div class="title-block">
          <div class="title-line">
            <h1>Windows Spotlight Downloader</h1>
            <a class="source-link" href="https://windows10spotlight.com/" target="_blank" rel="noreferrer">Source: windows10spotlight.com</a>
            <span class="app-version">Version 0.2.4</span>
          </div>
          <nav class="tabs" aria-label="Navigation">
            <button id="imagesTab" class="tab active" type="button">Images</button>
            <button id="configTab" class="tab" type="button">Config</button>
          </nav>
        </div>
      </div>
      <div class="controls">
        <label>Page début <input id="start" type="number" min="1" value="1"></label>
        <label>Lot <input id="batchSize" type="number" min="1" max="20" value="3"></label>
        <label>Filtre <input id="query" type="search" placeholder="island, forest, 2026-06"></label>
        <button id="scan">Scanner</button>
        <button id="selectAll" class="secondary">Tout cocher</button>
        <button id="download">Télécharger</button>
      </div>
    </div>
  </header>
  <main>
    <div id="updateNotice" class="update-notice" hidden>
      <span id="updateText"></span>
      <a id="updateLink" href="#" target="_blank" rel="noreferrer">Télécharger</a>
    </div>
    <section id="imagesPage" class="page">
      <div class="status">
        <span id="status">Prêt.</span>
        <span id="counter">0 sélectionnée</span>
      </div>
      <div id="progressWrap" class="progress-wrap" hidden>
        <div id="progressBar" class="progress-bar"></div>
      </div>
      <section id="grid" class="grid"></section>
      <div class="load-more-wrap">
        <button id="loadMore" class="secondary" type="button">Charger plus</button>
      </div>
    </section>
    <section id="configPage" class="page" hidden>
      <div class="config-panel">
        <h2>Bibliothèque</h2>
        <label>Emplacement
          <input id="libraryDir" class="wide-input" type="text" placeholder="C:\Users\...\Pictures\Spotlight">
        </label>
        <div class="config-row">
          <span id="configStatus" class="status">Chargement de la configuration...</span>
          <div>
            <button id="pickFolder" class="secondary" type="button">Choisir</button>
            <button id="saveConfig" type="button">Enregistrer</button>
          </div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const grid = document.querySelector("#grid");
    const statusEl = document.querySelector("#status");
    const counterEl = document.querySelector("#counter");
    const scanBtn = document.querySelector("#scan");
    const loadMoreBtn = document.querySelector("#loadMore");
    const downloadBtn = document.querySelector("#download");
    const selectAllBtn = document.querySelector("#selectAll");
    const imagesTab = document.querySelector("#imagesTab");
    const configTab = document.querySelector("#configTab");
    const imagesPage = document.querySelector("#imagesPage");
    const configPage = document.querySelector("#configPage");
    const controls = document.querySelector(".controls");
    const libraryDirInput = document.querySelector("#libraryDir");
    const configStatusEl = document.querySelector("#configStatus");
    const pickFolderBtn = document.querySelector("#pickFolder");
    const saveConfigBtn = document.querySelector("#saveConfig");
    const updateNotice = document.querySelector("#updateNotice");
    const updateText = document.querySelector("#updateText");
    const updateLink = document.querySelector("#updateLink");
    const progressWrap = document.querySelector("#progressWrap");
    const progressBar = document.querySelector("#progressBar");
    let items = [];
    let seenUrls = new Set();
    let nextPage = 1;
    let lastBatchSize = 3;
    let lastQuery = "";

    function showPage(page) {
      const showConfig = page === "config";
      imagesPage.hidden = showConfig;
      configPage.hidden = !showConfig;
      imagesTab.classList.toggle("active", !showConfig);
      configTab.classList.toggle("active", showConfig);
      controls.style.display = showConfig ? "none" : "flex";
      if (showConfig) loadConfig();
    }

    function setBusy(isBusy) {
      scanBtn.disabled = isBusy;
      loadMoreBtn.disabled = isBusy;
      downloadBtn.disabled = isBusy;
    }

    function setProgress(done, total) {
      if (!total) {
        progressWrap.hidden = true;
        progressBar.style.width = "0%";
        return;
      }
      progressWrap.hidden = false;
      progressBar.style.width = `${Math.round((done / total) * 100)}%`;
      if (done >= total) {
        setTimeout(() => {
          progressWrap.hidden = true;
          progressBar.style.width = "0%";
        }, 700);
      }
    }

    function selectedItems() {
      return [...document.querySelectorAll(".pick:checked:not(:disabled)")].map(input => items[Number(input.dataset.index)]);
    }

    function updateCounter() {
      const count = selectedItems().length;
      counterEl.textContent = `${count} sélectionnée${count > 1 ? "s" : ""}`;
      document.querySelectorAll(".tile").forEach(tile => {
        const checked = tile.querySelector(".pick").checked;
        tile.classList.toggle("selected", checked);
      });
    }

    function markTileInLibrary(index, path = "") {
      const item = items[index];
      if (!item) return;
      item.inLibrary = true;
      item.libraryPath = path || item.libraryPath || "";
      const tile = document.querySelector(`.tile[data-index="${index}"]`);
      if (!tile) return;
      tile.classList.add("in-library");
      tile.classList.remove("selected");
      const checkbox = tile.querySelector(".pick");
      checkbox.checked = false;
      checkbox.disabled = true;
      if (!tile.querySelector(".library-badge")) {
        const badge = document.createElement("span");
        badge.className = "library-badge";
        badge.textContent = "Déjà dans la bibliothèque";
        tile.querySelector(".image-wrap").appendChild(badge);
      }
      updateCounter();
    }

    function unmarkTileInLibrary(index) {
      const item = items[index];
      if (!item) return;
      item.inLibrary = false;
      item.libraryPath = "";
      const tile = document.querySelector(`.tile[data-index="${index}"]`);
      if (!tile) return;
      tile.classList.remove("in-library");
      const checkbox = tile.querySelector(".pick");
      checkbox.disabled = false;
      tile.querySelector(".library-badge")?.remove();
      updateCounter();
    }

    function appendItems(nextItems) {
      const freshItems = nextItems.filter(item => {
        if (seenUrls.has(item.finalUrl)) return false;
        seenUrls.add(item.finalUrl);
        return true;
      });
      const startIndex = items.length;
      items.push(...freshItems);
      for (const [offset, item] of freshItems.entries()) {
        const index = startIndex + offset;
        const article = document.createElement("article");
        article.className = "tile";
        article.dataset.index = index;
        if (item.inLibrary) article.classList.add("in-library");
        article.innerHTML = `
          <div class="image-wrap">
            <input class="check pick" type="checkbox" data-index="${index}" ${item.inLibrary ? "disabled" : ""}>
            <img loading="lazy" src="/proxy?url=${encodeURIComponent(item.previewUrl || item.finalUrl)}" alt="">
            ${item.inLibrary ? '<span class="library-badge">Déjà dans la bibliothèque</span>' : ''}
          </div>
          <div class="meta">
            <div class="title"></div>
            <div class="row">
              <span>${item.date || ""}</span>
              <a href="${item.finalUrl}" target="_blank" rel="noreferrer">Original</a>
            </div>
          </div>
        `;
        article.querySelector(".title").textContent = item.title || item.fileName;
        const checkbox = article.querySelector(".pick");
        checkbox.addEventListener("click", event => event.stopPropagation());
        checkbox.addEventListener("change", updateCounter);
        article.querySelector("a").addEventListener("click", event => event.stopPropagation());
        article.addEventListener("click", () => {
          if (item.inLibrary) return;
          checkbox.checked = !checkbox.checked;
          updateCounter();
        });
        grid.appendChild(article);
      }
      updateCounter();
      return freshItems.length;
    }

    async function loadBatch({reset = false} = {}) {
      if (reset) {
        items = [];
        seenUrls = new Set();
        grid.innerHTML = "";
        nextPage = Number(document.querySelector("#start").value || 1);
        lastBatchSize = Number(document.querySelector("#batchSize").value || 1);
        lastQuery = document.querySelector("#query").value || "";
        updateCounter();
      }
      const start = nextPage;
      const pages = Math.max(1, Math.min(20, lastBatchSize));
      const query = lastQuery;
      setBusy(true);
      statusEl.className = "";
      statusEl.textContent = reset ? "Scan en cours..." : "Chargement du lot suivant...";
      try {
        let added = 0;
        for (let offset = 0; offset < pages; offset++) {
          const page = start + offset;
          setProgress(offset, pages);
          statusEl.textContent = `Scan de la page ${page} (${offset + 1}/${pages})...`;
          const response = await fetch(`/api/scan?start=${page}&pages=1&query=${encodeURIComponent(query)}`);
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Scan impossible");
          added += appendItems(data.items);
          setProgress(offset + 1, pages);
        }
        nextPage = start + pages;
        statusEl.textContent = `${items.length} image${items.length > 1 ? "s" : ""} affichée${items.length > 1 ? "s" : ""}. Dernier lot: ${added} nouvelle${added > 1 ? "s" : ""}. Prochaine page: ${nextPage}.`;
      } catch (error) {
        statusEl.className = "error";
        statusEl.textContent = error.message;
      } finally {
        setBusy(false);
      }
    }

    async function download() {
      const chosen = selectedItems();
      if (!chosen.length) {
        statusEl.textContent = "Aucune image sélectionnée.";
        return;
      }
      setBusy(true);
      statusEl.className = "";
      statusEl.textContent = "Téléchargement...";
      try {
        const results = [];
        let folder = "";
        for (const [index, item] of chosen.entries()) {
          setProgress(index, chosen.length);
          statusEl.textContent = `Téléchargement ${index + 1}/${chosen.length}...`;
          const response = await fetch("/api/download", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({items: [item]})
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Téléchargement impossible");
          folder = data.folder || folder;
          results.push(...data.results);
          setProgress(index + 1, chosen.length);
        }
        const saved = results.filter(item => item.ok && !item.skipped);
        const skipped = results.filter(item => item.ok && item.skipped);
        const failed = results.filter(item => !item.ok).length;
        for (const result of results) {
          if (!result.ok) continue;
          const index = items.findIndex(item => item.finalUrl === result.url);
          if (index >= 0) markTileInLibrary(index, result.path || "");
        }
        statusEl.textContent = `${saved.length} téléchargée${saved.length > 1 ? "s" : ""}, ${skipped.length} déjà présente${skipped.length > 1 ? "s" : ""}${failed ? `, ${failed} erreur${failed > 1 ? "s" : ""}` : ""}. Dossier: ${folder}`;
      } catch (error) {
        statusEl.className = "error";
        statusEl.textContent = error.message;
      } finally {
        setBusy(false);
      }
    }

    async function loadConfig() {
      try {
        const response = await fetch("/api/config");
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Configuration introuvable");
        libraryDirInput.value = data.libraryDir || "";
        configStatusEl.className = "status";
        configStatusEl.textContent = `Dossier actuel: ${data.libraryDir}`;
      } catch (error) {
        configStatusEl.className = "status error";
        configStatusEl.textContent = error.message;
      }
    }

    async function saveConfig() {
      saveConfigBtn.disabled = true;
      configStatusEl.className = "status";
      configStatusEl.textContent = "Enregistrement...";
      try {
        const response = await fetch("/api/config", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({libraryDir: libraryDirInput.value})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Enregistrement impossible");
        libraryDirInput.value = data.libraryDir;
        configStatusEl.textContent = `Dossier enregistré: ${data.libraryDir}`;
        refreshLibraryStatus();
      } catch (error) {
        configStatusEl.className = "status error";
        configStatusEl.textContent = error.message;
      } finally {
        saveConfigBtn.disabled = false;
      }
    }

    async function pickFolder() {
      pickFolderBtn.disabled = true;
      configStatusEl.className = "status";
      configStatusEl.textContent = "Sélection du dossier...";
      try {
        const response = await fetch("/api/pick-folder", {method: "POST"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Sélection impossible");
        if (data.libraryDir) {
          libraryDirInput.value = data.libraryDir;
          configStatusEl.textContent = `Dossier sélectionné: ${data.libraryDir}`;
        } else {
          configStatusEl.textContent = "Sélection annulée.";
        }
      } catch (error) {
        configStatusEl.className = "status error";
        configStatusEl.textContent = error.message;
      } finally {
        pickFolderBtn.disabled = false;
      }
    }

    async function checkForUpdates() {
      try {
        const response = await fetch("/api/update-check");
        const data = await response.json();
        if (!response.ok || !data.updateAvailable) return;
        updateText.textContent = `Nouvelle version disponible: ${data.latestVersion} (vous avez ${data.currentVersion}).`;
        updateLink.href = data.downloadUrl || data.releaseUrl;
        updateNotice.hidden = false;
      } catch (error) {
        updateNotice.hidden = true;
      }
    }

    async function refreshLibraryStatus() {
      if (!items.length) return;
      try {
        const response = await fetch("/api/library-status", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({items})
        });
        const data = await response.json();
        if (!response.ok) return;
        for (const [index, item] of data.items.entries()) {
          items[index].inLibrary = item.inLibrary;
          items[index].libraryPath = item.libraryPath || "";
          if (item.inLibrary) markTileInLibrary(index, item.libraryPath || "");
          else unmarkTileInLibrary(index);
        }
      } catch (error) {
      }
    }

    scanBtn.addEventListener("click", () => loadBatch({reset: true}));
    loadMoreBtn.addEventListener("click", () => loadBatch());
    downloadBtn.addEventListener("click", download);
    imagesTab.addEventListener("click", () => showPage("images"));
    configTab.addEventListener("click", () => showPage("config"));
    saveConfigBtn.addEventListener("click", saveConfig);
    pickFolderBtn.addEventListener("click", pickFolder);
    selectAllBtn.addEventListener("click", () => {
      const picks = [...document.querySelectorAll(".pick:not(:disabled)")];
      const shouldCheck = picks.some(input => !input.checked);
      picks.forEach(input => input.checked = shouldCheck);
      updateCounter();
    });
    checkForUpdates();
    if (window.location.hash === "#config") showPage("config");
    loadBatch({reset: true});
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_asset(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/assets/logo.svg":
            self.send_asset(RESOURCE_DIR / "assets" / "logo.svg", "image/svg+xml; charset=utf-8")
            return

        if parsed.path == "/api/scan":
            params = urllib.parse.parse_qs(parsed.query)
            try:
                start = max(1, int(params.get("start", ["1"])[0]))
                pages = min(20, max(1, int(params.get("pages", ["3"])[0])))
                query = params.get("query", [""])[0]
                items = mark_library_status(scan_pages(start, pages, query))
                self.send_json({"items": items})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if parsed.path == "/api/config":
            try:
                self.send_json(load_config())
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if parsed.path == "/api/version":
            self.send_json({"version": APP_VERSION, "appDir": str(APP_DIR)})
            return

        if parsed.path == "/api/update-check":
            try:
                self.send_json(check_for_update())
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if parsed.path == "/proxy":
            params = urllib.parse.parse_qs(parsed.query)
            url = params.get("url", [""])[0]
            if not url.startswith(BASE_URL + "/wp-content/uploads/"):
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            try:
                body = fetch_bytes(url)
                content_type = mimetypes.guess_type(url)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(HTTPStatus.BAD_GATEWAY)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/download":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                results = download_items(payload.get("items", []))
                self.send_json({"folder": str(library_dir()), "results": results})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                self.send_json(save_config(payload))
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if path == "/api/library-status":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                self.send_json({"items": mark_library_status(payload.get("items", []))})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        if path == "/api/pick-folder":
            try:
                selected = pick_library_folder()
                self.send_json({"libraryDir": selected})
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return

        self.send_error(HTTPStatus.NOT_FOUND)
        return


class LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def open_server() -> LocalServer:
    preferred = 8765
    if len(sys.argv) > 1:
        preferred = int(sys.argv[1])
    return LocalServer(("127.0.0.1", preferred), Handler)


def main() -> int:
    os.chdir(APP_DIR)
    if not acquire_single_instance_lock():
        show_message(
            "Windows Spotlight Downloader",
            "Windows Spotlight Downloader est déjà ouvert. Ferme l'autre fenêtre avant d'en lancer une nouvelle.",
        )
        return 1
    with open_server() as server:
        port = server.server_address[1]
        url = f"http://127.0.0.1:{port}"
        print(f"Windows Spotlight Downloader: {url}")
        print(f"Dossier de sortie: {library_dir()}")
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            import webview

            webview.create_window(
                "Windows Spotlight Downloader",
                url,
                width=1280,
                height=860,
                min_size=(980, 620),
            )
            webview.start(gui="winforms")
        except KeyboardInterrupt:
            print("\nArrêt.")
        finally:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
