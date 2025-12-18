from pydantic import BaseModel
from datetime import datetime

class EncryptedFileResponse(BaseModel):
    id: str
    filename: str
    original_size: int
    encrypted_size: int
    created_at: datetime
