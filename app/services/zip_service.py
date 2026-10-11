from pathlib import Path
from zipfile import ZipFile
class ZipService:
    @staticmethod
    def extract(zip_path:Path, out:Path):
        out.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path) as z: z.extractall(out)
        return list(out.glob("*.pdf"))
