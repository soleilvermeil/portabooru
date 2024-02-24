import os
import requests
import json
import math
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import logging
import glob


INPUT_FOLDER = "./inputs"
OUTPUT_FOLDER = "./outputs"
BASE_URL = "https://danbooru.donmai.us"
MAX_ITEMS_PER_PAGE = 200
SUCCESSIVE_ERRORS_LIMIT = 5
FORBIDDEN_EXTENSIONS = [] # ["mp4", "zip"]
STATUS_CODE = {
    200: "OK",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    410: "Gone",
    420: "Invalid Record",
    422: "Locked",
    423: "Already Exists",
    424: "Invalid Parameters",
    429: "User Throttled",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable"
}


def login(username: str, api_key: str) -> None:
    """
    Logs in to the API using the given credentials.

    Parameters
    ----------
    * username (str): the username to login with
    * api_key (str): the api key to login with

    Returns
    -------
    None
    """
    logging.info("Logging in...")
    params = {
        'login': username,
        'api_key': api_key
    }
    response = requests.get(f"{BASE_URL}/users.json", params=params)
    if response.status_code != 200:
        logging.info(f"failed (status code: {response.status_code}: {STATUS_CODE[response.status_code]}).")
        exit(1)
    logging.info("success!")


def unpack(args):
    """
    Unpacks the arguments and calls the function with the unpacked arguments.

    Parameters
    ----------
    * args (list): the arguments to unpack, where the first argument is the function to call
    """
    func = args[0]
    args = args[1:]
    return func(*args)


def download_image(info: dict, tag: str, only_infos: bool = False) -> None:
    """
    Downloads the image and saves all its tags as well as all the image informations in files.

    Parameters
    ----------
    * info (dict): the image informations as a dictionary
    * tag (str): the tag to search for
    * only_infos (bool): whether to only download the infos of the images

    Returns
    -------
    None
    """
    downloaded_ids = get_downloaded_ids(tag)
    logging.debug("Reading image informations...")
    try:
        id = info['id']
        image_url = info['file_url']
        extension = info['file_ext']
        tags = info['tag_string']
        rating = info['rating']
    except KeyError:
        logging.debug("ignored (wrong formatting).")
        return
    if id in downloaded_ids:
        logging.debug("ignored (already downloaded).")
        return
    formatted_tag = tag
    for chars in ["<", ">", ":", "\"", "\\", "|", "?", "*"]:
        while chars in formatted_tag:
            formatted_tag = formatted_tag.replace(chars, "_")
    path = os.path.join(OUTPUT_FOLDER, formatted_tag, rating)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except FileExistsError: # necessary since multiprocessing could lead to multiple processes trying to create the same directory at the same time
            pass
    imagepath = os.path.join(path, f"{id}_image.{extension}")
    tagspath = os.path.join(path, f"{id}_tags.txt")
    jsonpath = os.path.join(path, f"{id}_infos.json")
    if os.path.exists(imagepath) and os.path.exists(tagspath) and os.path.exists(jsonpath):
        logging.debug("ignored (already exists).")
        return
    logging.debug(f"trying to download image with id '{id}'...")
    if extension.lower() in FORBIDDEN_EXTENSIONS:
        logging.debug(f"ignored (extension: {extension}).")
        return
    if not only_infos:
        try:
            image_response = requests.get(image_url)
        except requests.exceptions.ConnectionError:
            logging.debug("ignored (connection error).")
            return
        image_data = image_response.content
        with open(imagepath, "wb") as f:
            f.write(image_data)
    with open(tagspath, "w") as f:
        f.write("\n".join(tags.split(" ")))
    with open(jsonpath, "w") as f:
        json.dump(info, f, indent=4)
    with open(os.path.join(OUTPUT_FOLDER, formatted_tag, "manifest.txt"), "a") as f:
        f.write(f"{id}\n")
    logging.debug("done!")


def get_images_count(tag: str) -> int:
    """
    Returns the number of images corresponding to the given tag.
    
    Parameters
    ----------
    * tag (str): the tag to search for

    Returns
    -------
    * (int): the number of images corresponding to the given tag
    """
    count_url = f"{BASE_URL}/tags.json?search[name]={tag}"
    response = requests.get(count_url)
    return response.json()[0]['post_count']


def get_downloaded_ids(tag: str, rating: str | None = None) -> list[int]:
    """
    Returns the IDs of the images that have already been downloaded.

    Parameters
    ----------
    * tag (str): the tag to search for
    * rating (str | None): the rating of the images to download if specified

    Returns
    -------
    * (list[int]): the IDs of the images that have already been downloaded
    """
    path = os.path.join(OUTPUT_FOLDER, tag)
    if rating is not None:
        path = os.path.join(path, rating)
    files = glob.glob(f"{path}/*/*_infos.json", recursive=True)
    ids = [int(os.path.basename(file).split("_")[0]) for file in files]
    manifest_ids = []
    try:
        manifest_ids = open(os.path.join(path, "manifest.txt"), "r").read().splitlines()
    except FileNotFoundError:
        pass
    return ids

def get_images_infos(tag: str, limit: int | None = None, rating: str | None = None) -> list[dict]:
    """
    Makes a request to the API to get the informations of multiple images corresponding to the given tag. Images are sorted by ID, oldest first.

    Parameters
    ----------
    * tag (str): the tag to search for
    * limit (int | None): the maximum number of images to download if specified
    * rating (str | None): the rating of the images to download if specified

    Returns
    -------
    * (list[dict]): the informations of the images as a list of dictionaries
    """
    logging.info(f"Requesting images infos for tag '{tag}'.")
    result = []
    downloaded_ids = get_downloaded_ids(tag, rating)
    if limit is None:
        images_count = get_images_count(tag=tag)
        limit = images_count - len(downloaded_ids)
        logging.info(f"{images_count} images found corresponding to this tag.")
    page_limit = math.ceil(limit / MAX_ITEMS_PER_PAGE)
    with tqdm(total=limit, desc="Getting images informations", ascii=True) as pbar2:
        page = 1
        successive_errors = 0
        while page <= page_limit:
            max_items_for_current_page = MAX_ITEMS_PER_PAGE
            # TODO: improve the following line using for example requests.get(..., params=params)
            # NOTE: requests.get() automatically encodes the parameters, which is not wanted since a lot of tags contain special characters
            images_url = f"{BASE_URL}/posts.json?"
            images_url += f"tags={tag}"
            if rating is not None:
                images_url += f"+rating:{rating}"
            images_url += "&"
            images_url += f"limit={max_items_for_current_page}&"
            images_url += f"page={page}&"
            try:
                response = requests.get(images_url)
            except requests.exceptions.ConnectionError:
                if successive_errors < SUCCESSIVE_ERRORS_LIMIT:
                    logging.info("❌ Connection lost. Retrying...")
                    successive_errors += 1
                    continue
                else:
                    logging.info("❌ Connection lost. Skipping current page.")
                    successive_errors = 0
                    page += 1
                    continue
            if response.status_code != 200:
                if successive_errors < SUCCESSIVE_ERRORS_LIMIT:
                    logging.info(f"❌ Error {response.status_code} ({STATUS_CODE[response.status_code]}). Retrying...")
                    successive_errors += 1
                    continue
                else:
                    logging.info(f"❌ Error {response.status_code} ({STATUS_CODE[response.status_code]}). Skipping current page.")
                    successive_errors = 0
                    page += 1
                    continue
            items = response.json()
            if len(items) == 0:
                logging.debug("❎ Empty page found. Stopping.")
                break
            for item in items:
                if 'file_url' not in item:
                    logging.debug(f"❌ Image is not available.") # NOTE: image deleted, banned, premium only, etc.
                elif item['id'] in downloaded_ids or item in result:
                    logging.debug(f"❌ Image already downloaded.")
                else:
                    logging.debug(f"✅ Image added to download queue.")
                    result.append(item)
            page += 1
            pbar2.update(len(items))
    logging.info(f"{len(result)} images ready to be downloaded.")
    return result


if __name__ == "__main__":

    # Setting up the logger
    # ---------------------

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)8s] --- %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Setting up the folders
    # ----------------------

    if os.getenv("RUNNING_IN_DOCKER"):
        INPUT_FOLDER = "/inputs"
        OUTPUT_FOLDER = "/outputs"

    # Connecting to the API
    # ---------------------

    username = os.getenv("NAME")
    api_key = os.getenv("API_KEY")
    login(username, api_key)
    username = None
    api_key = None
    
    # Requesting the images
    # ---------------------

    tags = open(os.path.join(INPUT_FOLDER, "tags.txt"), "r").read().splitlines()
    logging.info(f"Tags found ('*' for metadata only):")
    for tag in tags:
        logging.info(f"  - {tag}")
    only_metadatas = [True if tags.startswith("*") else False for tags in tags]
    tags = [tags[1:] if tags.startswith("*") else tags for tags in tags]
    for tag, only_metadata in zip(tags, only_metadatas):
        logging.info(f"Starting collecting images for tag '{tag}'.")
        tag = tag.strip()
        kwargs = {"tag": tag}
        ids_before = get_downloaded_ids(tag)
        infos = get_images_infos(**kwargs)
        logging.info(f"Parallelizing the downloads using {cpu_count()} processes.")
        with Pool(processes=cpu_count()) as pool:
            with tqdm(total=len(infos), desc="Downloading images", ascii=True) as pbar:
                for _ in pool.imap_unordered(unpack, [(download_image, info, tag, only_metadata) for info in infos]):
                    pbar.update()
        ids_after = get_downloaded_ids(tag)
        logging.info(f"{len(ids_after) - len(ids_before)} images downloaded for tag '{tag}'.")
        