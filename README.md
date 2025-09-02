# SnapStitcher

CLI tool to download new Snapchat story/highlight snaps from provided links, validate and re-encode videos, and merge them into a single output video. Tracks previously downloaded snaps per link to avoid duplicates.

## Features
- Fetches page JSON (__NEXT_DATA__) and extracts snapList robustly
- Downloads only new snaps per link using last_snap.json
- Supports JPG and MP4; filters, validates, and re-encodes videos (H.264/AAC)
- Skips corrupted or silent videos; merges valid clips into one file
- Enforces minimum merged duration (>= 8 minutes) before keeping output
- Manages saved links via interactive CLI (saved_urls.json)

## Requirements
- Python 3.8+
- ffmpeg and ffprobe installed and added to PATH
- Python packages in equirements.txt

## Installation
`ash
pip install -r requirements.txt
`

On Windows, ensure fmpeg and fprobe are available in PATH. You can install via choco install ffmpeg or download from the official site.

## Usage
Run the CLI:
`ash
python main.py
`

Menu options:
1. Download stories from saved links
2. Save new link
3. Delete a link
4. Download from a link without saving (immediate)
5. Check available snaps for saved links
6. Download stories from a specific saved link
7. Exit

Outputs go to the output/ folder. Temporary downloads are in snaps_* folders and get cleaned up after merging.

## Data Files
- saved_urls.json: list of saved links
- last_snap.json: last downloaded timestamp per link

## Notes
- Only new snaps (with timestamp greater than the last recorded) are downloaded
- Merged video is kept only if duration is >= 8 minutes

## License
MIT
