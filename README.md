# JFFScraper

## About
Script to scrape and download content from the JustFor.Fans website. Supports Text, Photo, and Video posts (as of 08/11/2025).

## Requirements

- Python 3.x
- `ffmpeg` must be installed and available in PATH (required for video decryption and merging)

## Usage

0. (optional) Create and activate a Python virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Unix/macOS
    venv\Scripts\activate     # Windows
    ```
1. Install requirements: `pip install -r requirements.txt`
2. Set configuration in `config.ini`:
    - `overwrite_existing` - skip download if file exists (keep False to save on processing)
    - `save_path` - destination folder (saves to script folder if not provided)
    - `save_full_text` - save text file with full description for photo/video posts
    - `max_workers` - number of concurrent page processing threads
    - `concurrent_fragments` - number of concurrent video fragment downloads
    - `use_progress_bar` - toggle rich progress display vs verbose logging
    - `file_name_format` - filename format with placeholders:
        * `{name}` - uploader ID
        * `{post_date}` - post date
        * `{post_id}` - post ID
        * `{desc}` - post description excerpt
   
3. Get UserHash (required) and PosterID  (optional) values
    1. Log into your JustFor.Fans account
    2. (in Chrome), hit F12 to open dev-console
    3. Refresh page to view network activity
    4. Locate `getPost.php` call, extract `UserHash4` value from either the path or cookie

    5. If you want to scrape only a specific performer's posts, navigate to their profile
    6. Locate `getPost.php` call, extract `PosterID` value from the path

4. Run the script and pass in values as arguments:
    * `python app.py [UserHash] [PosterID]`

    or update config.ini with your extracted values and run:
    * `python app.py`

Note that leaving PosterID blank will result in the tool downloading all posts from all performers you are subscribed to.

## Output Structure

Downloads are organized as `{save_path}/{uploader_id}/{type}/` where type is `photo`, `video`, or `text`.

Each uploader folder contains a `metadata.db` SQLite database storing post and media metadata for tracking and querying.

## Contributors

This tool builds upon the work of [whats-happening-rightnow's justfor.fans.ripper](https://github.com/whats-happening-rightnow/justfor.fans.ripper) and its forks ([edwardsdean](https://github.com/edwardsdean/justfor.fans.ripper), [VeryEvilHumna](https://github.com/VeryEvilHumna/justfor.fans.ripper)).
