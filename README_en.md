# Image Organizer Pro for Anki

[![Anki Version](https://img.shields.io/badge/Anki-2.1.45%20--%202.1.50+-blue.svg)](https://apps.ankiweb.net/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)

**Image Organizer Pro** is a powerful, professional, and feature-rich Anki add-on designed to manage, clean up, and optimize image resources within your Anki decks. By converting formats, resizing resolutions, and removing duplicate media files, it can reduce your media storage folder size by **70% to 90%**. 

This plugin improves card loading speeds, sync times (with AnkiWeb or self-hosted servers), and optimizes mobile device storage—making it an essential tool for media-heavy decks such as Medical School (AnKing), Languages, Anatomy, and Geography.

---

## 🚀 Key Features

### 1. Smart Image Reorganization
*   **Unified File Naming**: Automatically rename all images using standard naming conventions (MD5 hash, timestamps, sequential numbering, or custom file templates).
*   **Deduplication & Multi-Card Referencing**: Scans all card fields, identifies identical images by file hash, and merges references. It handles concurrent references cleanly to prevent broken images or database errors.
*   **Automatic Reference Updates**: Automatically rewrites HTML `<img>` tags in your cards to update image sources, ensuring card layouts remain intact.

### 2. Advanced Image Optimization & Compression
*   **Smart Format Conversion**: Convert space-consuming, lossless formats (PNG, BMP, TIFF, WebP, HEIC/HEIF) to highly compressed JPG files to save substantial storage space.
*   **Resolution Resizing**: Downscale oversized high-res screenshots to target device presets. Includes built-in presets:
    *   `mobile` (720x1280) - Optimized for smartphones
    *   `tablet` (1080x1920) - Optimized for tablets
    *   `laptop` (1366x768) - Optimized for laptops
    *   `1080p` (1920x1080) - Full HD
    *   `1440p` (2560x1440) - 2K
    *   `4k` (3840x2160) - 4K Ultra HD
    *   `original` - Retain original resolution
*   **Small-Image Filtering**: Define a size threshold (e.g., skip files smaller than 1MB). This ensures tiny icons, emojis, or small diagrams aren't needlessly compressed or degraded.
*   **Space Savings Preview**: Estimates potential storage savings on-screen in real-time before applying any changes to your files.

### 3. Granular Range & Scope Selection
Process exactly what you need. Choose your scope via a simple radio-button interface:
*   **All Cards**: Scans and optimizes the entire Anki collection.
*   **Current Deck**: Processes the currently selected deck (including or excluding subdecks).
*   **Specified Decks**: Multi-select custom decks from an interactive deck tree.
*   **Selected Cards**: Process only cards selected in the Anki Card Browser.
*   **Custom Search Queries**: Run custom scans using Anki's standard search query syntax (e.g. `added:7` for recent cards, or `tag:large_image`).

### 4. Interactive UI & Deep Analytics
*   **Adaptive Layout**: The user interface is dynamically sized based on your monitor's screen resolution to fit both high-DPI displays and small laptop screens.
*   **Post-Process Statistics Dashboard**: Replaces the progress panel after optimization is completed to display clear metrics: total files processed, formats converted, compression ratios, and total megabytes saved.

### 5. Multi-Level Safety Mechanisms
*   **Dry Run Mode**: Scans your deck and simulates the organization process so you can preview changes without modifying files or the database.
*   **Automated Media Backup**: Automatically backs up files to a designated folder (`anki_image_backups`) before executing modifications.
*   **Failure Recovery**: Restores files easily from auto-backups if error conditions are detected.
*   **Safe Batching**: Processes files in configurable batch sizes to prevent database locking, app freezes, or memory leaks.

---

## 🛠️ Integration with Anki

Image Organizer Pro integrates seamlessly with the Anki environment:
1.  **Main Menu**: Accessible via **Tools** → **Image Organizer Pro**. Includes submenus for opening the main interface, launching Quick Processes directly, or accessing Settings.
2.  **Browser Context Menu**: Open the Anki Browser, select your cards, right-click, and select **🖼️ Process selected cards' images (Pro)...** to quickly target specific notes.
3.  **Editor Toolbar**: Adds a **🖼️↑** button to the Anki note editor toolbar (Add Card / Edit Card dialogs) for single-note, on-the-fly optimization.

---

## ⚙️ Configuration & Customization

The add-on offers customizable settings accessible via the **Settings** dialog or by editing the `config.json` file. Below are the key configuration parameters:

| Parameter Key | Type | Default Value | Description |
|---|---|---|---|
| `target_format` | String | `"jpg"` | Target format for image conversion (`"jpg"`, `"webp"`, or `"png"`). |
| `auto_backup` | Boolean | `true` | Enable/disable auto-backup of image files before processing. |
| `backup_folder` | String | `"anki_image_backups"` | Name of the backup folder inside the add-on folder structure. |
| `optimization_strategy` | String | `"balanced"` | Optimization speed/quality strategy (`"minimal"`, `"balanced"`, `"aggressive"`). |
| `skip_locked_cards` | Boolean | `true` | Skip cards that are locked by Anki. |
| `compression.jpg_quality` | Integer | `85` | Quality level for JPG compression (1 to 100). |
| `compression.min_file_size_kb` | Integer | `1024` | Skip files smaller than this size (in KB) to protect small images. |
| `resolution.default_preset` | String | `"laptop"` | Default resolution profile to apply. |
| `resolution.keep_aspect_ratio` | Boolean | `true` | Retain image proportions when resizing. |
| `resolution.resize_mode` | String | `"contain"` | Scaling mode: `"contain"`, `"cover"`, or `"fill"`. |

---

## 📦 Installation Guide

### System Requirements
*   **Anki Version**: 2.1.45 or higher (up to 2.1.50+ and Qt6)
*   **Python**: 3.7+ (Bundled with Anki)
*   **Operating System**: Windows 10/11, macOS 10.14+, Linux

### Setup Instructions

#### Method 1: Manual Installation (Recommended)
1.  Download the repository ZIP archive and extract it.
2.  Locate Anki's add-on directory on your computer:
    *   **Windows**: `%APPDATA%\Anki2\addons21`
    *   **macOS**: `~/Library/Application Support/Anki2/addons21`
    *   **Linux**: `~/.local/share/Anki2/addons21`
3.  Create a folder named `anki_image_organizer_pro` under the `addons21` directory.
4.  Copy all files from the extracted directory into the newly created folder.
5.  Restart Anki.

#### Method 2: From AnkiWeb (Pending Release)
1.  In Anki, go to **Tools** → **Add-ons**.
2.  Click **Get Add-ons...** on the right side.
3.  Enter the code: `[Pending Release]` and click **OK**.
4.  Restart Anki.

### Library Dependencies
This add-on requires the Python **Pillow** (PIL) library for format conversion and image resizing.
*   **Automatic Installation**: On startup, if Pillow is missing, the add-on will prompt you to install it automatically.
*   **Manual Installation**: If the auto-installer fails, you can run the following command in your system shell or virtual environment:
    ```bash
    pip install Pillow
    ```

---

## 🛡️ License

This project is licensed under the **MIT License** - see the [LICENSE](file:///d:/海光/data/anki-zpy/addons21/ImageOrganizer/LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to open Issues or submit Pull Requests on the official [GitHub Repository](https://github.com/bugsbunny8/anki-image-organizer).
