import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, unquote, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from restaurant.models import MenuItem


ALLOWED_IMAGE_HOSTS = {
    "api.openverse.org",
    "upload.wikimedia.org",
    "live.staticflickr.com",
    "images.unsplash.com",
}
MAX_IMAGE_BYTES = 12 * 1024 * 1024
IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
)
OPENVERSE_SEARCH_ALIASES = {
    "Idli (2 pieces)": "idli sambar",
    "Andhra Chicken Fry": "chicken fry",
    "Andhra Chicken Curry": "indian chicken curry",
}


def image_extension(data):
    for signature, extension in IMAGE_SIGNATURES:
        if data.startswith(signature):
            return extension
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and b"avif" in data[8:32]:
        return ".avif"
    raise ValueError("Downloaded response is not a supported image file.")


def is_supported_image(path):
    try:
        with path.open("rb") as image_file:
            image_extension(image_file.read(16))
    except (OSError, ValueError):
        return False
    return True


def thumbnail_source(source, width=960):
    parsed = urlsplit(source)
    if parsed.hostname != "upload.wikimedia.org":
        return source

    path_parts = parsed.path.split("/")
    try:
        commons_index = path_parts.index("commons")
    except ValueError:
        return source
    filename = unquote(path_parts[-1])
    thumb_parts = (
        path_parts[: commons_index + 1]
        + ["thumb"]
        + path_parts[commons_index + 1 : -1]
        + [filename, f"{width}px-{filename}"]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, "/".join(quote(part, safe="._-") for part in thumb_parts), "", ""))


def openverse_image_for(item, used_thumbnails, timeout):
    ignored_words = {"pieces", "piece"}
    item_words = {
        word.rstrip("s") if len(word) > 4 else word
        for word in slugify(item.name).replace("-", " ").split()
        if word not in ignored_words and not word.isdigit()
    }
    search_terms = [item.name]
    alias = OPENVERSE_SEARCH_ALIASES.get(item.name)
    if alias:
        search_terms.append(alias)

    for search_term in search_terms:
        query = urlencode(
            {
                "q": search_term,
                "license": "cc0,pdm,by,by-sa",
                "source": "flickr",
                "page_size": 10,
            }
        )
        request = Request(
            f"https://api.openverse.org/v1/images/?{query}",
            headers={"User-Agent": "SaffronTableMenuImages/1.0 (Django restaurant menu)"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read(2 * 1024 * 1024))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue

        matches = []
        for result in payload.get("results", []):
            thumbnail = result.get("thumbnail", "")
            if (
                result.get("source") != "flickr"
                or urlparse(thumbnail).hostname != "api.openverse.org"
                or thumbnail in used_thumbnails
            ):
                continue
            result_words = set(slugify(result.get("title", "")).replace("-", " ").split())
            result_words.update(tag.get("name", "").lower() for tag in result.get("tags", []))
            result_words = {word.rstrip("s") if len(word) > 4 else word for word in result_words}
            matched_words = item_words & result_words
            if not item_words or len(matched_words) < min(2, len(item_words)):
                continue
            matches.append((len(matched_words), result))

        if matches:
            matches.sort(key=lambda match: match[0], reverse=True)
            result = matches[0][1]
            return result["thumbnail"], result["foreign_landing_url"]
    return None


def download_image(source, timeout):
    if urlparse(source).hostname not in ALLOWED_IMAGE_HOSTS:
        raise ValueError("Image URL host is not allowed")
    request = Request(
        source,
        headers={
            "User-Agent": "SaffronTableMenuImages/1.0 (Django restaurant menu)",
            "Accept": "image/webp,image/png,image/jpeg,*/*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise ValueError(f"Unexpected content type: {content_type}")
        image_data = response.read(MAX_IMAGE_BYTES + 1)
    if len(image_data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit")
    return image_data, image_extension(image_data)


class Command(BaseCommand):
    help = "Download distinct menu photos into static/images/menu without overwriting files."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=float, default=20, help="Per-image network timeout in seconds.")

    def handle(self, *args, **options):
        image_directory = Path(settings.BASE_DIR) / "static" / "images" / "menu"
        image_directory.mkdir(parents=True, exist_ok=True)
        timeout = options["timeout"]
        downloaded = 0
        skipped = 0
        failures = []
        used_fallback_thumbnails = set()
        existing_hashes = {
            hashlib.sha256(image_file.read_bytes()).digest()
            for image_file in image_directory.iterdir()
            if image_file.is_file() and is_supported_image(image_file)
        }

        for item in MenuItem.objects.order_by("pk"):
            if item.image_path:
                existing_path = Path(settings.BASE_DIR) / "static" / item.image_path
                if existing_path.is_file() and is_supported_image(existing_path):
                    skipped += 1
                    continue

            source = item.image_url
            source_page = item.image_source_url
            hostname = urlparse(source).hostname
            if not source or hostname not in ALLOWED_IMAGE_HOSTS:
                failures.append(f"{item.name}: image URL host is missing or not allowed")
                continue

            try:
                image_data, extension = download_image(thumbnail_source(source), timeout)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                fallback = openverse_image_for(item, used_fallback_thumbnails, timeout)
                if not fallback:
                    failures.append(f"{item.name}: {exc}; no matching Openverse fallback")
                    continue
                source, source_page = fallback
                try:
                    image_data, extension = download_image(source, timeout)
                except (HTTPError, URLError, TimeoutError, OSError, ValueError) as fallback_error:
                    failures.append(f"{item.name}: fallback download failed: {fallback_error}")
                    continue
                used_fallback_thumbnails.add(source)

            image_hash = hashlib.sha256(image_data).digest()
            if image_hash in existing_hashes:
                failures.append(f"{item.name}: downloaded image duplicates another menu photo")
                continue

            filename = f"{slugify(item.name)}{extension}"
            destination = image_directory / filename
            if destination.exists():
                if not is_supported_image(destination):
                    failures.append(f"{item.name}: destination already exists and is not a supported image")
                    continue
                skipped += 1
            else:
                try:
                    with destination.open("xb") as image_file:
                        image_file.write(image_data)
                except FileExistsError:
                    if not is_supported_image(destination):
                        failures.append(f"{item.name}: destination was concurrently created with invalid data")
                        continue
                    skipped += 1
                except OSError as exc:
                    failures.append(f"{item.name}: could not write image: {exc}")
                    continue
                else:
                    downloaded += 1

            item.image_path = f"images/menu/{filename}"
            item.image_url = source
            item.image_source_url = source_page
            item.save(update_fields=["image_path", "image_url", "image_source_url"])
            existing_hashes.add(image_hash)

        self.stdout.write(f"Downloaded: {downloaded}; already present: {skipped}; failed: {len(failures)}.")
        for failure in failures:
            self.stderr.write(f"- {failure}")
        if failures:
            raise CommandError("Some menu images could not be downloaded. Failed rows retain their remote URL and local fallback.")