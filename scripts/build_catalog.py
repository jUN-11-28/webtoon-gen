"""
Scans tmp_images/ for existing *_text.png files and inlines the catalog
directly into webtoon/index.html and webtoon/viewer.html.

Run this after generating new images to update the viewer.

Expected directory layout:
  tmp_images/{series_id}/{episode_id}/001_S01_C01_text.png
  ...

Episode metadata (title, number) is pulled from storyboards/{series_id}/{episode_id}.json
if available; otherwise falls back to directory names.
"""
import json
import re
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
IMAGES_DIR = ROOT / "tmp_images"
STORYBOARDS_DIR = ROOT / "storyboards"
WEBTOON_DIR = ROOT / "webtoon"

HTML_FILES = [
    WEBTOON_DIR / "index.html",
    WEBTOON_DIR / "viewer.html",
]

SERIES_META = {
    "how_we_become_human": {
        "title": "우리는 그렇게 인간이 된다",
        "englishTitle": "How We Become Human",
        "description": "평범한 일상 속, 아주 조금씩 인간이 되어가는 이야기",
        "genre": ["로맨스", "일상"],
    },
    "positive_for_love": {
        "title": "사랑에 양성",
        "englishTitle": "Positive for Love",
        "description": "예상치 못한 만남이 만들어낸 예상치 못한 감정",
        "genre": ["로맨스", "청춘"],
    },
}

MARKER_RE = re.compile(
    r"<!-- CATALOG_START -->.*?<!-- CATALOG_END -->",
    re.DOTALL,
)


def read_episode_meta(series_id: str, episode_id: str) -> dict:
    json_path = STORYBOARDS_DIR / series_id / f"{episode_id}.json"
    if not json_path.exists():
        return {"number": episode_id, "title": episode_id}
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    ep = data.get("episode", {})
    return {
        "number": ep.get("number", episode_id),
        "title": ep.get("title", episode_id),
    }


def scan_images(series_id: str, episode_id: str) -> list:
    ep_dir = IMAGES_DIR / series_id / episode_id
    if not ep_dir.exists():
        return []
    files = sorted(
        f.name for f in ep_dir.iterdir()
        if f.suffix == ".png" and f.name.endswith("_text.png")
    )
    return [f"../tmp_images/{series_id}/{episode_id}/{name}" for name in files]


def build_catalog() -> dict:
    if not IMAGES_DIR.exists():
        print(f"tmp_images/ not found: {IMAGES_DIR}")
        return {"series": []}

    series_list = []

    for series_dir in sorted(IMAGES_DIR.iterdir()):
        if not series_dir.is_dir():
            continue
        series_id = series_dir.name
        meta = SERIES_META.get(series_id, {
            "title": series_id,
            "englishTitle": series_id,
            "description": "",
            "genre": [],
        })

        episodes = []
        for ep_dir in sorted(series_dir.iterdir()):
            if not ep_dir.is_dir():
                continue
            episode_id = ep_dir.name
            images = scan_images(series_id, episode_id)
            if not images:
                continue
            ep_meta = read_episode_meta(series_id, episode_id)
            episodes.append({
                "id": episode_id,
                "number": ep_meta["number"],
                "title": ep_meta["title"],
                "cutCount": len(images),
                "images": images,
            })

        if not episodes:
            continue

        series_list.append({
            "id": series_id,
            "title": meta["title"],
            "englishTitle": meta["englishTitle"],
            "description": meta["description"],
            "genre": meta["genre"],
            "episodes": episodes,
        })

    return {"series": series_list}


def inject_into_html(catalog: dict):
    json_str = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    replacement = (
        f"<!-- CATALOG_START -->"
        f"<script>const CATALOG={json_str};</script>"
        f"<!-- CATALOG_END -->"
    )

    for html_path in HTML_FILES:
        if not html_path.exists():
            print(f"  SKIP (not found): {html_path}")
            continue
        content = html_path.read_text(encoding="utf-8")
        if not MARKER_RE.search(content):
            print(f"  SKIP (no marker): {html_path.name}")
            continue
        updated = MARKER_RE.sub(replacement, content)
        html_path.write_text(updated, encoding="utf-8")
        print(f"  Updated: {html_path.name}")


def main():
    catalog = build_catalog()
    inject_into_html(catalog)

    series_list = catalog["series"]
    total_cuts = sum(ep["cutCount"] for s in series_list for ep in s["episodes"])
    total_eps = sum(len(s["episodes"]) for s in series_list)

    print(f"\nCatalog: {len(series_list)} series / {total_eps} episodes / {total_cuts} cuts")
    for s in series_list:
        for ep in s["episodes"]:
            print(f"  {s['id']} / {ep['id']}: {ep['cutCount']}컷")


if __name__ == "__main__":
    main()
