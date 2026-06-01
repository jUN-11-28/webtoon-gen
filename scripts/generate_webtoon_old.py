import os
import json
import base64
import time
import argparse
import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def flatten_cuts(project):
    for scene in project["scenes"]:
        for cut in scene["cuts"]:
            yield scene, cut


def build_character_bible(project):
    lines = []

    for c in project.get("character_bible", []):
        lines.append(
            f"{c.get('name')}: {c.get('visual_core', '')}. "
            f"Wardrobe: {c.get('wardrobe', '')}. "
            f"Expression notes: {c.get('expression_notes', '')}."
        )

    return "\n".join(lines)


def build_prompt(project, scene, cut, with_text=False):
    character_bible = build_character_bible(project)
    style_guide = project.get("style_guide", {})
    episode = project.get("episode", {})

    dialogue_items = cut.get("dialogue", [])
    narration_items = cut.get("narration", [])
    sfx_items = cut.get("sfx", [])

    dialogue = "\n".join(
        f"- Speaker: {d.get('speaker')}\n"
        f"  Text: {d.get('text')}\n"
        f"  Bubble position: {d.get('bubble_position', 'auto')}"
        for d in dialogue_items
    )

    narration = "\n".join(
        f"- {text}" for text in narration_items
    )

    sfx = "\n".join(
        f"- {text}" for text in sfx_items
    )

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

Character bible:
{character_bible}

Style:
{episode.get("style", "")}
Color palette: {style_guide.get("color_palette", "")}
Mood: {", ".join(style_guide.get("mood_keywords", []))}

Panel rules:
- Polished Korean romance webtoon style.
- Vertical webtoon panel.
- Clean line art, soft shading, cinematic composition.
- Keep characters visually consistent.
- Make this look like a finished Korean webtoon cut.

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


def generate_image(prompt: str, output_path: Path, model: str, size: str):
    print(f"[{now()}]   Image API request started...")

    start = time.time()

    result = client.images.generate(
        model=model,
        prompt=prompt,
        size=size
    )

    elapsed_api = time.time() - start
    print(f"[{now()}]   Image API response received. Took {elapsed_api:.1f}s")

    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    output_path.write_bytes(image_bytes)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"[{now()}]   Saved locally: {output_path} ({file_size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description="Generate webtoon panel images from storyboard JSON."
    )

    parser.add_argument(
        "json_path",
        help="Path to storyboard JSON file"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all cuts"
    )

    parser.add_argument(
        "--importance",
        default="high",
        choices=["high", "medium", "low"],
        help="Generate only cuts with this importance. Default: high"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of generated cuts"
    )

    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Start from selected cut order number. Example: --start 11"
    )

    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="End at selected cut order number. Example: --end 20"
    )

    parser.add_argument(
        "--with-text",
        action="store_true",
        help="Render speech bubbles, dialogue, narration, and SFX inside the image"
    )

    parser.add_argument(
        "--model",
        default="gpt-image-2",
        help="OpenAI image model name"
    )

    parser.add_argument(
        "--size",
        default="1024x1536",
        help="Image size. Example: 1024x1536"
    )

    parser.add_argument(
        "--output-dir",
        default="tmp_images",
        help="Local output directory"
    )

    parser.add_argument(
        "--save-prompts",
        action="store_true",
        help="Save prompts as .txt files next to images"
    )

    args = parser.parse_args()

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing. Please check your .env file.")

    if args.start < 1:
        raise ValueError("--start must be 1 or higher")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    json_path = Path(args.json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as f:
        project = json.load(f)

    selected_cuts = []

    for idx, (scene, cut) in enumerate(flatten_cuts(project), start=1):
        cut_importance = cut.get("importance", "medium")

        if not args.all and cut_importance != args.importance:
            continue

        selected_cuts.append((idx, scene, cut))

    start_index = args.start - 1
    end_index = args.end

    selected_cuts = selected_cuts[start_index:end_index]

    if args.limit:
        selected_cuts = selected_cuts[:args.limit]

    total = len(selected_cuts)

    if total == 0:
        print("No cuts selected.")
        return

    results = []

    print("=" * 70)
    print(f"[{now()}] JSON: {json_path}")
    print(f"[{now()}] Output directory: {output_dir}")
    print(f"[{now()}] Model: {args.model}")
    print(f"[{now()}] Size: {args.size}")
    print(f"[{now()}] Text mode: {'ON' if args.with_text else 'OFF'}")
    print(f"[{now()}] Selected cuts: {total}")
    print("=" * 70)

    for order, (idx, scene, cut) in enumerate(selected_cuts, start=1):
        cut_start = time.time()

        cut_id = cut.get("cut_id", f"cut_{idx}")
        cut_importance = cut.get("importance", "medium")

        mode_suffix = "text" if args.with_text else "clean"
        filename = f"{idx:03d}_{cut_id}_{mode_suffix}.png"
        output_path = output_dir / filename

        prompt = build_prompt(
            project=project,
            scene=scene,
            cut=cut,
            with_text=args.with_text
        )

        print("=" * 70)
        print(f"[{now()}] Progress: {order}/{total}")
        print(f"[{now()}] Original cut order: {idx}")
        print(f"[{now()}] Cut ID: {cut_id}")
        print(f"[{now()}] Scene: {scene.get('scene_id')} - {scene.get('scene_title')}")
        print(f"[{now()}] Importance: {cut_importance}")
        print(f"[{now()}] Output: {output_path}")

        try:
            if args.save_prompts:
                prompt_path = output_dir / f"{idx:03d}_{cut_id}_{mode_suffix}.txt"
                prompt_path.write_text(prompt, encoding="utf-8")
                print(f"[{now()}]   Prompt saved: {prompt_path}")

            generate_image(
                prompt=prompt,
                output_path=output_path,
                model=args.model,
                size=args.size
            )

            elapsed_cut = time.time() - cut_start

            results.append({
                "cut_order": idx,
                "cut_id": cut_id,
                "scene_id": scene.get("scene_id"),
                "file_name": filename,
                "local_path": str(output_path),
                "importance": cut_importance,
                "with_text": args.with_text,
                "status": "success",
                "elapsed_seconds": round(elapsed_cut, 2)
            })

            print(f"[{now()}] Cut completed in {elapsed_cut:.1f}s")

        except Exception as e:
            elapsed_cut = time.time() - cut_start

            results.append({
                "cut_order": idx,
                "cut_id": cut_id,
                "scene_id": scene.get("scene_id"),
                "file_name": filename,
                "local_path": str(output_path),
                "importance": cut_importance,
                "with_text": args.with_text,
                "status": "error",
                "error": str(e),
                "elapsed_seconds": round(elapsed_cut, 2)
            })

            print(f"[{now()}] ERROR on {cut_id}: {e}")

        time.sleep(2)

    result_suffix = "text" if args.with_text else "clean"
    result_path = output_dir / f"generation_results_{result_suffix}.json"

    result_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("=" * 70)
    print(f"[{now()}] DONE")
    print(f"[{now()}] Results saved: {result_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()