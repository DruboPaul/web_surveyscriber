import os
import pandas as pd
from typing import Dict, List, Union


class LocalStorageService:
    def __init__(self, base_dir: str = "data/outputs"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save_excel(
        self,
        data: Union[Dict, List[Dict]],
        filename: str
    ) -> str:
        """
        Save structured data to an Excel file.

        data: dict or list of dicts
        filename: e.g. "result.xlsx"
        """
        if isinstance(data, dict):
            data = [data]

        df = pd.DataFrame(data)
        output_path = os.path.join(self.base_dir, filename)
        df.to_excel(output_path, index=False)

        return output_path
