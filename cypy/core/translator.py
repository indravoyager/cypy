import os
import cv2
import time
import json
import fitz
import zipfile
import shutil
import concurrent.futures
import threading
import uuid
try:
    import rarfile
except ImportError:
    rarfile = None
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from ultralytics import YOLO

from cypy.core.config import (
    MODEL_YOLO, FONT_MANGA, ROOT_DIR, LANG_CODES,
    MAX_TINGGI_MOSAIK, PAD_X_RATIO, PAD_Y_RATIO, MIN_PAD, SKALA_POTONGAN_MOSAIK,
    MARGIN_KIRI_NOMOR, MARGIN_KANAN, JARAK_ANTAR_POTONGAN, LEBAR_MOSAIK_MIN,
    PAKAI_PATCH_UNTUK_BOX_GEPENG, RASIO_BOX_GEPENG, LEBAR_BOX_GEPENG_RATIO, TINGGI_BOX_GEPENG_RATIO,
    MANUAL_TRANSLATION_OVERRIDE, SUPPORTED_IMAGE_EXTENSIONS
)
from cypy.core.utils import (
    bersihkan_json_dari_gemini,
    buang_kotak_raksasa_palsu,
    gabung_kotak_tumpang_tindih, buang_kotak_ngawur, buang_kotak_sfx_dan_gambar,
    buat_crop_lega_tapi_tidak_nyamber, mask_luar_box_utama, tulis_teks_di_balon
)


yolo_lock = threading.Lock()

def terjemahkan_mosaik(gambar_mosaik_pil, provider, target_language="Indonesian", max_retry=3):
    """Sends a single mosaic image to the LLM provider for translation~ ♪"""
    for percobaan in range(max_retry):
        try:
            if not provider.validate_api_key():
                print(f"\n[!] API key for {provider.provider_name} is missing or empty!")
                return {}

            examples = {
                "english": ("Hello!", "Mother... wait..."),
                "indonesian": ("Cepat bangun!", "Ibu... tunggu..."),
                "japanese": ("早く起きて！", "お母さん…待って…"),
                "mandarin": ("快点起床！", "妈妈……等等……"),
                "spanish": ("¡Despierta rápido!", "Madre... espera..."),
                "portuguese": ("Acorde rápido!", "Mãe... espere..."),
                "javanese": ("Ndang tangi!", "Ibu... enteni..."),
            }
            lang_key = target_language.lower()
            example_val_1, example_val_3 = examples.get(lang_key, (examples["english"][0], examples["english"][1]))

            prompt = (
                f"You are an accurate, literal manga translator from its original language to {target_language}. "
                "The image contains several speech bubbles arranged vertically. "
                "Each bubble is prefixed with a LARGE RED NUMBER on its left as its ID. \n\n"

                "MAIN TASK:\n"
                f"Read the text in each bubble, then translate it into {target_language}, faithfully preserving the original meaning. \n\n"

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
                f"5. If the text contains a question, the {target_language} output must also be a question. \n"
                "6. Do not create new sentences that sound unnatural if they are not in the original text. \n"
                "7. For long sentences, keep all parts of the meaning. Do not truncate. \n"
                "8. If unsure about some text, use [?] for that part. \n"
                "9. If the bubble only contains SFX, scribbles, is empty, or is background art and not a meaningful dialogue, reply with 'SKIP'. \n\n"

                "OUTPUT FORMAT:\n"
                "Provide the response ONLY in valid JSON without markdown formatting. \n"
                "Keys must be the red ID numbers as strings. \n"
                f"Values must be the {target_language} translation. \n"
                f'Example output: {{"1": "{example_val_1}", "2": "SKIP", "3": "{example_val_3}"}}'
            )

            response_text = provider.translate_image(gambar_mosaik_pil, prompt)

            teks_json = bersihkan_json_dari_gemini(response_text)
            hasil = json.loads(teks_json)

            return hasil

        except ValueError as ve:
            if str(ve) == "API_KEY_ERROR":
                print(f"\n[!] API key for {provider.provider_name} is expired or invalid.")
                return {}
            raise ve
        except Exception as e:
            err_str = str(e).lower()
            if "api key expired" in err_str or "api_key_invalid" in err_str or "api key" in err_str or "api_key" in err_str:
                print(f"\n[!] API key for {provider.provider_name} is expired or invalid.")
                return {}
                
            if "429" in err_str or "too many requests" in err_str or "rate limit" in err_str:
                wait_time = 5 * (2 ** percobaan)
                print(f"\n[!] Rate limit hit for {provider.provider_name}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            print(f"\n[!] {provider.provider_name} error (Attempt {percobaan + 1}/{max_retry}).")

            if percobaan < max_retry - 1:
                time.sleep(10)
            else:
                print(f"  [!] Failed to connect to {provider.provider_name}.")
                return {}


def perkecil_daftar_potongan_jika_mosaik_terlalu_tinggi(
    daftar_potongan,
    max_tinggi_mosaik=6000,
    jarak_antar_potongan=10,
    padding_atas_bawah=20
):
    """
    Shrinks panels before constructing the mosaic if it exceeds the max height limit.
    Red IDs are drawn post-resize so they remain perfectly clear
    """
    if not daftar_potongan:
        return daftar_potongan

    jumlah_potongan = len(daftar_potongan)
    tinggi_gambar_total = sum(p.height for _, p in daftar_potongan)
    tinggi_spasi_total = jumlah_potongan * jarak_antar_potongan + padding_atas_bawah
    tinggi_mosaik_awal = tinggi_gambar_total + tinggi_spasi_total

    if tinggi_mosaik_awal <= max_tinggi_mosaik:
        return daftar_potongan

    tinggi_target_gambar = max(1, max_tinggi_mosaik - tinggi_spasi_total)
    rasio = tinggi_target_gambar / float(tinggi_gambar_total)

    daftar_baru = []

    for nomor, pot in daftar_potongan:
        lebar_baru = max(1, int(pot.width * rasio))
        tinggi_baru = max(1, int(pot.height * rasio))

        pot_baru = pot.resize(
            (lebar_baru, tinggi_baru),
            Image.Resampling.LANCZOS
        )

        daftar_baru.append((nomor, pot_baru))

    return daftar_baru



def proses_satu_gambar(image_path, yolo_model, provider, target_language="Indonesian"):
    """Processes a single manga page. Splits landscape images into two pages automatically~ ♪"""
    img = cv2.imread(image_path)
    if img is None:
        print("[!] Image file is corrupt or unreadable.")
        return None
        
    tinggi_img, lebar_img = img.shape[:2]
    
    ratio = lebar_img / tinggi_img
    
    # Auto-Split Landscape (Dua atau lebih Halaman)
    if ratio > 1.2:
        # Tentukan berapa halaman.
        # Rasio lebar/tinggi halaman manga standar biasanya sekitar 0,7 hingga 0,75
        num_splits = max(2, round(ratio / 0.71))
        
        print(f"  [Auto-Split] Wide image detected (ratio {ratio:.2f}). Splitting into {num_splits} parts...")
        
        split_width = lebar_img // num_splits
        
        # Manga biasanya dibaca dari kanan ke kiri, jadi bagian paling kanan adalah Halaman 1.
        splits = []
        for i in range(num_splits):
            # Hitung dari kanan ke kiri
            x_end = lebar_img - (i * split_width)
            x_start = x_end - split_width
            if i == num_splits - 1: # Pembagian terakhir (paling kiri) menghitung sisanya
                x_start = 0
                
            img_part = img[:, x_start:x_end]
            part_path = image_path.rsplit(".", 1)[0] + f"_split{i+1}.png"
            cv2.imwrite(part_path, img_part)
            
            print(f"  Translating Part {i+1} (Right-to-Left)...")
            res_path = _proses_satu_gambar_core(part_path, yolo_model, provider, target_language)
            splits.append((res_path, part_path))
            
        # Gabungkan Ulang
        valid_res = [res for res, _ in splits if res]
        if len(valid_res) == num_splits:
            # Muat semua hasil gambar
            img_results = [cv2.imread(res) for res in valid_res]
            
            # Urutannya dari kanan ke kiri. Balikkan urutan visual dari kiri ke kanan untuk hconcat.
            img_results.reverse()
            
            # Memastikan ketinggiannya sama untuk penggabungan.
            target_h = max(img.shape[0] for img in img_results)
            for i in range(len(img_results)):
                h, w = img_results[i].shape[:2]
                if h != target_h:
                    img_results[i] = cv2.resize(img_results[i], (int(w * target_h / h), target_h))
            
            combined = cv2.hconcat(img_results)
            
            lang_code = LANG_CODES.get(target_language.lower(), target_language[:2].lower() if target_language else "tr")
            suffix = f"_cypytr_{lang_code}"
            output_path = image_path.rsplit(".", 1)[0] + f"{suffix}.png"
            
            cv2.imwrite(output_path, combined)
            
            # Bersihkan hasil split
            for res_path, part_path in splits:
                try: os.remove(res_path)
                except: pass
                try: os.remove(part_path)
                except: pass
                
            return output_path
            
    # Kalau bukan gambar landscape proses aja kayak biasa
    return _proses_satu_gambar_core(image_path, yolo_model, provider, target_language)

def _proses_satu_gambar_core(image_path, yolo_model, provider, target_language="Indonesian"):
    """Core processing function for a single manga page~ ♪"""

    print(f"\nTranslating: {os.path.basename(image_path)}")

    lang_code = LANG_CODES.get(target_language.lower(), target_language[:2].lower() if target_language else "tr")
    suffix = f"_cypytr_{lang_code}"

    img = cv2.imread(image_path)

    if img is None:
        print("[!] Image file is corrupt or unreadable.")
        return None

    img_pil_utama = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw_utama = ImageDraw.Draw(img_pil_utama)

    tinggi_img, lebar_img = img.shape[:2]

    tahap_prediksi = [
        {"conf": 0.28, "iou": 0.45},
        {"conf": 0.18, "iou": 0.55},
        {"conf": 0.10, "iou": 0.65}
    ]

    kotak_mentah = []

    for tahap in tahap_prediksi:
        with yolo_lock:
            temp_results = yolo_model.predict(
                source=img,
                conf=tahap["conf"],
                iou=tahap["iou"],
                verbose=False
            )

        for box in temp_results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            kotak_mentah.append([x1, y1, x2, y2])

    kotak_matang = buang_kotak_raksasa_palsu(kotak_mentah)
    kotak_matang = gabung_kotak_tumpang_tindih(kotak_matang)
    kotak_matang = buang_kotak_ngawur(kotak_matang, lebar_img, tinggi_img)
    kotak_matang = buang_kotak_sfx_dan_gambar(
        img=img,
        boxes=kotak_matang,
        image_name=image_path
    )

    daftar_potongan = []
    koordinat_jejak = {}

    for urutan, (x1, y1, x2, y2) in enumerate(kotak_matang, start=1):
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)

        pad_x = max(MIN_PAD, int(box_w * PAD_X_RATIO))
        pad_y = max(MIN_PAD, int(box_h * PAD_Y_RATIO))

        crop_x1, crop_y1, crop_x2, crop_y2 = buat_crop_lega_tapi_tidak_nyamber(
            [x1, y1, x2, y2],
            kotak_matang,
            lebar_img,
            tinggi_img,
            pad_x,
            pad_y
        )

        potongan = img[crop_y1:crop_y2, crop_x1:crop_x2].copy()

        if potongan.size == 0:
            continue

        potongan = mask_luar_box_utama(
            potongan,
            crop_x1,
            crop_y1,
            x1,
            y1,
            x2,
            y2
        )

        potongan_pil = Image.fromarray(cv2.cvtColor(potongan, cv2.COLOR_BGR2RGB))

        if SKALA_POTONGAN_MOSAIK != 1:
            ukuran_baru = (
                max(1, int(potongan_pil.width * SKALA_POTONGAN_MOSAIK)),
                max(1, int(potongan_pil.height * SKALA_POTONGAN_MOSAIK))
            )

            potongan_pil = potongan_pil.resize(
                ukuran_baru,
                Image.Resampling.LANCZOS
            )

        daftar_potongan.append((str(urutan), potongan_pil))
        koordinat_jejak[str(urutan)] = (x1, y1, x2, y2)

    total_balon = len(daftar_potongan)

    if total_balon == 0:
        print("  No text bubbles found.")

        output_path = image_path.rsplit(".", 1)[0] + f"{suffix}.png"
        img_pil_utama.save(output_path)

        return output_path

    print(f"  Found {total_balon} speech bubbles...")

    margin_kiri_nomor = MARGIN_KIRI_NOMOR
    margin_kanan = MARGIN_KANAN
    jarak_antar_potongan = JARAK_ANTAR_POTONGAN

    daftar_potongan = perkecil_daftar_potongan_jika_mosaik_terlalu_tinggi(
        daftar_potongan,
        max_tinggi_mosaik=MAX_TINGGI_MOSAIK,
        jarak_antar_potongan=jarak_antar_potongan,
        padding_atas_bawah=20
    )

    lebar_mosaik = max(
        LEBAR_MOSAIK_MIN,
        max([p.width for _, p in daftar_potongan]) + margin_kiri_nomor + margin_kanan
    )

    tinggi_mosaik = (
        sum([p.height for _, p in daftar_potongan])
        + (total_balon * jarak_antar_potongan)
        + 20
    )

    kanvas_mosaik = Image.new(
        "RGB",
        (lebar_mosaik, tinggi_mosaik),
        color=(255, 255, 255)
    )

    draw_mosaik = ImageDraw.Draw(kanvas_mosaik)

    y_offset = 10

    font_nomor = ImageFont.load_default()

    try:
        font_nomor = ImageFont.truetype(FONT_MANGA, 40)
    except Exception:
        pass

    for nomor, pot in daftar_potongan:
        draw_mosaik.text(
            (5, y_offset + (pot.height // 2) - 20),
            nomor,
            fill=(255, 0, 0),
            font=font_nomor
        )

        kanvas_mosaik.paste(pot, (margin_kiri_nomor, y_offset))

        y_offset += pot.height + jarak_antar_potongan

    temp_mosaik_dir = os.path.join(ROOT_DIR, "cypy_cache")
    os.makedirs(temp_mosaik_dir, exist_ok=True)

    mosaik_path = os.path.join(
        temp_mosaik_dir,
        f"mosaic_preview_{os.path.basename(image_path)}"
    )

    kanvas_mosaik.save(mosaik_path)

    print(f"  Translating with {provider.provider_name} ({provider.model_name})...")

    hasil_terjemahan = terjemahkan_mosaik(kanvas_mosaik, provider=provider, target_language=target_language)

    if not hasil_terjemahan:
        print("  [!] Translation failed.")
        return None

    if MANUAL_TRANSLATION_OVERRIDE:
        hasil_terjemahan.update(MANUAL_TRANSLATION_OVERRIDE)

    for nomor, teks in hasil_terjemahan.items():
        if nomor in koordinat_jejak:
            if teks.upper() != "SKIP" and teks.strip() != "":
                x1, y1, x2, y2 = koordinat_jejak[nomor]

                w = max(1, x2 - x1)
                h = max(1, y2 - y1)
                rasio = w / float(h)
                luas_ratio = (w * h) / float(max(1, lebar_img * tinggi_img))

                if rasio >= 3.2 and w >= lebar_img * 0.35:
                    continue

                if luas_ratio >= 0.035 and rasio >= 2.8:
                    continue

                box_gepeng_mencurigakan = (
                    rasio >= RASIO_BOX_GEPENG
                    and w >= lebar_img * LEBAR_BOX_GEPENG_RATIO
                    and h <= tinggi_img * TINGGI_BOX_GEPENG_RATIO
                )

                if PAKAI_PATCH_UNTUK_BOX_GEPENG and box_gepeng_mencurigakan:
                    tulis_teks_di_balon(
                        draw_utama,
                        teks,
                        x1,
                        y1,
                        x2,
                        y2,
                        background_patch=True,
                        target_language=target_language
                    )

                else:
                    margin_x = int((x2 - x1) * 0.12)
                    margin_y = int((y2 - y1) * 0.12)

                    overlay = Image.new(
                        "RGBA",
                        img_pil_utama.size,
                        (255, 255, 255, 0)
                    )

                    draw_overlay = ImageDraw.Draw(overlay)

                    draw_overlay.ellipse(
                        [
                            x1 + margin_x,
                            y1 + margin_y,
                            x2 - margin_x,
                            y2 - margin_y
                        ],
                        fill=(255, 255, 255, 255)
                    )

                    overlay_blurred = overlay.filter(ImageFilter.GaussianBlur(radius=8))

                    img_pil_utama.paste(overlay_blurred, (0, 0), overlay_blurred)

                    tulis_teks_di_balon(
                        draw_utama,
                        teks,
                        x1,
                        y1,
                        x2,
                        y2,
                        background_patch=False,
                        target_language=target_language
                    )

    output_path = image_path.rsplit(".", 1)[0] + f"{suffix}.png"

    img_pil_utama.save(output_path)

    return output_path


def proses_folder(folder_path, yolo_model, provider, target_language="Indonesian"):
    """Processes all supported images in a folder in parallel."""
    supported = SUPPORTED_IMAGE_EXTENSIONS
    files = sorted([
        f for f in os.listdir(folder_path)
        if f.lower().endswith(supported)
    ])

    if not files:
        print(f"  [!] No supported image files found in: {folder_path}")
        return

    total = len(files)
    print(f"\n[Batch] Found {total} images in folder.")

    sukses = 0
    gagal = 0
    
    def process_file(filename, idx):
        file_path = os.path.join(folder_path, filename)
        
        # Resume Check
        lang_code = LANG_CODES.get(target_language.lower(), target_language[:2].lower() if target_language else "tr")
        suffix = f"_cypytr_{lang_code}"
        expected_output = file_path.rsplit(".", 1)[0] + f"{suffix}.png"
        
        if os.path.exists(expected_output):
            print(f"\n[{idx}/{total}] Skipping {filename} (Already translated).")
            return True

        print(f"\n[{idx}/{total}] Processing {filename}...")
        hasil = proses_satu_gambar(file_path, yolo_model, provider=provider, target_language=target_language)
        return bool(hasil)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_file, f, idx): f for idx, f in enumerate(files, start=1)}
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                sukses += 1
            else:
                gagal += 1

    print(f"\n[Batch] Completed! Success: {sukses}, Failed: {gagal}, Total: {total}")


def mulai_ritual_pdf(pdf_path, yolo_model, provider, target_language="Indonesian"):
    """Processes a PDF page-by-page concurrently, and binds them back together."""
    print(f"\nProcessing PDF: {os.path.basename(pdf_path)}")

    lang_code = LANG_CODES.get(target_language.lower(), "tr")
    suffix = f"_cypytr_{lang_code}"

    doc = fitz.open(pdf_path)

    temp_dir = os.path.join(ROOT_DIR, "cypy_cache", f"pdf_temp_{uuid.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)

    translated_images_paths = [None] * len(doc)
    total_pages = len(doc)
    
    # Save all pages first
    print("Extracting PDF pages...")
    page_paths = []
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)
        img_path = os.path.join(temp_dir, f"page_{page_num:04d}.png")
        pix.save(img_path)
        page_paths.append((page_num, img_path))
        
    def process_pdf_page(page_num, img_path):
        expected_output = img_path.rsplit(".", 1)[0] + f"{suffix}.png"
        if os.path.exists(expected_output):
            print(f"\n[PDF {page_num + 1}/{total_pages}] Skipping (Already translated).")
            return page_num, expected_output
            
        print(f"\n[PDF {page_num + 1}/{total_pages}] Translating...")
        hasil_path = proses_satu_gambar(img_path, yolo_model, provider=provider, target_language=target_language)
        return page_num, hasil_path

    print("Translating pages...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_pdf_page, p_num, p_path) for p_num, p_path in page_paths]
        for future in concurrent.futures.as_completed(futures):
            p_num, res_path = future.result()
            translated_images_paths[p_num] = res_path

    valid_paths = [p for p in translated_images_paths if p]
    if valid_paths:
        print("Saving final PDF...")
        images = [Image.open(img).convert("RGB") for img in valid_paths]
        output_pdf_path = pdf_path.rsplit(".", 1)[0] + f"{suffix}.pdf"
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
        print(f"Done! Saved at: {output_pdf_path}")

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def setup_rarfile():
    if rarfile is None:
        return False
    import shutil
    import platform
    if shutil.which('unrar') or shutil.which('unrar.exe'):
        return True
    
    os_name = platform.system()
    
    if os_name == "Windows":  # Windows
        common_paths = [
            r"C:\Program Files\WinRAR\UnRAR.exe",
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
    elif os_name == "Darwin":  # macOS
        common_paths = [
            "/usr/local/bin/unrar",
            "/opt/homebrew/bin/unrar"
        ]
    else:  # Linux
        common_paths = [
            "/usr/bin/unrar",
            "/usr/local/bin/unrar"
        ]

    for p in common_paths:
        if os.path.exists(p):
            rarfile.UNRAR_TOOL = p
            return True
    return False

def mulai_ritual_archive(archive_path, yolo_model, provider, target_language="Indonesian"):
    """Processes CBZ/ZIP/CBR/RAR archives."""
    print(f"\nProcessing Archive: {os.path.basename(archive_path)}")
    
    is_rar = archive_path.lower().endswith(('.rar', '.cbr'))
    if is_rar and not setup_rarfile():
        print("\n[!] Error: 'rarfile' module is not installed or 'unrar' is missing.")
        print("Please ensure you have WinRAR or 7-Zip installed (or add unrar to PATH).")
        print("If you just ran the update, please RESTART cypy for the module to load.")
        return
        
    if is_rar:
        print("[Info] Archive detected. Output will be saved as .pdf")

    temp_dir = os.path.join(ROOT_DIR, "cypy_cache", f"archive_temp_{uuid.uuid4().hex[:8]}")
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

    # Find all images recursively
    image_paths = []
    for root, _, files in os.walk(temp_dir):
        for f in files:
            if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                image_paths.append(os.path.join(root, f))
                
    image_paths.sort()
    total = len(image_paths)
    
    if total == 0:
        print("[!] No images found in archive.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return
        
    print(f"Found {total} images. Starting translation...")
    
    lang_code = LANG_CODES.get(target_language.lower(), target_language[:2].lower() if target_language else "tr")
    suffix = f"_cypytr_{lang_code}"
    
    translated_paths = []

    def process_arch_file(img_path, idx):
        expected_output = img_path.rsplit(".", 1)[0] + f"{suffix}.png"
        if os.path.exists(expected_output):
            print(f"\n[{idx}/{total}] Skipping (Already translated).")
            return expected_output
            
        print(f"\n[{idx}/{total}] Translating {os.path.basename(img_path)}...")
        res = proses_satu_gambar(img_path, yolo_model, provider=provider, target_language=target_language)
        return res if res else img_path # fallback to original if failed

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_arch_file, p, i): i for i, p in enumerate(image_paths, start=1)}
        for future in concurrent.futures.as_completed(futures):
            translated_paths.append(future.result())
            
    # Repack into PDF
    valid_paths = [p for p in translated_paths if p and os.path.exists(p)]
    if valid_paths:
        output_pdf_path = archive_path.rsplit(".", 1)[0] + f"{suffix}.pdf"
        print(f"\nCombining translated images into PDF...")
        images = [Image.open(img).convert("RGB") for img in valid_paths]
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
        print(f"Done! Saved at: {output_pdf_path}")
                
    shutil.rmtree(temp_dir, ignore_errors=True)

