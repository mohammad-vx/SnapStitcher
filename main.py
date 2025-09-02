import requests
import re
import json
import os
from urllib.parse import urlparse
from datetime import datetime
import subprocess
import shutil

# Function to load last snaps from file
def load_last_snaps():
    if os.path.exists("last_snap.json"):
        with open("last_snap.json", "r") as f:
            return json.load(f)
    return {}

# Function to save last snaps to file
def save_last_snaps(last_snaps):
    with open("last_snap.json", "w") as f:
        json.dump(last_snaps, f)

# Function to check available snaps without downloading
def check_available_snaps(url):
    HEADERS_PAGE = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html"
    }

    res = requests.get(url, headers=HEADERS_PAGE, allow_redirects=True)
    html = res.text

    matches = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not matches:
        print("❌ No JSON data found.")
        return None

    data = json.loads(matches[0])
    pageProps = data.get("props", {}).get("pageProps", {})

    snapList = get_snap_list(pageProps)
    if not snapList:
        print("❌ No snapList found in the data.")
        return None

    total_snaps = len(snapList)
    print(f"✅ Total available snaps: {total_snaps}")

    # Load last timestamp for this URL
    last_snaps = load_last_snaps()
    last_timestamp = last_snaps.get(url, 0)

    # Snaps that have been downloaded (timestamp <= last_timestamp)
    downloaded_snaps_list = [snap for snap in snapList if int(snap.get("timestampInSec", {}).get("value", 0)) <= last_timestamp]
    downloaded_count = len(downloaded_snaps_list)
    print(f"✅ Downloaded snaps from available: {downloaded_count}")

    # New snaps (timestamp > last_timestamp)
    new_snaps_list = [snap for snap in snapList if int(snap.get("timestampInSec", {}).get("value", 0)) > last_timestamp]
    new_count = len(new_snaps_list)
    print(f"✅ New snaps not downloaded yet: {new_count}")

    # Count jpg and mp4 in new snaps
    jpg_count = len([snap for snap in new_snaps_list if snap.get("snapMediaType", 2) == 2])
    mp4_count = len([snap for snap in new_snaps_list if snap.get("snapMediaType", 2) == 1])
    print(f"✅ From new snaps: JPG: {jpg_count}, MP4: {mp4_count}")

    return {
        "total": total_snaps,
        "downloaded": downloaded_count,
        "new": new_count,
        "jpg": jpg_count,
        "mp4": mp4_count
    }

# Function to download snaps from a given URL
def download_snaps(url, folder_name):
    HEADERS_PAGE = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html"
    }

    HEADERS_FILE = {
        "User-Agent": HEADERS_PAGE["User-Agent"],
        "Referer": url,
        "Accept": "*/*",
        "Range": "bytes=0-"
    }

    res = requests.get(url, headers=HEADERS_PAGE, allow_redirects=True)
    html = res.text

    matches = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not matches:
        print("❌ No JSON data found.")
        return []

    data = json.loads(matches[0])
    pageProps = data.get("props", {}).get("pageProps", {})

    snapList = get_snap_list(pageProps)
    if not snapList:
        print("❌ No snapList found in the data.")
        return []

    # Load last timestamp for this URL
    last_snaps = load_last_snaps()
    last_timestamp = last_snaps.get(url, 0)

    # Filter snaps: only those with timestamp > last_timestamp
    filtered_snapList = [snap for snap in snapList if int(snap.get("timestampInSec", {}).get("value", 0)) > last_timestamp]

    if not filtered_snapList:
        print("❌ No new snaps found after filtering.")
        return []

    print(f"✅ Found {len(filtered_snapList)} new snaps.")

    os.makedirs(folder_name, exist_ok=True)
    downloaded_files = []
    new_last_timestamp = last_timestamp  # To update with the max timestamp downloaded

    for i, snap in enumerate(filtered_snapList):
        try:
            snap_url = snap["snapUrls"]["mediaUrl"]
            media_type = snap.get("snapMediaType", 2)
            ext = "mp4" if media_type == 1 else "jpg"

            timestamp_sec = snap.get("timestampInSec", {}).get("value")
            if timestamp_sec:
                try:
                    timestamp_sec = int(timestamp_sec)
                    readable_time = datetime.utcfromtimestamp(timestamp_sec).strftime('%Y-%m-%d_%H-%M-%S')
                    # Update new_last_timestamp if this is higher
                    if timestamp_sec > new_last_timestamp:
                        new_last_timestamp = timestamp_sec
                except:
                    readable_time = "unknown_time"
            else:
                readable_time = "no_time"

            file_name = f"STORY_{i+1}_{readable_time}.{ext}"
            file_path = os.path.join(folder_name, file_name)

            readable_time_print = readable_time.replace("_", ":")
            print(f"⬇️ Downloading: {snap_url}")
            print(f"🕒 Snap publish time: {readable_time_print} UTC")

            r = requests.get(snap_url, headers=HEADERS_FILE)
            if r.status_code in (200, 206):
                with open(file_path, "wb") as f:
                    f.write(r.content)
                print(f"✅ Saved: {file_path}")
                downloaded_files.append(file_path)
            else:
                print(f"⚠️ Download failed, status code: {r.status_code}")
        except Exception as e:
            print(f"⚠️ Error in snap {i+1}: {e}")

    # Update last_snap.json if new snaps were downloaded
    if downloaded_files and new_last_timestamp > last_timestamp:
        last_snaps[url] = new_last_timestamp
        save_last_snaps(last_snaps)

    return downloaded_files

def get_snap_list(page_props):
    if "highlight" in page_props and "snapList" in page_props["highlight"]:
        return page_props["highlight"]["snapList"]
    if "story" in page_props:
        story = page_props["story"]
        if isinstance(story, dict) and "snapList" in story:
            return story["snapList"]
    for key in ["snapList"]:
        if key in page_props and isinstance(page_props[key], list):
            return page_props[key]
    return None

# Function to get video info
def get_video_info(file_path):
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

# Function to check if video is valid
def is_valid_video(file_path):
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", file_path,
        "-f", "null",
        "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

# Function to reencode video
def reencode_video(input_file, output_file):
    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-ac", "2",
        "-b:a", "192k",
        "-y",
        output_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

# Function to merge videos
def merge_videos(folder_name, output_folder):
    # Collect only video files (.mp4), skip images
    files = [os.path.join(folder_name, f) for f in os.listdir(folder_name) if f.lower().endswith('.mp4')]
    files.sort(key=lambda x: os.path.getctime(x))  # Sort by creation time	

    valid_files = []
    temp_dir = os.path.join(folder_name, "temp_videos")
    os.makedirs(temp_dir, exist_ok=True)

    for f in files:
        print(f"Checking file: {f}")
        temp_output = os.path.join(temp_dir, f"processed_{os.path.basename(f)}")

        if is_valid_video(f):
            info = get_video_info(f)
            has_audio = any(stream["codec_type"] == "audio" for stream in info.get("streams", []))
            if not has_audio:
                print(f"⚠️ Skipping file with no audio: {f}")
                continue

            if reencode_video(f, temp_output):
                valid_files.append(temp_output)
            else:
                print(f"⚠️ Failed to re-encode file: {f}")
        else:
            print(f"⚠️ Skipping corrupted file: {f}")

    if not valid_files:
        print("No valid video files found to merge.")
        # Still delete original files even if no merge
        all_files = [os.path.join(folder_name, f) for f in os.listdir(folder_name) if f.lower().endswith(('.mp4', '.jpg'))]
        for f in all_files:
            os.remove(f)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    # Write list.txt
    list_path = os.path.join(folder_name, "list.txt")
    with open(list_path, "w", encoding="utf-8") as list_file:
        for vf in valid_files:
            abs_path = os.path.abspath(vf).replace("\\", "/")
            list_file.write(f"file '{abs_path}'\n")

    output_video = os.path.join(output_folder, f"output_{os.path.basename(folder_name)}.mp4")
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", os.path.abspath(list_path).replace("\\", "/"),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-ac", "2",
        "-b:a", "192k",
        "-shortest",
        "-y",
        output_video
    ]

    print(f"Merging files into {output_video} ...")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Done! Output file: {output_video}")

        # Check duration
        info = get_video_info(output_video)
        duration = float(info.get("format", {}).get("duration", 0))
        if duration < 480:  # 8 minutes = 480 seconds
            print(f"⚠️ Video duration {duration} seconds is less than 8 minutes. Deleting {output_video}")
            os.remove(output_video)
        else:
            print(f"✅ Video duration {duration} seconds is valid.")
    else:
        print(f"❌ Error during merging: {result.stderr}")

    # Clean up temp files
    for f in valid_files:
        os.remove(f)
    if os.path.exists(list_path):
        os.remove(list_path)
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Delete original downloaded files after merging (including images if any were downloaded)
    all_files = [os.path.join(folder_name, f) for f in os.listdir(folder_name) if f.lower().endswith(('.mp4', '.jpg'))]
    for f in all_files:
        os.remove(f)

# Function to load saved URLs from file
def load_saved_urls():
    if os.path.exists("saved_urls.json"):
        with open("saved_urls.json", "r") as f:
            return json.load(f)
    return []

# Function to save URLs to file
def save_urls(urls):
    with open("saved_urls.json", "w") as f:
        json.dump(urls, f)

def process_urls(urls, output_folder):
    for idx, url in enumerate(urls):
        now_folder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"snaps_{idx+1}_{now_folder}"
        print(f"📂 Processing link {idx+1}: {url} in folder {folder_name}")

        downloaded_files = download_snaps(url, folder_name)
        if downloaded_files:
            merge_videos(folder_name, output_folder)
        else:
            print(f"⚠️ No files downloaded for link {url}")
            # If no downloads, remove empty folder
            if os.path.exists(folder_name) and not os.listdir(folder_name):
                os.rmdir(folder_name)

        print(f"✅ Finished processing link {idx+1}")

def check_saved_urls():
    saved_urls = load_saved_urls()
    if not saved_urls:
        print("❌ No saved links found.")
        return

    print("✅ Saved links:")
    for i, url in enumerate(saved_urls):
        print(f"{i+1}. {url}")
        print(f"Checking available snaps for {url}:")
        check_available_snaps(url)
        print("---")

def main():
    output_folder = "output"
    os.makedirs(output_folder, exist_ok=True)

    while True:
        print("\nOptions:")
        print("1. Download stories from saved links")
        print("2. Save new link")
        print("3. Delete a link")
        print("4. Download from a link without saving (immediate)")
        print("5. Check available snaps for saved links")
        print("6. Download stories from a specific saved link")
        print("7. Exit")
        choice = input("Enter your choice (1-7): ").strip()

        if choice == '1':
            saved_urls = load_saved_urls()
            if not saved_urls:
                print("❌ No saved links found.")
            else:
                print("✅ Saved links:")
                for i, url in enumerate(saved_urls):
                    print(f"{i+1}. {url}")
                process_urls(saved_urls, output_folder)

        elif choice == '2':
            new_url = input("Enter new link to save: ").strip()
            if new_url:
                saved_urls = load_saved_urls()
                saved_urls.append(new_url)
                save_urls(saved_urls)
                print("✅ Link saved.")
            else:
                print("❌ No link entered.")

        elif choice == '3':
            saved_urls = load_saved_urls()
            if not saved_urls:
                print("❌ No saved links to delete.")
            else:
                print("✅ Saved links:")
                for i, url in enumerate(saved_urls):
                    print(f"{i+1}. {url}")
                try:
                    index = int(input("Enter the number of the link to delete: ")) - 1
                    if 0 <= index < len(saved_urls):
                        deleted = saved_urls.pop(index)
                        save_urls(saved_urls)
                        print(f"✅ Deleted: {deleted}")
                    else:
                        print("❌ Invalid number.")
                except ValueError:
                    print("❌ Invalid input.")

        elif choice == '4':
            temp_url = input("Enter link for immediate download: ").strip()
            if temp_url:
                process_urls([temp_url], output_folder)
            else:
                print("❌ No link entered.")

        elif choice == '5':
            check_saved_urls()

        elif choice == '6':
            saved_urls = load_saved_urls()
            if not saved_urls:
                print("❌ No saved links found.")
            else:
                print("✅ Saved links:")
                for i, url in enumerate(saved_urls):
                    print(f"{i+1}. {url}")
                try:
                    index = int(input("Enter the number of the link to download: ")) - 1
                    if 0 <= index < len(saved_urls):
                        selected_url = saved_urls[index]
                        process_urls([selected_url], output_folder)
                    else:
                        print("❌ Invalid number.")
                except ValueError:
                    print("❌ Invalid input.")

        elif choice == '7':
            print("Exiting...")
            break

        else:
            print("❌ Invalid choice. Please enter 1-7.")

if __name__ == "__main__":
    main()