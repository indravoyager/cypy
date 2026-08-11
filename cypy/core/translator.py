import os
import cv2
import time
import json
import re
import fitz
import zipfile
import shutil
import threading
import traceback
import uuid
import numpy as np
try:
    import rarfile
except ImportError:
    rarfile = None
from PIL import Image, ImageDraw, ImageFont, ImageFilter
Image.init()

from cypy.core.yolo_onnx import YOLOONNX as YOLO
from cypy.core.providers.base import ProviderError
import cypy.core.config as config
from cypy.core.services.rate_limiter import rate_limiter
from cypy.core.services.image_service import (
    bersihkan_json_dari_gemini,
    buang_kotak_raksasa_palsu,
    gabung_kotak_tumpang_tindih, buang_kotak_ngawur, buang_kotak_sfx_dan_gambar,
    buat_crop_lega_tapi_tidak_nyamber, mask_luar_box_utama, tulis_teks_di_balon,
    imwrite_safe, chunk_crop_list
)


def natural_sort_key(s):
    """
    Key for natural numerical sorting (e.g. page1.png, page2.png, page10.png).
    Splits string into text and integer components.
    """
    filename = os.path.basename(str(s))
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]


def _get_lang_code(target_language):
    """Get language code from target language name."""
    lang_str = str(target_language) if target_language else "Indonesian"
    return config.LANG_CODES.get(lang_str.lower(), lang_str[:2].lower())


def _make_output_path(input_path, target_language, output_ext=".png"):
    """Generate output path with language-code subfolder.

    Example: manga/page1.png -> manga/ID/page1.png
    """
    lang_code = _get_lang_code(target_language)
    lang_code_upper = lang_code.upper()

    dir_name = os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    name_without_ext = os.path.splitext(base_name)[0]

    output_dir = os.path.join(dir_name, lang_code_upper)
    os.makedirs(output_dir, exist_ok=True)

    return os.path.join(output_dir, f"{name_without_ext}{output_ext}")


yolo_lock = threading.Lock()


def _composite_translations(main_image_pil, main_draw, coordinate_map, translations,
                            img_width, img_height, target_language):
    """Draw translated text back onto the page, skipping SKIP/empty and odd boxes."""
    for num, text in translations.items():
        if num not in coordinate_map:
            continue
        if text.upper() == "SKIP" and text.strip() != "":
            continue
        if text.strip() == "":
            continue

        x1, y1, x2, y2 = coordinate_map[num]
        w, h = max(1, x2 - x1), max(1, y2 - y1)
        ratio = w / float(h)
        area_ratio = (w * h) / float(max(1, img_width * img_height))

        if ratio >= 3.2 and w >= img_width * 0.35:
            continue
        if area_ratio >= 0.035 and ratio >= 2.8:
            continue

        suspicious_flat_box = (
            ratio >= config.RASIO_BOX_GEPENG
            and w >= img_width * config.LEBAR_BOX_GEPENG_RATIO
            and h <= img_height * config.TINGGI_BOX_GEPENG_RATIO
        )

        if config.PAKAI_PATCH_UNTUK_BOX_GEPENG and suspicious_flat_box:
            tulis_teks_di_balon(
                main_draw, text, x1, y1, x2, y2,
                background_patch=True, target_language=target_language
            )
        else:
            margin_x = int((x2 - x1) * config.MASK_MARGIN_RATIO)
            margin_y = int((y2 - y1) * config.MASK_MARGIN_RATIO)
            margin_x = min(margin_x, (x2 - x1) // 2)
            margin_y = min(margin_y, (y2 - y1) // 2)

            overlay = Image.new("RGBA", main_image_pil.size, (255, 255, 255, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            corner_radius = max(6, min(max(1, x2 - x1), max(1, y2 - y1)) // 3)
            try:
                draw_overlay.rounded_rectangle(
                    [x1 + margin_x, y1 + margin_y, x2 - margin_x, y2 - margin_y],
                    radius=corner_radius,
                    fill=(255, 255, 255, 255)
                )
            except Exception:
                draw_overlay.rectangle(
                    [x1 + margin_x, y1 + margin_y, x2 - margin_x, y2 - margin_y],
                    fill=(255, 255, 255, 255)
                )
            overlay_blurred = overlay.filter(ImageFilter.GaussianBlur(radius=3))
            main_image_pil.paste(overlay_blurred, (0, 0), overlay_blurred)

            tulis_teks_di_balon(
                main_draw, text, x1, y1, x2, y2,
                background_patch=False, target_language=target_language
            )


def translate_mosaic(mosaic_image_pil, provider, target_language="Indonesian", max_retry=3):
    """Sends a single mosaic image to the LLM provider for translation with rate limiting & retries."""
    if not provider.validate_api_key():
        print(f"\n[!] API key for {provider.provider_name} is missing or empty!")
        return {}

    lang_str = str(target_language) if target_language else "Indonesian"
    examples = {
        "english": ("Hello!", "Mother... wait..."),
        "indonesian": ("Cepat bangun!", "Ibu... tunggu..."),
        "japanese": ("早く起きて！", "お母さん…待って…"),
        "mandarin": ("快点起床！", "妈妈……等等……"),
        "spanish": ("¡Despierta rápido!", "Madre... espera..."),
        "portuguese": ("Acorde rápido!", "Mãe... espere..."),
        "javanese": ("Ndang tangi!", "Ibu... enteni..."),
    }
    lang_key = lang_str.lower()
    example_val_1, example_val_3 = examples.get(lang_key, (examples["english"][0], examples["english"][1]))

    prompt = (
        f"You are an accurate, literal manga translator from its original language to {lang_str}. "
        "The image contains several speech bubbles arranged vertically. "
        "Each bubble is prefixed with a LARGE RED NUMBER on its left as its ID. \n\n"

        "MAIN TASK:\n"
        f"Read the text in each bubble, then translate it into {lang_str}, faithfully preserving the original meaning. \n\n"

        "VERTICAL READING RULES:\n"
        "1. Read vertical text from top to bottom. \n"
        "2. If there are multiple vertical columns, read the rightmost column first, then move left. \n"
        "3. Do not reverse column orders. \n"
        "4. Do not mix text between bubbles. \n\n"

        "TRANSLATION RULES:\n"
        "1. Translate literally and accurately. Do not make it overly polite, do not summarize, and do not invent content. \n"
        "2. Do not add subjects or objects not present in the original text. \n"
        "3. Do not alter the relationships between characters. \n"
        "4. If the text is rude, explicit, teasing, degrading, bashful, or begging, maintain that exact tone. \n"
        f"5. If the text contains a question, the {lang_str} output must also be a question. \n"
        "6. Do not create new sentences that sound unnatural if they are not in the original text. \n"
        "7. For long sentences, keep all parts of the meaning. Do not truncate. \n"
        "8. If unsure about some text, use [?] for that part. \n"
        "9. If the bubble only contains SFX, scribbles, is empty, or is background art and not a meaningful dialogue, reply with 'SKIP'. \n\n"

        "HONORIFICS RULE:\n"
        "1. If the original text contains Japanese honorifics (san, kun, chan, sama, senpai, sensei, etc.), "
        "keep them as-is in the translation. Do NOT translate honorifics. \n"
        "2. Examples: -san stays as -san, -kun stays as -kun, -chan stays as -chan. \n"
        "3. This applies even when translating to non-Japanese languages. \n\n"

        "SFX RULE:\n"
        "1. If a bubble contains ONLY sound effects (SFX) with no dialogue, reply with 'SKIP'. \n"
        "2. SFX examples: ドドド, ゴゴゴ, バキ, ギュウ, キラキラ, etc. \n"
        "3. If a bubble has BOTH dialogue and SFX, translate only the dialogue part. \n\n"

        "RETURN ALL IDs RULE:\n"
        "1. You MUST return a JSON entry for EVERY red ID number visible in the image. \n"
        "2. Do NOT skip any ID numbers. If ID 1, 2, 3, 4, 5 are visible, your JSON must contain all 5 keys. \n"
        "3. For IDs you cannot read or translate, use 'SKIP' as the value. \n"
        "4. This is critical - missing IDs will cause errors. \n\n"

        "OUTPUT FORMAT:\n"
        "Provide the response ONLY in valid JSON without markdown formatting. \n"
        "Keys must be the red ID numbers as strings. \n"
        f"Values must be the {lang_str} translation or 'SKIP'. \n"
        f'Example output: {{"1": "{example_val_1}", "2": "SKIP", "3": "{example_val_3}", "4": "SKIP", "5": "{example_val_1}"}}'
    )

    def do_call():
        raw_text = provider.translate_image(mosaic_image_pil, prompt)
        if not raw_text:
            return {}
        cleaned = bersihkan_json_dari_gemini(raw_text)
        return json.loads(cleaned)

    try:
        result = rate_limiter.execute_with_retry(
            api_call=do_call,
            provider_name=provider.provider_name,
            max_retries=max_retry,
        )
        return result or {}
    except ProviderError:
        print(f"\n[!] API key for {provider.provider_name} is expired or invalid.")
        return {}
    except Exception as e:
        traceback.print_exc()
        print(f"\n[!] {provider.provider_name} request failed: {e}")
        return {}


def shrink_crop_list_if_mosaic_too_tall(
    crop_list,
    max_mosaic_height=6000,
    crop_spacing=10,
    padding_top_bottom=20
):
    """
    Shrinks panels before constructing the mosaic if it exceeds the max height limit.
    Red IDs are drawn post-resize so they remain perfectly clear.
    """
    if not crop_list:
        return crop_list

    crop_count = len(crop_list)
    total_image_height = sum(p.height for _, p in crop_list)
    total_space_height = crop_count * crop_spacing + padding_top_bottom
    initial_mosaic_height = total_image_height + total_space_height

    if initial_mosaic_height <= max_mosaic_height:
        return crop_list

    target_image_height = max(1, max_mosaic_height - total_space_height)
    ratio = target_image_height / float(total_image_height)

    new_list = []

    for num, crop in crop_list:
        new_width = max(1, int(crop.width * ratio))
        new_height = max(1, int(crop.height * ratio))

        new_crop = crop.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

        new_list.append((num, new_crop))

    return new_list


def process_single_image(image_path, yolo_model, provider, target_language="Indonesian"):
    """Processes a single manga page. Splits landscape images into two pages automatically."""
    if config.CANCEL_TRANSLATION:
        return None
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("[!] Image file is corrupt or unreadable.")
        return None

    img_height, img_width = img.shape[:2]
    ratio = img_width / img_height

    # Auto-Split Landscape (two or more pages)
    if ratio > 1.2:
        num_splits = max(2, round(ratio / 0.71))
        print(f"  [Auto-Split] Wide image detected (ratio {ratio:.2f}). Splitting into {num_splits} parts...")

        split_width = img_width // num_splits
        splits = []
        try:
            for i in range(num_splits):
                x_end = img_width - (i * split_width)
                x_start = x_end - split_width
                if i == num_splits - 1:
                    x_start = 0

                img_part = img[:, x_start:x_end]
                part_path = image_path.rsplit(".", 1)[0] + f"_split{i+1}.png"
                imwrite_safe(part_path, img_part)

                print(f"  Translating Part {i+1} (Right-to-Left)...")
                res_path = _process_single_image_core(part_path, yolo_model, provider, target_language)
                splits.append((res_path, part_path))

            valid_res = [res for res, _ in splits if res]
            if len(valid_res) == num_splits:
                img_results = [cv2.imdecode(np.fromfile(res, dtype=np.uint8), cv2.IMREAD_COLOR) for res in valid_res]
                img_results.reverse()

                target_h = max(img.shape[0] for img in img_results)
                for i in range(len(img_results)):
                    h, w = img_results[i].shape[:2]
                    if h != target_h:
                        img_results[i] = cv2.resize(img_results[i], (int(w * target_h / h), target_h))

                combined = cv2.hconcat(img_results)
                output_path = _make_output_path(image_path, target_language)
                imwrite_safe(output_path, combined)
                return output_path
        finally:
            for res_path, part_path in splits:
                if res_path:
                    try: os.remove(res_path)
                    except Exception: pass
                if part_path:
                    try: os.remove(part_path)
                    except Exception: pass

    return _process_single_image_core(image_path, yolo_model, provider, target_language)


def _process_single_image_core(image_path, yolo_model, provider, target_language="Indonesian"):
    """Core processing function for a single manga page."""
    if config.CANCEL_TRANSLATION:
        return None

    print(f"\nTranslating: {os.path.basename(image_path)}")

    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("[!] Image file is corrupt or unreadable.")
        return None

    main_image_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    main_draw = ImageDraw.Draw(main_image_pil)
    img_height, img_width = img.shape[:2]

    prediction_stages = [
        {"conf": 0.28, "iou": 0.45},
        {"conf": 0.18, "iou": 0.55},
        {"conf": 0.10, "iou": 0.65}
    ]

    raw_boxes = []
    for stage in prediction_stages:
        with yolo_lock:
            temp_results = yolo_model.predict(
                source=img,
                conf=stage["conf"],
                iou=stage["iou"],
                verbose=False
            )

        for box in temp_results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            raw_boxes.append([x1, y1, x2, y2])

    filtered_boxes = buang_kotak_raksasa_palsu(raw_boxes)
    filtered_boxes = gabung_kotak_tumpang_tindih(filtered_boxes)
    filtered_boxes = buang_kotak_ngawur(filtered_boxes, img_width, img_height)
    filtered_boxes = buang_kotak_sfx_dan_gambar(
        img=img,
        boxes=filtered_boxes,
        image_name=image_path
    )

    crop_list = []
    coordinate_map = {}

    for order, (x1, y1, x2, y2) in enumerate(filtered_boxes, start=1):
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)

        pad_x = max(config.MIN_PAD, int(box_w * config.PAD_X_RATIO))
        pad_y = max(config.MIN_PAD, int(box_h * config.PAD_Y_RATIO))

        crop_x1, crop_y1, crop_x2, crop_y2 = buat_crop_lega_tapi_tidak_nyamber(
            [x1, y1, x2, y2],
            filtered_boxes,
            img_width,
            img_height,
            pad_x,
            pad_y
        )

        crop = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()
        if crop.size == 0:
            continue

        crop = mask_luar_box_utama(
            crop,
            crop_x1,
            crop_y1,
            x1,
            y1,
            x2,
            y2
        )

        crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        if config.SKALA_POTONGAN_MOSAIK != 1:
            new_size = (
                max(1, int(crop_pil.width * config.SKALA_POTONGAN_MOSAIK)),
                max(1, int(crop_pil.height * config.SKALA_POTONGAN_MOSAIK))
            )
            crop_pil = crop_pil.resize(
                new_size,
                Image.Resampling.LANCZOS
            )

        crop_list.append((str(order), crop_pil))
        coordinate_map[str(order)] = (x1, y1, x2, y2)

    total_bubbles = len(crop_list)

    if total_bubbles == 0:
        print("  No text bubbles found.")
        output_path = _make_output_path(image_path, target_language)
        main_image_pil.save(output_path)
        return output_path

    print(f"  Found {total_bubbles} speech bubbles...")

    # --- BUBBLE CHUNKING (Max 20 Bubbles per Request) ---
    max_per_batch = getattr(config, "max_bubbles_per_request", 20)
    crop_chunks = chunk_crop_list(crop_list, max_per_batch)
    combined_translations = {}

    left_number_margin = config.MARGIN_KIRI_NOMOR
    right_margin = config.MARGIN_KANAN
    crop_spacing = config.JARAK_ANTAR_POTONGAN

    for chunk_idx, chunk_crops in enumerate(crop_chunks, start=1):
        if config.CANCEL_TRANSLATION:
            return None

        if len(crop_chunks) > 1:
            print(f"  [Chunk {chunk_idx}/{len(crop_chunks)}] Processing bubbles {chunk_crops[0][0]}..{chunk_crops[-1][0]} ({len(chunk_crops)} bubbles)...")

        shrunk_crops = shrink_crop_list_if_mosaic_too_tall(
            chunk_crops,
            max_mosaic_height=config.MAX_TINGGI_MOSAIK,
            crop_spacing=crop_spacing,
            padding_top_bottom=20
        )

        mosaic_width = max(
            config.LEBAR_MOSAIK_MIN,
            max([p.width for _, p in shrunk_crops]) + left_number_margin + right_margin
        )

        mosaic_height = (
            sum([p.height for _, p in shrunk_crops])
            + (len(shrunk_crops) * crop_spacing)
            + 20
        )

        mosaic_canvas = Image.new(
            "RGB",
            (mosaic_width, mosaic_height),
            color=(255, 255, 255)
        )
        mosaic_draw = ImageDraw.Draw(mosaic_canvas)
        y_offset = 10

        number_font = ImageFont.load_default()
        try:
            number_font = ImageFont.truetype(config.FONT_MANGA, 40)
        except Exception:
            pass

        for num, crop in shrunk_crops:
            mosaic_draw.text(
                (5, y_offset + (crop.height // 2) - 20),
                num,
                fill=(255, 0, 0),
                font=number_font
            )
            mosaic_canvas.paste(crop, (left_number_margin, y_offset))
            y_offset += crop.height + crop_spacing

        print(f"  Translating with {provider.provider_name} ({provider.model_name})...")
        chunk_result = translate_mosaic(mosaic_canvas, provider=provider, target_language=target_language)

        if chunk_result:
            combined_translations.update(chunk_result)

    if not combined_translations:
        print("  [!] Translation failed.")
        return None

    if config.MANUAL_TRANSLATION_OVERRIDE:
        combined_translations.update(config.MANUAL_TRANSLATION_OVERRIDE)

    _composite_translations(
        main_image_pil, main_draw, coordinate_map, combined_translations,
        img_width, img_height, target_language
    )

    output_path = _make_output_path(image_path, target_language)
    main_image_pil.save(output_path)
    return output_path


def process_image_batch(image_paths, yolo_model, provider, target_language="Indonesian"):
    """
    Translates a list of image paths using Multi-Page Mosaic Batching.
    Stitches speech bubbles from multiple pages into combined mosaic requests (max 20 bubbles/request).
    Dramatically reduces API calls by 70-80% and eliminates rate limit errors!
    """
    if not image_paths:
        return []

    total_images = len(image_paths)
    print(f"\n[Multi-Page Batch] Processing {total_images} pages with Multi-Page Mosaic Batching...")

    page_data = []
    untranslated_crops = []

    for p_idx, img_path in enumerate(image_paths):
        if config.CANCEL_TRANSLATION:
            return []

        expected_output = _make_output_path(img_path, target_language)
        if os.path.exists(expected_output):
            print(f"  [{p_idx+1}/{total_images}] Skipping {os.path.basename(img_path)} (Already translated).")
            page_data.append({'path': img_path, 'already_done': True, 'output_path': expected_output})
            continue

        img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"  [!] Failed to read {os.path.basename(img_path)}")
            page_data.append({'path': img_path, 'already_done': False, 'failed': True})
            continue

        img_height, img_width = img.shape[:2]
        main_image_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        prediction_stages = [
            {"conf": 0.28, "iou": 0.45},
            {"conf": 0.18, "iou": 0.55},
            {"conf": 0.10, "iou": 0.65}
        ]
        raw_boxes = []
        for stage in prediction_stages:
            with yolo_lock:
                temp_results = yolo_model.predict(
                    source=img,
                    conf=stage["conf"],
                    iou=stage["iou"],
                    verbose=False
                )
            for box in temp_results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                raw_boxes.append([x1, y1, x2, y2])

        filtered_boxes = buang_kotak_raksasa_palsu(raw_boxes)
        filtered_boxes = gabung_kotak_tumpang_tindih(filtered_boxes)
        filtered_boxes = buang_kotak_ngawur(filtered_boxes, img_width, img_height)
        filtered_boxes = buang_kotak_sfx_dan_gambar(img=img, boxes=filtered_boxes, image_name=img_path)

        page_entry = {
            'path': img_path,
            'img': img,
            'pil': main_image_pil,
            'draw': ImageDraw.Draw(main_image_pil),
            'img_width': img_width,
            'img_height': img_height,
            'boxes': filtered_boxes,
            'translations': {},
            'already_done': False,
            'failed': False
        }

        page_crops = []
        for b_idx, (x1, y1, x2, y2) in enumerate(filtered_boxes, start=1):
            box_w = max(1, x2 - x1)
            box_h = max(1, y2 - y1)

            pad_x = max(config.MIN_PAD, int(box_w * config.PAD_X_RATIO))
            pad_y = max(config.MIN_PAD, int(box_h * config.PAD_Y_RATIO))

            crop_x1, crop_y1, crop_x2, crop_y2 = buat_crop_lega_tapi_tidak_nyamber(
                [x1, y1, x2, y2], filtered_boxes, img_width, img_height, pad_x, pad_y
            )

            crop = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()
            if crop.size == 0:
                continue

            crop = mask_luar_box_utama(crop, crop_x1, crop_y1, x1, y1, x2, y2)
            crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

            if config.SKALA_POTONGAN_MOSAIK != 1:
                new_size = (
                    max(1, int(crop_pil.width * config.SKALA_POTONGAN_MOSAIK)),
                    max(1, int(crop_pil.height * config.SKALA_POTONGAN_MOSAIK))
                )
                crop_pil = crop_pil.resize(new_size, Image.Resampling.LANCZOS)

            global_id = f"{p_idx}_{b_idx}"
            untranslated_crops.append((global_id, crop_pil, p_idx, b_idx, (x1, y1, x2, y2)))
            page_crops.append((str(b_idx), crop_pil, (x1, y1, x2, y2)))

        page_entry['page_crops'] = page_crops
        page_data.append(page_entry)

    total_untranslated = len(untranslated_crops)
    print(f"[Multi-Page Batch] Extracted {total_untranslated} speech bubbles across {total_images} pages.")

    if total_untranslated > 0:
        max_per_batch = getattr(config, "max_bubbles_per_request", 20)
        crop_chunks = []
        for i in range(0, total_untranslated, max_per_batch):
            crop_chunks.append(untranslated_crops[i:i + max_per_batch])

        total_chunks = len(crop_chunks)
        print(f"[Multi-Page Batch] Stitching into {total_chunks} mosaic requests (max {max_per_batch} bubbles/request)...")

        left_number_margin = config.MARGIN_KIRI_NOMOR
        right_margin = config.MARGIN_KANAN
        crop_spacing = config.JARAK_ANTAR_POTONGAN

        for chunk_idx, chunk_items in enumerate(crop_chunks, start=1):
            if config.CANCEL_TRANSLATION:
                return []

            local_crops_for_mosaic = []
            id_mapping = {}

            for local_idx, (global_id, crop_pil, p_idx, b_idx, box) in enumerate(chunk_items, start=1):
                local_id_str = str(local_idx)
                local_crops_for_mosaic.append((local_id_str, crop_pil))
                id_mapping[local_id_str] = (p_idx, b_idx)

            shrunk_crops = shrink_crop_list_if_mosaic_too_tall(
                local_crops_for_mosaic,
                max_mosaic_height=config.MAX_TINGGI_MOSAIK,
                crop_spacing=crop_spacing,
                padding_top_bottom=20
            )

            mosaic_width = max(
                config.LEBAR_MOSAIK_MIN,
                max([p.width for _, p in shrunk_crops]) + left_number_margin + right_margin
            )
            mosaic_height = (
                sum([p.height for _, p in shrunk_crops])
                + (len(shrunk_crops) * crop_spacing)
                + 20
            )

            mosaic_canvas = Image.new("RGB", (mosaic_width, mosaic_height), color=(255, 255, 255))
            mosaic_draw = ImageDraw.Draw(mosaic_canvas)
            y_offset = 10

            number_font = ImageFont.load_default()
            try:
                number_font = ImageFont.truetype(config.FONT_MANGA, 40)
            except Exception:
                pass

            for num, crop in shrunk_crops:
                mosaic_draw.text(
                    (5, y_offset + (crop.height // 2) - 20),
                    num,
                    fill=(255, 0, 0),
                    font=number_font
                )
                mosaic_canvas.paste(crop, (left_number_margin, y_offset))
                y_offset += crop.height + crop_spacing

            print(f"  [Request {chunk_idx}/{total_chunks}] Translating {len(shrunk_crops)} bubbles with {provider.provider_name}...")
            chunk_result = translate_mosaic(mosaic_canvas, provider=provider, target_language=target_language)

            if chunk_result:
                for local_id, text in chunk_result.items():
                    if local_id in id_mapping:
                        p_idx, b_idx = id_mapping[local_id]
                        page_data[p_idx]['translations'][str(b_idx)] = text

    final_output_paths = [None] * total_images

    for p_idx, page in enumerate(page_data):
        if page.get('already_done'):
            final_output_paths[p_idx] = page['output_path']
            continue
        if page.get('failed'):
            continue

        main_image_pil = page['pil']
        main_draw = page['draw']
        img_width = page['img_width']
        img_height = page['img_height']
        translations = page['translations']
        coordinate_map = {str(b_idx): box for b_idx, (_, _, box) in enumerate(page['page_crops'], start=1)}

        if config.MANUAL_TRANSLATION_OVERRIDE:
            translations.update(config.MANUAL_TRANSLATION_OVERRIDE)

        _composite_translations(
            main_image_pil, main_draw, coordinate_map, translations,
            img_width, img_height, target_language
        )

        output_path = _make_output_path(page['path'], target_language)
        main_image_pil.save(output_path)
        final_output_paths[p_idx] = output_path

    return final_output_paths


def _resolve_export_fmt(archive_path):
    """Map config export_format to actual format, resolving 'auto' from input extension."""
    fmt = config.EXPORT_FORMAT
    if fmt == "auto":
        ext = os.path.splitext(archive_path)[1].lower()
        if ext in (".cbz", ".zip"):
            return "cbz"
        if ext in (".cbr", ".rar"):
            return "cbz"
        return "pdf"
    return fmt


def _export_archive(valid_paths, out_path, fmt):
    """Export translated PNGs into a single CBZ or PDF file."""
    if fmt == "cbz":
        with zipfile.ZipFile(out_path, "w") as zf:
            for img in valid_paths:
                zf.write(img, os.path.basename(img))
        print(f"Exported CBZ: {out_path}")
    elif fmt == "pdf":
        opened = []
        try:
            for img in valid_paths:
                opened.append(Image.open(img).convert("RGB"))
            if opened:
                opened[0].save(out_path, save_all=True, append_images=opened[1:])
                print(f"Exported PDF: {out_path}")
        finally:
            for im in opened:
                try:
                    im.close()
                except Exception:
                    pass
    else:
        print(f"[!] Unknown export format: {fmt}")


def process_folder(folder_path, yolo_model, provider, target_language="Indonesian"):
    """Processes all supported images in a folder using Multi-Page Mosaic Batching."""
    supported = config.SUPPORTED_IMAGE_EXTENSIONS
    files = sorted(
        [f for f in os.listdir(folder_path) if f.lower().endswith(supported)],
        key=natural_sort_key
    )

    if not files:
        print(f"  [!] No supported image files found in: {folder_path}")
        return

    total = len(files)
    print(f"\n[Batch] Found {total} images in folder (Sorted numerically).")
    image_paths = [os.path.join(folder_path, f) for f in files]

    results = process_image_batch(image_paths, yolo_model, provider=provider, target_language=target_language)
    success = sum(1 for r in results if r)
    failed = total - success
    print(f"\n[Batch] Completed! Success: {success}, Failed: {failed}, Total: {total}")


def process_pdf(pdf_path, yolo_model, provider, target_language="Indonesian"):
    """Processes a PDF page-by-page using Multi-Page Mosaic Batching."""
    print(f"\nProcessing PDF: {os.path.basename(pdf_path)}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[!] Could not open PDF file: {e}")
        return

    temp_dir = os.path.join(config.DATA_DIR, "cypy_cache", f"pdf_temp_{uuid.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        total_pages = len(doc)
        print("Extracting PDF pages...")
        page_paths = []
        for page_num in range(total_pages):
            if config.CANCEL_TRANSLATION:
                print("\n[PDF] Extraction cancelled.")
                return
            page = doc.load_page(page_num)
            page_rect = page.rect
            max_pt = max(page_rect.width, page_rect.height)
            if max_pt > 0:
                target_pixel = 2000
                dpi = (target_pixel / max_pt) * 72
                dpi = int(max(72, min(300, dpi)))
            else:
                dpi = 300
            pix = page.get_pixmap(dpi=dpi)
            img_path = os.path.join(temp_dir, f"page_{page_num:04d}.png")
            pix.save(img_path)
            page_paths.append(img_path)

        results = process_image_batch(page_paths, yolo_model, provider=provider, target_language=target_language)

        valid_paths = [p for p in results if p and os.path.exists(p)]
        fmt = _resolve_export_fmt(pdf_path)

        if fmt != "none" and valid_paths and not config.CANCEL_TRANSLATION:
            out_path = _make_output_path(pdf_path, target_language, output_ext=f".{fmt}")
            _export_archive(valid_paths, out_path, fmt)

        if fmt == "none" and valid_paths:
            first = valid_paths[0]
            src_dir = os.path.dirname(first)
            dst_dir = os.path.join(os.path.dirname(pdf_path),
                                   os.path.basename(src_dir))
            if os.path.isdir(src_dir):
                try:
                    if os.path.exists(dst_dir):
                        shutil.rmtree(dst_dir, ignore_errors=True)
                    shutil.copytree(src_dir, dst_dir)
                    print(f"Kept PNGs: {dst_dir}")
                except Exception as e:
                    print(f"[!] Failed to copy output: {e}")

        success = len(valid_paths)
        print(f"\n[PDF] Completed! Success: {success}, Failed: {total_pages - success}, Total: {total_pages}")

    finally:
        try:
            doc.close()
        except Exception:
            pass
        shutil.rmtree(temp_dir, ignore_errors=True)


def setup_rarfile():
    if rarfile is None:
        return False
    import platform
    if shutil.which('unrar') or shutil.which('unrar.exe'):
        return True

    os_name = platform.system()
    if os_name == "Windows":
        common_paths = [
            r"C:\Program Files\WinRAR\UnRAR.exe",
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
    elif os_name == "Darwin":
        common_paths = [
            "/usr/local/bin/unrar",
            "/opt/homebrew/bin/unrar"
        ]
    else:
        common_paths = [
            "/usr/bin/unrar",
            "/usr/local/bin/unrar"
        ]

    for p in common_paths:
        if os.path.exists(p):
            rarfile.UNRAR_TOOL = p
            return True
    return False


def process_archive(archive_path, yolo_model, provider, target_language="Indonesian"):
    """Processes CBZ/ZIP/CBR/RAR archives using Multi-Page Mosaic Batching."""
    print(f"\nProcessing Archive: {os.path.basename(archive_path)}")

    is_rar = archive_path.lower().endswith(('.rar', '.cbr'))
    if is_rar and not setup_rarfile():
        print("\n[!] Error: 'rarfile' module is not installed or 'unrar' is missing.")
        print("Please ensure you have WinRAR or 7-Zip installed (or add unrar to PATH).")
        return

    temp_dir = os.path.join(config.DATA_DIR, "cypy_cache", f"archive_temp_{uuid.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)

    print("Extracting archive...")
    try:
        if is_rar:
            with rarfile.RarFile(archive_path) as rf:
                rf.extractall(temp_dir)
        else:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(temp_dir)
    except Exception as e:
        print(f"[!] Extraction failed: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    image_paths = []
    for root, _, files in os.walk(temp_dir):
        for f in files:
            if f.lower().endswith(config.SUPPORTED_IMAGE_EXTENSIONS):
                image_paths.append(os.path.join(root, f))

    image_paths.sort(key=natural_sort_key)
    total = len(image_paths)

    if total == 0:
        print("[!] No images found in archive.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    print(f"Found {total} images (Sorted numerically). Starting Multi-Page Batch translation...")
    results = process_image_batch(image_paths, yolo_model, provider=provider, target_language=target_language)

    valid_paths = [p for p in results if p and os.path.exists(p)]
    fmt = _resolve_export_fmt(archive_path)

    if fmt != "none" and valid_paths and not config.CANCEL_TRANSLATION:
        out_path = _make_output_path(archive_path, target_language, output_ext=f".{fmt}")
        _export_archive(valid_paths, out_path, fmt)

    if fmt == "none" and valid_paths:
        first = valid_paths[0]
        src_dir = os.path.dirname(first)
        dst_dir = os.path.join(os.path.dirname(archive_path),
                               os.path.basename(src_dir))
        if os.path.isdir(src_dir):
            try:
                if os.path.exists(dst_dir):
                    shutil.rmtree(dst_dir, ignore_errors=True)
                shutil.copytree(src_dir, dst_dir)
                print(f"Kept PNGs: {dst_dir}")
            except Exception as e:
                print(f"[!] Failed to copy output: {e}")

    success = len(valid_paths)
    print(f"\n[Archive] Completed! Success: {success}, Failed: {total - success}, Total: {total}")
    shutil.rmtree(temp_dir, ignore_errors=True)
