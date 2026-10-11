from pydantic import BaseModel
from typing import Literal
class KnowledgeUploadResponse(BaseModel):
 success:bool=True
 message:str
 data:dict
