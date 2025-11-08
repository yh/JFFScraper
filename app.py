import base64
import datetime
import glob
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import bs4
import cloudscraper
import subprocess
import configparser

from yt_dlp import YoutubeDL
scraper = cloudscraper.create_scraper(browser={
        'browser': 'chrome',
        'platform': 'android',
        'desktop': False
    })


class Post:
    def __init__(self, post_soup: bs4.Tag):
        self.post_soup = post_soup

        ptext = post_soup.select("div.fr-view")
        classvals = post_soup.attrs["class"]

        self.uploader_id: str = re.fullmatch(
            r"""location\.href=['"]/?(.+?)['"]""",
            post_soup.select("h5.mbsc-card-title.mbsc-bold span")[0].get("onclick"),
        ).group(1)
        self.post_date_str = post_soup.select("div.mbsc-card-subtitle")[0].text.strip()
        # Stripping "burning post" alert
        self.post_date_str = self.post_date_str.split("This post will disappear")[
            0
        ].strip()

        self.pid = base64.b64decode(post_soup.attrs["data-pid"]).decode()
        self.full_text = ptext[0].text.strip() if ptext else ""
        self.tags = list(
            x.text.strip().strip("#") for x in post_soup.select("div.postTags a")
        )
        self.access_control = next(
            (
                x[len("AccessControl-") :]
                for x in classvals
                if x.startswith("AccessControl-")
            ),
            None,
        )

        self.store_url = None

        self.type = None
        if "shoutout" in classvals:
            self.type = "shoutout"
        elif "video" in classvals:
            self.type = "video"
        elif "photo" in classvals:
            self.type = "photo"
        elif "text" in classvals:
            self.type = "text"

        self.pinned = "pinned" in classvals

        store_button = post_soup.select("div.storeItemWidget button")
        if len(store_button) > 0:
            store_url = re.fullmatch(
                r"""location\.href=['"]/?(.+?)['"]""", store_button[0].get("onclick")
            ).group(1)
            self.store_url = urllib.parse.urljoin("https://justfor.fans/", store_url)

        self.upload_date = "Unknown Date"
        self.upload_date_iso = "Unknown Date"
        self.post_date = "Unknown Date"
        self.post_date_iso = "Unknown Date"

        try:
            pinned = post_soup.select("div.pinnedNotice")
            if pinned is not None:
                self.post_date = "Pinned"
        except:
            pass

        try:
            card_subtitle = post_soup.select("div.mbsc-card-subtitle")
            post_url = html.unescape(
                re.fullmatch(
                    r"""location\.href=['"]/?(.+?)['"]""",
                    card_subtitle[0].get("onclick"),
                ).group(1)
            )
            self.post_url = urllib.parse.urljoin("https://justfor.fans/", post_url)
            parsed_url = urllib.parse.urlparse(self.post_url)
            query_strings = urllib.parse.parse_qs(parsed_url.query)
            if "Post" in query_strings:
                self.mcid = base64.b64decode(query_strings["Post"][0]).decode()
                if "-MC-" in self.mcid:
                    dt = datetime.datetime.fromtimestamp(
                        int(self.mcid.split("-MC-")[1]) * 0.001
                    )
                    self.upload_date = dt.strftime("%Y-%m-%d")
                    self.upload_date_iso = dt.isoformat()
                    self.post_date = self.upload_date
                    self.post_date_iso = self.upload_date_iso
        except:
            pass

        try:
            dt_format = "%B %d, %Y, %I:%M %p"
            dt = datetime.datetime.strptime(self.post_date_str, dt_format)
            self.post_date = dt.strftime("%Y-%m-%d")
            self.post_date_iso = dt.isoformat()
        except:
            pass

        self.excerpt = self.full_text
        self.excerpt = re.sub(r'[\\\/:*?"<>|\s]', " ", self.excerpt)
        self.excerpt = re.sub(r"\s{2,}", " ", self.excerpt).strip()

        basename = (
            config.get('General', 'file_name_format').replace("{name}", self.uploader_id)
            .replace("{post_date}", self.post_date)
            .replace("{post_id}", self.pid)
            .replace("{desc}", self.excerpt)
        )
        basename = basename.strip().encode("utf-8")

        if len(basename) >= 140:
            i = basename.rfind(b" ", 0, 140)
            if i == -1:
                i = 140
            basename = basename[:i] + b"..."

        self.basename = basename.decode("utf-8")


def create_folder(post: Post) -> str:
    fpath = os.path.join(config.get('Paths', 'save_path'), post.uploader_id, post.type)
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    return fpath


def photo_save(post: Post):
    print("Downloading Photo : %s" % post.basename)

    photos_url = []

    photos_img = post.post_soup.select("div.imageGallery.galleryLarge img.expandable")

    if len(photos_img) == 0:
        photos_img.append(post.post_soup.select("img.expandable")[0])

    for i, img in enumerate(photos_img):
        if "src" in img.attrs:
            imgsrc = img.attrs["src"]
        elif "data-lazy" in img.attrs:
            imgsrc = img.attrs["data-lazy"]
        else:
            # print("no image source, skipping")
            continue
        ext = imgsrc.split(".")[-1]

        folder = create_folder(post)
        ppath = ".".join(
            [os.path.join(folder, "{}.{:02}".format(post.basename, i)), ext]
        )

        exists = (
            len(
                glob.glob(
                    os.path.join(folder, post.basename[:50])
                    + "*.{:02}.{}".format(i, ext)
                )
            )
            > 0
        )
        if not config.getboolean('General', 'overwrite_existing') and exists:
            # print(f'p: <<exists skip>>: {ppath}')
            continue

        photos_url.append((ppath, imgsrc))

    for img in photos_url:
        ppath, imgsrc = img
        tmp_ppath = ppath + ".tmp"

        try:
            response = scraper.get(imgsrc, stream=True)
            # print("Downloading " + str(round(int(response.headers.get('content-length'))/1024/1024, 2)) + " MB")
            with open(tmp_ppath, "wb") as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response
            os.rename(tmp_ppath, ppath)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception:
            import traceback

            print(traceback.format_exc())

def decrypt_file_internal(path, hex_key):
    f_base, f_ext = os.path.splitext(path)
    out_path = f"{f_base}_decrypted{f_ext}"
    
    command = [
        'ffmpeg',
        '-decryption_key', hex_key,
        '-i', path,
        '-c', 'copy',  # Copy codec, don't re-encode
        '-y',          # Overwrite output
        out_path
    ]
    
    subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    shutil.move(out_path, path)

def video_save(post: Post):
    print("Downloading Video : %s" % post.basename)

    folder = create_folder(post)
    vpath = os.path.join(folder, post.basename) + ".mp4"

    downloading = next(
        iter(glob.glob(os.path.join(folder, f"* - {post.pid} - *.ytdl"))), None
    )
    downloaded = next(
        iter(glob.glob(os.path.join(folder, f"* - {post.pid} - *.mp4"))), None
    )
    exists = downloading is None and downloaded is not None
    if not config.getboolean('General', 'overwrite_existing') and exists:
        if downloaded is not None and downloaded != vpath:
            os.rename(downloaded, vpath)
        return

    try:
        videoBlock = post.post_soup.select("div.videoBlock a")
        if len(videoBlock) == 0:
            if post.store_url is None:
                print("Get video URL failed: %s" % post.basename[:30])
            else:
                print("Store post: %s" % post.basename[:30])
            return
        vidurljumble = videoBlock[0].attrs["onclick"]

        jumble_args = vidurljumble.split(", ")
        vidurl_json_str = jumble_args[1] # Arg 2: {"540p":...}

        vidurl = json.loads(vidurl_json_str)
        url = vidurl.get("All", "")
        if url == "":
            url = vidurl.get("1080p", "")
        if url == "":
            url = vidurl.get("540p", "")

        # print("URL: %s" % url)

        license_url_str = jumble_args[6] # Arg 7: "https://..."...
        license_url = license_url_str.strip('")')
        parsed_license_url = urllib.parse.urlparse(license_url)
        query_params = urllib.parse.parse_qs(parsed_license_url.query)
        kid = query_params['kid'][0]
            
        license_response = scraper.get(license_url)
        hex_key = license_response.content.hex()

        # print("KEY: %s:%s" % (kid, hex_key))

        temp_path = os.path.join(folder, post.pid)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "retries": 10,
            "concurrent_fragment_downloads": 8,
            "updatetime": True,
            "noprogress": True,
            "outtmpl": temp_path,
            "allow_unplayable_formats": True,
            "format": "bv*+ba/b",

        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        vpath_base = os.path.splitext(temp_path)[0]
        search_pattern = f"{vpath_base}.f*"
        downloaded_files = glob.glob(search_pattern)

        for f_path in downloaded_files:
            decrypt_file_internal(f_path, hex_key)
        
        video_file = next((f for f in downloaded_files if f.endswith('.mp4')), None)
        audio_file = next((f for f in downloaded_files if f.endswith('.m4a') or f.endswith('.m4b')), None)

        # print("Video file: %s" % video_file)
        # print("Audio file: %s" % audio_file)

        merge_command = [
            'ffmpeg',
            '-i', video_file,
            '-i', audio_file,
            '-c', 'copy',  # Copy the video codec
            '-y',          # Overwrite output file if it exists
            '-shortest',
            vpath
        ]
        subprocess.run(merge_command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        for f in downloaded_files:
            os.remove(f)

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        import traceback

        print(traceback.format_exc())


def text_save(post: Post):
    print("Downloading Text :  %s" % post.basename)

    folder = create_folder(post)
    tpath = os.path.join(folder, post.basename) + ".txt"

    exists = len(glob.glob(os.path.join(folder, post.basename[:50]) + "*.txt")) > 0
    if not config.getboolean('General', 'overwrite_existing') and exists:
        return

    # print(f't: {tpath}')

    with open(tpath, "w", encoding="utf-8") as file:
        file.write("---\n")
        file.write("pid: %s\n" % post.pid)
        file.write("mcid: %s\n" % post.mcid)
        file.write("upload: %s\n" % post.upload_date_iso)
        file.write("publish: %s\n" % post.post_date_iso)
        file.write("tags: %s\n" % ", ".join(post.tags))
        if post.access_control is not None:
            file.write("access_control: %s\n" % post.access_control)
        if post.store_url is not None:
            file.write("store_url: %s\n" % post.store_url)
        file.write("---\n\n")
        file.write(post.full_text)

        file.close()


def parse_and_get(html_text: str):
    soup = bs4.BeautifulSoup(html_text, "html.parser")

    for pp in soup.select("div.mbsc-card.jffPostClass"):
        try:
            if "donotremove" in pp.get("class"):
                # Skip "Whom To Follow"
                continue

            post = Post(pp)

            if post.type == "shoutout":
                # Skip "Shoutout Post"
                continue
            elif post.type == "video":
                video_save(post)
                if config.getboolean('General', 'save_full_text'):
                    text_save(post)
            elif post.type == "photo":
                photo_save(post)
                if config.getboolean('General', 'save_full_text'):
                    text_save(post)
            elif post.type == "text":
                if config.getboolean('General', 'save_full_text'):
                    text_save(post)

            if post.post_date == "Unknown Date":
                print("================================")
                print("[WARN] Unknown Date")
                print(pp.prettify())
                print("================================")

        except KeyboardInterrupt:
            sys.exit(0)
        except Exception:
            print("================================")
            print(pp.prettify())
            import traceback

            print(traceback.format_exc())
            print("================================")


def get_html(loopct: int) -> str:
    geturl = ""
    if poster_id != "":
        geturl = config.get('API', 'api_url_poster').format(
            hash=user_hash, poster_id=poster_id, seq=loopct,
        )
    else:
        geturl = config.get('API', 'api_url').format(
            hash=user_hash, seq=loopct,
        )

    html_text = scraper.get(geturl).text
    return html_text


if __name__ == "__main__":
    config = configparser.ConfigParser(allow_no_value=True)
    config.read('config.ini')

    user_hash = ""
    poster_id = ""

    if len(sys.argv) >= 2:
        user_hash = sys.argv[1]
        print("(%s) Using user hash from command line parameters." % user_hash)

    if len(sys.argv) >= 3:
        poster_id = sys.argv[2]
        print("(%s) Using poster ID from command line parameters." % poster_id)
    
    if user_hash == "":
        user_hash = config.get('Authentication', 'user_hash')

    if user_hash == "":
        print(
            "Specify UserHash4 in the config file or in the command line parameters and restart program. Aborted."
        )
        sys.exit(0)
    else:
        print("(%s) Using user hash from config file." % user_hash)

    if poster_id == "":
        poster_id = config.get('Poster', 'poster_id', fallback="")
        if poster_id:
            print("(%s) Using poster ID from config file." % poster_id)

    loopit = True
    loopct: int = 0
    while loopit:
        html_text = get_html(loopct)

        if "as sad as you are" in html_text:
            print("(%s) No more posts to parse. Exiting." % user_hash)
            print(
                "If program has not downloaded any files, your token might be expired or invalid. Get a new one."
            )
            loopit = False
        else:
            parse_and_get(html_text)
            loopct += 10
