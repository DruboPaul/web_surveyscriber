from paddleocr import PaddleOCR
import os

# -----------------------------
# Paths
# -----------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_PATH = os.path.join(PROJECT_ROOT, "data", "uploads", "sample1.jpg")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "ocr_output.txt")

print("Using image path:", IMAGE_PATH)
print("File exists:", os.path.exists(IMAGE_PATH))

# -----------------------------
# Initialize OCR
# -----------------------------
ocr = PaddleOCR(
    lang="en",
    use_textline_orientation=True
)

# -----------------------------
# Run OCR
# -----------------------------
result = ocr.predict(IMAGE_PATH)

print("\nOCR TEXT OUTPUT:\n")

clean_texts = []

# -----------------------------
# Parse PaddleOCR v3 output
# -----------------------------
for page in result:
    if isinstance(page, dict):
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])

        for text, score in zip(texts, scores):
            score = round(float(score), 2)

            # Filter low-confidence noise
            if score >= 0.6 and text.strip():
                print(f"{text}  ({score})")
                clean_texts.append(text)

# -----------------------------
# Save output to file
# -----------------------------
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    for line in clean_texts:
        f.write(line + "\n")

print("\nSaved cleaned OCR text to:")
print(OUTPUT_PATH)
