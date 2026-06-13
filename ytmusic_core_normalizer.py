import os
import re
import json
import concurrent.futures
import time
from pathlib import Path

# ── mutagen imports ────────────────────────────────────────────────────────────
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, TRCK
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover, MP4StreamInfoError
from mutagen import File as MutagenFile

# ── optional ytmusicapi ────────────────────────────────────────────────────────
try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def load_grouped_artists(json_path: str) -> list:
    """Load grouped_artists.json; return [] on failure."""
    if not os.path.isfile(json_path):
        print(f"[WARN] grouped_artists.json not found at: {json_path}")
        return []
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def deduplicate_artists(artist_string: str) -> str:
    """
    Split on comma, remove exact duplicates while preserving first-seen order.
    'a,b,v,v,c,a,c,b' -> 'a,b,v,c'
    Does NOT split on & or feat – those are handled separately.
    """
    if not artist_string:
        return artist_string
    parts = [a.strip() for a in artist_string.split(",")]
    seen = set()
    unique = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return ", ".join(unique)


def parse_track_number(filename: str):
    """
    Extract leading track number from filename.
    '03.Song Name.flac' or '03 - Song Name.mp3' -> '3' (or None)
    """
    stem = Path(filename).stem
    m = re.match(r"^(\d+)", stem)
    return m.group(1) if m else None


def find_cover_image(directory: str):
    """Return path to best cover image in directory, or None."""
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    images = [
        os.path.join(directory, f) for f in os.listdir(directory)
        if f.lower().endswith(image_extensions)
    ]
    if not images:
        return None
    preferred = ['cover.png', 'cover.jpg', 'folder.jpg', 'front.jpg']
    for name in preferred:
        for img in images:
            if os.path.basename(img).lower() == name:
                return img
    cover_patterns = [r'cover', r'folder', r'front', r'album', r'^artwork$', r'^thumb$']
    for pat in cover_patterns:
        for img in images:
            if re.search(pat, os.path.basename(img), re.IGNORECASE):
                return img
    return images[0]


# ══════════════════════════════════════════════════════════════════════════════
# ARTIST NORMALISATION LOGIC
# ══════════════════════════════════════════════════════════════════════════════

# Cache fetched artist data so we don't hit the API repeatedly
_artist_cache: dict = {}


def _get_raw_artist_data(artist_id: str, raw_dir: str) -> dict | None:
    """
    Load from raw_responses/{id}_artist_data.json.
    If missing and ytmusicapi available, fetch and save.
    """
    if artist_id in _artist_cache:
        return _artist_cache[artist_id]

    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, f"{artist_id}_artist_data.json")

    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _artist_cache[artist_id] = data
        return data

    if not YTMUSIC_AVAILABLE:
        print(f"  [WARN] ytmusicapi not installed; cannot fetch artist {artist_id}")
        return None

    try:
        print(f"  [API ] Fetching YTMusic artist: {artist_id}")
        ytmusic = YTMusic()
        data = ytmusic.get_artist(channelId=artist_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=3, ensure_ascii=False)
        _artist_cache[artist_id] = data
        return data
    except Exception as e:
        print(f"  [ERR ] YTMusic fetch failed for {artist_id}: {e}")
        return None


def _split_compound_artist(token: str, primary_name: str, alt_name: str | None) -> list[str]:
    """
    Given a single artist token (possibly 'A & B' or 'A feat. B'),
    split it into individual artists IF the first component matches
    primary_name or alt_name.

    Rules:
    - Ignore anything inside () or [] brackets entirely – return [token] unchanged.
    - Split on ' & ' and ' feat. ' / ' ft. ' (case-insensitive).
    - Only split if the first part is an alias of the known artist.
    - Items inside 'artistname (CV A & B)' style: () content protected – handled later.
    """
    # If token contains parentheses or brackets, leave it alone
    if re.search(r'[\(\[\（【]', token):
        return [token]

    # Patterns to split on
    split_pat = re.split(r'\s*(?:&|feat\.|ft\.|/)\s*', token, flags=re.IGNORECASE)

    if len(split_pat) < 2:
        return [token]

    first = split_pat[0].strip()
    known = {n.strip().lower() for n in [primary_name, alt_name] if n}

    if first.lower() in known:
        # First part is our known artist – rest are separate artists
        return [p.strip() for p in split_pat if p.strip()]
    else:
        # The whole token is a single entity (e.g. a band name with & in it)
        return [token]


def normalize_artists(
    raw_artist_str: str,
    grouped: list,
    raw_dir: str,
) -> str:
    """
    Full normalisation pipeline for one artist tag string.

    Steps:
    1. Split on comma, deduplicate positions.
    2. For each token, try to match against grouped_artists entries.
    3. On match: replace token with canonical name; if compound (&/feat.),
       split into individual artists and expand in-place.
    4. Final deduplication pass.
    """
    if not raw_artist_str:
        return raw_artist_str

    # Step 1 – initial dedup
    tokens = [t.strip() for t in raw_artist_str.split(",") if t.strip()]
    seen = set()
    tokens_deduped = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            tokens_deduped.append(t)
    tokens = tokens_deduped

    result_tokens = []

    for token in tokens:
        matched = False

        for entry in grouped:
            eid = entry.get("id")
            names = entry.get("name", [])
            if not eid or not names:
                continue  # skip entries with null id

            # Check all alias texts for a match
            for name_obj in names:
                alias_text = name_obj.get("text", "")
                if alias_text == token:
                    # ── Match found ──────────────────────────────────────────
                    primary_name = names[0]["text"]  # most common name

                    # Fetch raw artist data for official name
                    raw_data = _get_raw_artist_data(eid, raw_dir)
                    official_name = raw_data.get("name") if raw_data else None

                    # Determine alt_name (if primary != official)
                    # primary_name = grouped file's name[0].text  (most common/local)
                    # official_name = {id}_artist_data.json['name'] (YTMusic canonical)
                    alt_name = None
                    has_dual_names = False
                    if official_name and official_name.rstrip() != primary_name:
                        alt_name = official_name.rstrip()
                        has_dual_names = True
                        print(
                            f"  [ALT ] '{primary_name}' also known as '{alt_name.rstrip()}'"
                        )

                    # Check if token is compound (& / feat.) BEFORE deciding expansion
                    # Use primary_name AND alt_name as known identifiers for splitting
                    parts = _split_compound_artist(token, primary_name, alt_name)

                    if len(parts) > 1:
                        # Compound token: first part is the known artist, rest are others
                        # If dual names: insert both for the matched artist, then others
                        if has_dual_names:
                            # official first (EN), then primary (JP/CN/local), then collaborators
                            expanded = [official_name, primary_name] + parts[1:]
                        else:
                            canonical = official_name if official_name else primary_name
                            expanded = [canonical] + parts[1:]
                        print(f"  [SPLIT] '{token}' -> {expanded}")
                    else:
                        if has_dual_names:
                            if official_name.lower().rstrip() == primary_name.lower():
                                #only different is upper case
                                expanded = [primary_name]
                            else:
                                # Two-name artist: insert official (EN) first, then primary (local)
                                # e.g. '塞壬唱片-MSR' -> ['Monster Siren Records', '塞壬唱片-MSR']
                                expanded = [official_name, primary_name]
                                print(f"  [DUAL ] '{token}' -> {expanded}")
                        else:
                            canonical = official_name if official_name else primary_name
                            expanded = [canonical]
                            if canonical != token:
                                print(f"  [NORM ] '{token}' -> '{canonical}'")

                    result_tokens.extend(expanded)
                    matched = True
                    break  # stop checking aliases for this entry

            if matched:
                break  # stop checking entries

        if not matched:
            result_tokens.append(token)

    # Final deduplication preserving order
    seen2: set = set()
    final: list = []
    for t in result_tokens:
        if t not in seen2:
            seen2.add(t)
            final.append(t)

    return ", ".join(final)


# ══════════════════════════════════════════════════════════════════════════════
# TAG READ / WRITE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _read_artist(file_path: str) -> str | None:
    ext = file_path.lower()
    try:
        if ext.endswith('.mp3'):
            audio = EasyID3(file_path)
            return audio['artist'][0] if 'artist' in audio else None
        elif ext.endswith('.flac'):
            audio = FLAC(file_path)
            return audio['artist'][0] if 'artist' in audio else None
        elif ext.endswith(('.m4a', '.mp4')):
            audio = MP4(file_path)
            return (audio.tags or {}).get('\xa9ART', [None])[0]
        else:
            audio = MutagenFile(file_path, easy=True)
            if audio and 'artist' in audio:
                return audio['artist'][0]
    except Exception:
        pass
    return None


def _write_tags(
    file_path: str,
    new_artist: str | None,
    track_number: str | None,
    cover_image_path: str | None,
):
    """Write artist, track number, and cover art. Preserves all other tags."""
    ext = file_path.lower()
    try:
        # ── MP3 ────────────────────────────────────────────────────────────
        if ext.endswith('.mp3'):
            try:
                easy = EasyID3(file_path)
            except Exception:
                easy = EasyID3()
                easy.save(file_path)
                easy = EasyID3(file_path)

            if new_artist:
                easy['artist'] = new_artist
            if track_number:
                easy['tracknumber'] = track_number
            easy.save()

            # Cover art requires ID3 raw
            if cover_image_path:
                tags = ID3(file_path)
                tags.delall('APIC')
                mime, pic_type = _cover_mime(cover_image_path)
                with open(cover_image_path, 'rb') as f:
                    img_data = f.read()
                tags.add(APIC(
                    encoding=3, mime=mime, type=3,
                    desc='Cover', data=img_data
                ))
                tags.save(v2_version=3)

        # ── FLAC ───────────────────────────────────────────────────────────
        elif ext.endswith('.flac'):
            audio = FLAC(file_path)
            if new_artist:
                audio['artist'] = new_artist
            if track_number:
                audio['tracknumber'] = track_number
            if cover_image_path:
                audio.clear_pictures()
                pic = Picture()
                pic.type = 3
                pic.mime, _ = _cover_mime(cover_image_path)
                with open(cover_image_path, 'rb') as f:
                    pic.data = f.read()
                pic.desc = 'Cover'
                audio.add_picture(pic)
            audio.save()

        # ── M4A / MP4 ──────────────────────────────────────────────────────
        elif ext.endswith(('.m4a', '.mp4')):
            try:
                audio = MP4(file_path)
                if not audio.tags:
                    audio.add_tags()
                if new_artist:
                    audio.tags['\xa9ART'] = [new_artist]
                if track_number:
                    audio.tags['trkn'] = [(int(track_number), 0)]
                if cover_image_path:
                    with open(cover_image_path, 'rb') as f:
                        img_data = f.read()
                    _, pic_type = _cover_mime(cover_image_path)
                    fmt = MP4Cover.FORMAT_PNG if pic_type == 'png' else MP4Cover.FORMAT_JPEG
                    audio.tags['covr'] = [MP4Cover(img_data, fmt)]
                audio.save()
            except MP4StreamInfoError as e:
                print(f"  [ERR ] Invalid MP4: {file_path}: {e}")
                return False

        # ── Other formats ──────────────────────────────────────────────────
        else:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                print(f"  [ERR ] Unsupported format: {file_path}")
                return False
            if new_artist:
                audio['artist'] = new_artist
            if track_number:
                audio['tracknumber'] = track_number
            audio.save()

        return True

    except Exception as e:
        print(f"  [ERR ] Write failed {file_path}: {e}")
        return False


def _cover_mime(path: str):
    ext = Path(path).suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg', 'jpeg'
    elif ext == '.png':
        return 'image/png', 'png'
    elif ext == '.webp':
        return 'image/webp', 'webp'
    return 'image/jpeg', 'jpeg'


# ══════════════════════════════════════════════════════════════════════════════
# DIRECTORY PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

VALID_EXT = ('.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac', '.wma', '.mp4')


def process_file(
    file_path: str,
    grouped: list,
    raw_dir: str,
    cover_image: str | None,
) -> tuple:
    """
    Process a single music file:
    - read artist tag
    - normalize/expand via grouped_artists
    - extract track number from filename
    - write updated tags + cover art
    Returns (file_path, orig_artist, new_artist, track_num, status)
    """
    filename = os.path.basename(file_path)
    track_num = parse_track_number(filename)
    orig_artist = _read_artist(file_path)

    if orig_artist is None:
        return (file_path, None, None, track_num, "no_artist_tag")

    new_artist = normalize_artists(orig_artist, grouped, raw_dir)

    ok = _write_tags(file_path, new_artist, track_num, cover_image)
    status = "ok" if ok else "write_error"
    return (file_path, orig_artist, new_artist, track_num, status)


def process_directory(
    directory: str,
    grouped: list,
    raw_dir: str,
):
    music_files = sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(VALID_EXT)
    )
    if not music_files:
        return

    cover = find_cover_image(directory)
    print(f"\n📁 {directory}")
    if cover:
        print(f"   🖼  Cover: {os.path.basename(cover)}")

    results = []
    # Sequential within a directory to avoid race on API calls / file writes
    for fp in music_files:
        r = process_file(fp, grouped, raw_dir, cover)
        results.append(r)
        path, orig, new, trk, status = r
        name = os.path.basename(path)
        trk_str = f"[{trk}]" if trk else "[?]"
        if status == "ok":
            if orig != new:
                print(f"   ✓ {trk_str} {name}")
                print(f"       Artist: {orig}")
                print(f"       -> {new}")
            else:
                print(f"   · {trk_str} {name}  (no change)")
        elif status == "no_artist_tag":
            print(f"   - {trk_str} {name}  (no artist tag)")
        else:
            print(f"   ✗ {trk_str} {name}  ({status})")

    return results


def scan_and_process(
    root_dir: str,
    grouped_json: str,
    raw_dir: str,
):
    grouped = load_grouped_artists(grouped_json)
    print(f"Loaded {len(grouped)} grouped artist entries.")

    start = time.time()
    total_files = 0
    total_changed = 0
    total_errors = 0

    for dirpath, _, _ in os.walk(root_dir):
        results = process_directory(dirpath, grouped, raw_dir)
        if not results:
            continue
        for _, orig, new, _, status in results:
            total_files += 1
            if status == "ok" and orig != new:
                total_changed += 1
            elif status == "write_error":
                total_errors += 1

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.2f}s")
    print(f"Files processed : {total_files}")
    print(f"Tags changed    : {total_changed}")
    print(f"Errors          : {total_errors}")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Music Tag Normaliser")
    print("="*60)

    root_dir = input("Enter root music directory: ").strip()
    if not os.path.isdir(root_dir):
        print("Error: directory not found.")
        return

    grouped_json = input(
        "Path to grouped_artists.json [default: grouped_artists.json]: "
    ).strip() or "grouped_artists.json"

    raw_dir = input(
        "Directory for raw_responses cache [default: raw_responses]: "
    ).strip() or "raw_responses"

    scan_and_process(root_dir, grouped_json, raw_dir)
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()