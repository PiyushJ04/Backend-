from pathlib import Path
import shutil
class StorageService:
    BASE=Path("storage/exams")
    @classmethod
    def save(cls, exam_id:str, src:Path, name:str):
        d=cls.BASE/exam_id; d.mkdir(parents=True, exist_ok=True)
        dst=d/name; shutil.copy2(src,dst); return str(dst)
