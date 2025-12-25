import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from backend.app.services.storage import LocalStorageService

load_dotenv()

# -----------------------------
# OpenAI client
# -----------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# OCR OUTPUT (mocked for test)
# -----------------------------
ocr_text = """
Subject
Date:
Today, I met Mr. John.
"""

# -----------------------------
# Prompt
# -----------------------------
prompt = f"""
Extract the person's name from the text below.

Return ONLY valid JSON.
No markdown.
No explanation.

Text:
\"\"\"
{ocr_text}
\"\"\"
"""

# -----------------------------
# OpenAI call
# -----------------------------
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": "You extract structured data."},
        {"role": "user", "content": prompt}
    ],
    temperature=0
)
print("response", response)
raw = response.choices[0].message.content.strip()

# Safety cleanup
if raw.startswith("```"):
    raw = raw.replace("```json", "").replace("```", "").strip()

data = json.loads(raw)

print("PARSED JSON:\n", data)

# -----------------------------
# SAVE TO EXCEL (via service)
# -----------------------------
storage = LocalStorageService()

output_path = storage.save_excel(
    data=data,
    filename="test_output.xlsx"
)

print(f"\nExcel file saved at: {output_path}")
