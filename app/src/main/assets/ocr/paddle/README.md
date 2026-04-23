# Paddle OCR model assets

The three `.nb` files expected here are too large to commit directly. Run

```bash
scripts/download_paddle_models.sh
```

from the repo root to fetch them, along with the Paddle Lite prebuilt
runtime. The app transparently falls back to the ML Kit OCR engine when
these files are missing, so the build still works out of the box.

Expected files after the script runs:

| File                                        | Approx size |
|---------------------------------------------|-------------|
| `ch_PP-OCRv3_det_slim_opt.nb`               | 2.4 MB      |
| `ch_PP-OCRv3_rec_slim_opt.nb`               | 4.8 MB      |
| `ch_ppocr_mobile_v2.0_cls_slim_opt.nb`      | 0.6 MB      |
| `ppocr_keys_v1.txt`                         | 18 KB       |
