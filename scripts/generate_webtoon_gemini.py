import os
import json
import time
import argparse
import datetime
import threading
from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SUPPORTED_REF_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_print_lock = threading.Lock()


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def flatten_cuts(project):
    for scene in project["scenes"]:
        for cut in scene["cuts"]:
            yield scene, cut


def safe_get_list(value):
    if isinstance(value, list):
        return value
    return []


def build_character_bible(project):
    lines = []
    for c in project.get("character_bible", []):
        lines.append(
            f"{c.get('id', '')} / {c.get('name', '')}: "
            f"{c.get('visual_core', '')}. "
            f"Wardrobe: {c.get('wardrobe', '')}. "
            f"Expression notes: {c.get('expression_notes', '')}."
        )
    return "\n".join(lines)


def get_character_ids_from_cut(cut):
    return safe_get_list(cut.get("characters"))


def find_reference_file(base_dir: Path, name: str) -> Optional[Path]:
    for ext in SUPPORTED_REF_EXTENSIONS:
        candidate = base_dir / f"{name}{ext}"
        if candidate.exists():
            return candidate
    return None


def collect_character_refs(cut, character_ref_dir: Path) -> List[Path]:
    refs = []
    for character_id in get_character_ids_from_cut(cut):
        ref = find_reference_file(character_ref_dir, character_id)
        if ref:
            refs.append(ref)
    return refs


def collect_scene_ref(scene, scene_ref_dir: Path) -> List[Path]:
    scene_id = scene.get("scene_id")
    if not scene_id:
        return []
    ref = find_reference_file(scene_ref_dir, scene_id)
    return [ref] if ref else []


def build_prompt(project, scene, cut, with_text=False, has_refs=False):
    character_bible = build_character_bible(project)
    style_guide = project.get("style_guide", {})
    episode = project.get("episode", {})

    dialogue_items = safe_get_list(cut.get("dialogue"))
    narration_items = safe_get_list(cut.get("narration"))
    sfx_items = safe_get_list(cut.get("sfx"))

    dialogue = "\n".join(
        f"- Speaker: {d.get('speaker')}\n"
        f"  Text: {d.get('text')}\n"
        f"  Bubble position: {d.get('bubble_position', 'auto')}"
        for d in dialogue_items
    )

    narration = "\n".join(f"- {text}" for text in narration_items)
    sfx = "\n".join(f"- {text}" for text in sfx_items)

    if with_text:
        text_rules = """
Text rendering mode:
- Render speech bubbles directly inside the image.
- Render all Korean dialogue exactly as provided.
- Render narration as clean rectangular narration boxes.
- Render SFX as Korean comic sound effect text.
- Follow bubble_position as closely as possible.
- Korean text must be readable, clean, and correctly spelled.
- Use natural Korean webtoon typography.
- Keep speech bubbles from covering important faces.
- If there is too much text, use smaller but readable bubbles.
- Do not invent new dialogue.
- Do not translate Korean text into English.
""".strip()
        dialogue_label = "Dialogue to render inside the panel:"
        narration_label = "Narration to render inside the panel:"
        sfx_label = "SFX to render inside the panel:"
    else:
        text_rules = """
Clean artwork mode:
- Do not draw speech bubbles.
- Do not render Korean text inside the image.
- Leave clean empty space for speech bubbles.
""".strip()
        dialogue_label = "Dialogue to add later:"
        narration_label = "Narration to add later:"
        sfx_label = "SFX to add later:"

    if has_refs:
        reference_rules = """
Reference image continuity:
- Use the provided reference images for character consistency, outfit continuity, hairstyle, mask style, facial features, and scene continuity.
- Character reference images are the highest priority for facial identity.
- Scene reference images are for location, lighting, camera mood, and environmental continuity.
- If reference images conflict with the storyboard, follow the storyboard but keep character identity consistent.
""".strip()
    else:
        reference_rules = """
Reference image continuity:
- No image references are provided for this cut.
- Use the character bible and storyboard description to maintain consistency.
""".strip()

    continuity_notes = cut.get("continuity_notes", "")
    outfit_continuity = cut.get("outfit_continuity", "")
    location_continuity = cut.get("location_continuity", "")

    return f"""
Create one vertical Korean webtoon panel.

Title: {project.get("project_title", "")}
English title: {project.get("english_title", "")}
Episode: {episode.get("number", "")} - {episode.get("title", "")}
Scene: {scene.get("scene_id", "")} - {scene.get("scene_title", "")}
Cut: {cut.get("cut_id", "")}

Visual prompt:
{cut.get("visual_prompt", "")}

Camera:
{cut.get("camera", "")}

Emotion:
{cut.get("emotion", "")}

Continuity notes:
{continuity_notes if continuity_notes else "- none"}

Outfit continuity:
{outfit_continuity if outfit_continuity else "- follow character bible and previous relevant panel"}

Location continuity:
{location_continuity if location_continuity else "- follow scene and visual prompt"}

Character bible:
{character_bible}

Style:
{episode.get("style", "")}
Color palette: {style_guide.get("color_palette", "")}
Mood: {", ".join(style_guide.get("mood_keywords", []))}

Panel rules:
- Polished Korean webtoon style.
- Vertical webtoon panel.
- Clean line art, soft shading, cinematic composition.
- Keep characters visually consistent across all panels.
- Make this look like a finished Korean webtoon cut.
- Preserve story-specific details when relevant: character outfits, props, location details, mood, lighting, and emotional continuity.
{reference_rules}

{text_rules}

{dialogue_label}
{dialogue if dialogue else "- none"}

{narration_label}
{narration if narration else "- none"}

{sfx_label}
{sfx if sfx else "- none"}

Negative prompt:
{style_guide.get("global_negative_prompt", "")}
""".strip()


def _is_imagen_model(model: str) -> bool:
    return model.startswith("imagen-")


def generate_image_imagen(
    client: genai.Client,
    prompt: str,
    output_path: Path,
    model: str,
    aspect_ratio: str,
):
    tprint(f"[{now()}]   Imagen API request started")
    start = time.time()

    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
        ),
    )

    elapsed = time.time() - start
    tprint(f"[{now()}]   Imagen response received. Took {elapsed:.1f}s")

    img_bytes = response.generated_images[0].image.image_bytes
    output_path.write_bytes(img_bytes)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    tprint(f"[{now()}]   Saved: {output_path} ({file_size_mb:.2f} MB)")


def generate_image_gemini(
    client: genai.Client,
    prompt: str,
    output_path: Path,
    model: str,
    ref_paths: List[Path],
):
    mode = f"with {len(ref_paths)} ref(s)" if ref_paths else "text-only"
    tprint(f"[{now()}]   Gemini image API request started ({mode})")
    start = time.time()

    contents = []
    for ref_path in ref_paths:
        mime_type = MIME_TYPES.get(ref_path.suffix.lower(), "image/png")
        contents.append(
            types.Part.from_bytes(data=ref_path.read_bytes(), mime_type=mime_type)
        )
    contents.append(prompt)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    elapsed = time.time() - start
    tprint(f"[{now()}]   Gemini response received. Took {elapsed:.1f}s")

    image_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            break

    if image_bytes is None:
        raise RuntimeError("No image data in Gemini response")

    output_path.write_bytes(image_bytes)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    tprint(f"[{now()}]   Saved: {output_path} ({file_size_mb:.2f} MB)")


def generate_image(
    client: genai.Client,
    prompt: str,
    output_path: Path,
    model: str,
    aspect_ratio: str,
    ref_paths: List[Path],
):
    if _is_imagen_model(model):
        if ref_paths:
            tprint(f"[{now()}]   WARNING: Imagen models do not support reference images. Ignoring refs.")
        generate_image_imagen(client, prompt, output_path, model, aspect_ratio)
    else:
        generate_image_gemini(client, prompt, output_path, model, ref_paths)


def process_cut(
    client: genai.Client,
    project: dict,
    order: int,
    total: int,
    idx: int,
    scene: dict,
    cut: dict,
    output_dir: Path,
    character_ref_dir: Path,
    scene_ref_dir: Path,
    model: str,
    aspect_ratio: str,
    with_text: bool,
    use_character_refs: bool,
    use_scene_refs: bool,
    max_refs: int,
    save_prompts: bool,
) -> dict:
    cut_start = time.time()

    cut_id = cut.get("cut_id", f"cut_{idx}")
    cut_importance = cut.get("importance", "medium")
    mode_suffix = "text" if with_text else "clean"
    filename = f"{idx:03d}_{cut_id}_{mode_suffix}.png"
    output_path = output_dir / filename

    ref_paths: List[Path] = []

    if use_character_refs:
        ref_paths.extend(collect_character_refs(cut=cut, character_ref_dir=character_ref_dir))

    if use_scene_refs:
        ref_paths.extend(collect_scene_ref(scene=scene, scene_ref_dir=scene_ref_dir))

    deduped_refs = []
    seen = set()
    for path in ref_paths:
        resolved = str(path.resolve())
        if resolved not in seen:
            seen.add(resolved)
            deduped_refs.append(path)
    ref_paths = deduped_refs[:max_refs]

    prompt = build_prompt(
        project=project,
        scene=scene,
        cut=cut,
        with_text=with_text,
        has_refs=bool(ref_paths),
    )

    tprint("=" * 70)
    tprint(f"[{now()}] Progress: {order}/{total}")
    tprint(f"[{now()}] Original cut order: {idx}")
    tprint(f"[{now()}] Cut ID: {cut_id}")
    tprint(f"[{now()}] Scene: {scene.get('scene_id')} - {scene.get('scene_title')}")
    tprint(f"[{now()}] Importance: {cut_importance}")
    tprint(f"[{now()}] Output: {output_path}")

    if ref_paths:
        tprint(f"[{now()}] References:")
        for ref in ref_paths:
            tprint(f"  - {ref}")
    else:
        tprint(f"[{now()}] References: none")

    try:
        if save_prompts:
            prompt_path = output_dir / f"{idx:03d}_{cut_id}_{mode_suffix}.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
            tprint(f"[{now()}]   Prompt saved: {prompt_path}")

        generate_image(
            client=client,
            prompt=prompt,
            output_path=output_path,
            model=model,
            aspect_ratio=aspect_ratio,
            ref_paths=ref_paths,
        )

        elapsed_cut = time.time() - cut_start
        tprint(f"[{now()}] Cut completed in {elapsed_cut:.1f}s")

        return {
            "cut_order": idx,
            "cut_id": cut_id,
            "scene_id": scene.get("scene_id"),
            "file_name": filename,
            "local_path": str(output_path),
            "importance": cut_importance,
            "with_text": with_text,
            "reference_images": [str(p) for p in ref_paths],
            "status": "success",
            "elapsed_seconds": round(elapsed_cut, 2),
        }

    except Exception as e:
        elapsed_cut = time.time() - cut_start
        tprint(f"[{now()}] ERROR on {cut_id}: {e}")

        return {
            "cut_order": idx,
            "cut_id": cut_id,
            "scene_id": scene.get("scene_id"),
            "file_name": filename,
            "local_path": str(output_path),
            "importance": cut_importance,
            "with_text": with_text,
            "reference_images": [str(p) for p in ref_paths],
            "status": "error",
            "error": str(e),
            "elapsed_seconds": round(elapsed_cut, 2),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Generate webtoon panel images from storyboard JSON using Gemini."
    )

    parser.add_argument("json_path", help="Path to storyboard JSON file")

    parser.add_argument("--all", action="store_true", help="Generate all cuts")

    parser.add_argument(
        "--importance",
        default="high",
        choices=["high", "medium", "low"],
        help="Generate only cuts with this importance. Default: high",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of generated cuts",
    )

    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Start from selected cut order number. Example: --start 11",
    )

    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="End at selected cut order number. Example: --end 20",
    )

    parser.add_argument(
        "--with-text",
        action="store_true",
        help="Render speech bubbles, dialogue, narration, and SFX inside the image",
    )

    parser.add_argument(
        "--model",
        default="gemini-2.5-flash-image",
        help=(
            "Gemini model name. "
            "Gemini (supports refs): gemini-2.5-flash-image, gemini-3.1-flash-image, gemini-3-pro-image. "
            "Imagen (no refs): imagen-4.0-generate-001, imagen-4.0-fast-generate-001."
        ),
    )

    parser.add_argument(
        "--aspect-ratio",
        default="9:16",
        help="Aspect ratio for Imagen models (e.g. 9:16, 1:1). Ignored for Gemini models.",
    )

    parser.add_argument(
        "--output-dir",
        default="tmp_images",
        help="Local output directory",
    )

    parser.add_argument(
        "--save-prompts",
        action="store_true",
        help="Save prompts as .txt files next to images",
    )

    parser.add_argument(
        "--use-character-refs",
        action="store_true",
        help="Use character reference images from references/characters",
    )

    parser.add_argument(
        "--character-ref-dir",
        default="references/characters",
        help="Directory containing character reference images",
    )

    parser.add_argument(
        "--use-scene-refs",
        action="store_true",
        help="Use scene reference images from references/scenes",
    )

    parser.add_argument(
        "--scene-ref-dir",
        default="references/scenes",
        help="Directory containing scene reference images",
    )

    parser.add_argument(
        "--use-previous",
        action="store_true",
        help="Use the previous generated panel as reference (sequential mode only)",
    )

    parser.add_argument(
        "--max-refs",
        type=int,
        default=6,
        help="Maximum number of reference images to send",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers. Use 1 for sequential mode.",
    )

    args = parser.parse_args()

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing. Please check your .env file.")

    if args.start < 1:
        raise ValueError("--start must be 1 or higher")

    if args.workers > 1 and args.use_previous:
        print(
            f"[{now()}] WARNING: --use-previous is not compatible with parallel mode "
            f"(--workers {args.workers}). Disabling --use-previous."
        )
        args.use_previous = False

    client = genai.Client(api_key=GEMINI_API_KEY)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    character_ref_dir = Path(args.character_ref_dir)
    scene_ref_dir = Path(args.scene_ref_dir)

    json_path = Path(args.json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as f:
        project = json.load(f)

    all_cuts: List[Tuple[int, dict, dict]] = []
    for idx, (scene, cut) in enumerate(flatten_cuts(project), start=1):
        cut_importance = cut.get("importance", "medium")
        if not args.all and cut_importance != args.importance:
            continue
        all_cuts.append((idx, scene, cut))

    start_index = args.start - 1
    end_index = args.end
    selected_cuts = all_cuts[start_index:end_index]

    if args.limit:
        selected_cuts = selected_cuts[: args.limit]

    total = len(selected_cuts)
    if total == 0:
        print("No cuts selected.")
        return

    parallel_mode = args.workers > 1

    print("=" * 70)
    print(f"[{now()}] JSON: {json_path}")
    print(f"[{now()}] Output directory: {output_dir}")
    print(f"[{now()}] Model: {args.model}")
    if _is_imagen_model(args.model):
        print(f"[{now()}] Aspect ratio: {args.aspect_ratio}")
    print(f"[{now()}] Text mode: {'ON' if args.with_text else 'OFF'}")
    print(f"[{now()}] Character refs: {'ON' if args.use_character_refs else 'OFF'}")
    print(f"[{now()}] Scene refs: {'ON' if args.use_scene_refs else 'OFF'}")
    print(f"[{now()}] Previous panel ref: {'ON' if args.use_previous else 'OFF'}")
    print(f"[{now()}] Selected cuts: {total}")
    print(f"[{now()}] Mode: {'parallel (workers=' + str(args.workers) + ')' if parallel_mode else 'sequential'}")
    print("=" * 70)

    common_kwargs = dict(
        client=client,
        project=project,
        total=total,
        output_dir=output_dir,
        character_ref_dir=character_ref_dir,
        scene_ref_dir=scene_ref_dir,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        with_text=args.with_text,
        use_character_refs=args.use_character_refs,
        use_scene_refs=args.use_scene_refs,
        max_refs=args.max_refs,
        save_prompts=args.save_prompts,
    )

    results = []

    if not parallel_mode:
        for order, (idx, scene, cut) in enumerate(selected_cuts, start=1):
            # Sequential: support --use-previous
            if args.use_previous and order > 1:
                prev_idx, prev_scene, prev_cut = selected_cuts[order - 2]
                prev_cut_id = prev_cut.get("cut_id", f"cut_{prev_idx}")
                prev_suffix = "text" if args.with_text else "clean"
                prev_path = output_dir / f"{prev_idx:03d}_{prev_cut_id}_{prev_suffix}.png"
                if prev_path.exists():
                    cut = dict(cut)
                    # Inject previous image path via a temporary mechanism
                    cut["_previous_ref"] = prev_path

            result = process_cut(
                order=order,
                idx=idx,
                scene=scene,
                cut=cut,
                **common_kwargs,
            )
            results.append(result)
            time.sleep(1)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            for order, (idx, scene, cut) in enumerate(selected_cuts, start=1):
                future = executor.submit(
                    process_cut,
                    order=order,
                    idx=idx,
                    scene=scene,
                    cut=cut,
                    **common_kwargs,
                )
                futures[future] = order

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        results.sort(key=lambda r: r["cut_order"])

    result_suffix = "text" if args.with_text else "clean"
    result_path = output_dir / f"generation_results_{result_suffix}.json"
    result_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")

    print("=" * 70)
    print(f"[{now()}] DONE")
    print(f"[{now()}] Success: {success} / {total}  |  Failed: {failed}")
    print(f"[{now()}] Results saved: {result_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
