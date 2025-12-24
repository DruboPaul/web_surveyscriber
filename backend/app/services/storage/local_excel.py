import os
import pandas as pd
from uuid import uuid4
from datetime import date

OUTPUT_DIR = "data/outputs"


def save_excel(rows: list[dict], custom_filename: str = None) -> str:
    """
    Save extracted rows to an Excel file.
    One Excel file per batch.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.DataFrame(rows)

    if custom_filename:
        # Sanitize filename (remove any path characters)
        safe_name = "".join(c for c in custom_filename if c.isalnum() or c in ('_', '-', ' '))
        filename = f"{safe_name}.xlsx"
    else:
        filename = f"batch_{uuid4().hex}.xlsx"
    
    path = os.path.join(OUTPUT_DIR, filename)

    df.to_excel(path, index=False)

    return path


def save_csv(rows: list[dict], custom_filename: str = None) -> str:
    """
    Save extracted rows to a CSV file.
    One CSV file per batch.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = pd.DataFrame(rows)

    if custom_filename:
        # Sanitize filename (remove any path characters)
        safe_name = "".join(c for c in custom_filename if c.isalnum() or c in ('_', '-', ' '))
        filename = f"{safe_name}.csv"
    else:
        filename = f"batch_{uuid4().hex}.csv"
    
    path = os.path.join(OUTPUT_DIR, filename)

    df.to_csv(path, index=False)

    return path
