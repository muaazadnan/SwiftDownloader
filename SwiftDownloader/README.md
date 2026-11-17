# SwiftDownloader

**Free. Fast. Unlimited.**

A professional, open-source download manager for Windows 10/11.

## Features

- **Accelerated Downloads** — Multi-connection downloading for faster speeds
- **Pause & Resume** — Stop and continue downloads at any time
- **Auto-Retry** — Automatically recover from network interruptions
- **Download Queue** — Manage and prioritize your downloads
- **Scheduler** — Schedule downloads for later (once, daily, weekly)
- **File Categorization** — Automatically organize files by type
- **Browser Integration** — Extensions for Chrome, Edge, and Firefox
- **Clipboard Monitoring** — Detect download links from your clipboard
- **SHA-256 Verification** — Verify file integrity after download
- **Dark & Light Themes** — Modern UI with professional design
- **System Tray** — Minimize to tray and run in background
- **Speed Limiter** — Control bandwidth usage
- **Import/Export** — Manage download lists as text files

## System Requirements

- Windows 10 or Windows 11 (64-bit)
- 100 MB disk space
- Internet connection

## Installation

### Installer (Recommended)

1. Download `SwiftDownloader_Setup.exe` from the [Releases](../../releases) page
2. Double-click the installer
3. Follow the setup wizard
4. Launch SwiftDownloader from the desktop or Start Menu

### Portable

1. Download `SwiftDownloader_Portable.zip` from [Releases](../../releases)
2. Extract to any folder
3. Run `SwiftDownloader.exe`

## Browser Integration

SwiftDownloader includes browser extensions for automatic download interception.

### Chrome / Edge

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extensions/chrome` folder from the SwiftDownloader installation directory

### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `manifest.json` from the `extensions/firefox` folder

The installer can also register the native messaging host automatically.

## Building from Source

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
git clone https://github.com/swiftdownloader/swiftdownloader.git
cd swiftdownloader
pip install -r requirements.txt
```

### Run

```bash
python -m app.main
```

### Run Tests

```bash
pip install pytest
pytest tests/ -v
```

### Build Executable

```bash
pip install pyinstaller
cd scripts
pyinstaller swiftdownloader.spec
```

The built application will be in `dist/SwiftDownloader/`.

### Build Installer

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Open `installer/swiftdownloader_setup.iss` in Inno Setup
3. Click Build → Compile
4. The installer will be generated at `dist/SwiftDownloader_Setup.exe`

### Automated Build

Push to GitHub and the included GitHub Actions workflow will:
1. Run all tests
2. Build the Windows executable with PyInstaller
3. Build the installer with Inno Setup
4. Upload both as artifacts
5. Create a release (when pushing a version tag like `v1.0.0`)

## Architecture

```
SwiftDownloader/
├── app/
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration and constants
│   ├── database.py             # SQLite database layer
│   ├── download_engine/
│   │   ├── engine.py           # Core download engine
│   │   └── manager.py          # Download orchestrator
│   ├── scheduler/
│   │   └── scheduler.py        # Download scheduler
│   ├── browser_integration/
│   │   └── native_server.py    # TCP server for browser extensions
│   ├── services/
│   │   └── clipboard_monitor.py
│   ├── ui/
│   │   ├── main_window.py      # Main application window
│   │   ├── themes/             # Dark and light theme styles
│   │   ├── pages/              # Dashboard, downloads, settings, about
│   │   └── dialogs/            # Add download dialog
│   └── utils/
│       ├── formatting.py       # Size, speed, ETA formatting
│       └── logging_setup.py    # Logging configuration
├── browser_extensions/
│   ├── chrome/                 # Chrome/Edge extension (Manifest v3)
│   ├── firefox/                # Firefox extension (Manifest v2)
│   └── native_host/            # Native messaging host
├── tests/                      # pytest test suite
├── installer/                  # Inno Setup script
├── scripts/                    # PyInstaller spec
└── .github/workflows/          # CI/CD pipeline
```

## License

MIT License — see [LICENSE](LICENSE).

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## Troubleshooting

**Downloads are slow:**
- Increase connections per download in Settings (default: 8, max: 32)
- Check that the server supports range requests (some servers limit speed per connection)

**Browser extension not connecting:**
- Make sure SwiftDownloader is running
- Check that the native messaging host is registered (reinstall with browser integration checked)

**Application won't start:**
- Check the log file at `%LOCALAPPDATA%\SwiftDownloader\swiftdownloader.log`
- Try running with `--debug` flag for console output
