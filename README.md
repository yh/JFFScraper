# JFFScraper

## About
Script to scrape and download content from the JustFor.Fans website. Supports Text, Photo, and Video posts (as of 08/11/2025).

## Usage

0. (optional) Create and activate a Python virtual environment:
     ```
    python -m venv venv
    venv\Scripts\activate
    ```
1. Install requirements: `pip install -r requirements.txt`
2. Set configuration
    1. `overwrite_existing` - will skip download if file exists (set to True to save on processing and downloading)
    2. `save_path` - destination folder - will save to same location as script folder if none provided
    3. `save_full_text` - will save text file with full description
    4. `file_name_format` - filename format, following values are available:
        * `post_date`
        * `post_id`
        * `desc`
   
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

## Contributors

This tool builds upon the work of [whats-happening-rightnow' justfor.fans.ripper](https://github.com/whats-happening-rightnow/justfor.fans.ripper) and its forks ([edwardsdean](https://github.com/edwardsdean/justfor.fans.ripper), [VeryEvilHumna](https://github.com/VeryEvilHumna/justfor.fans.ripper)).
