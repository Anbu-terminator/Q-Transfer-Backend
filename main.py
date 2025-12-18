from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from datetime import datetime
from bson import ObjectId
import io

from app.database import connect_db, close_db, get_db, get_fs
from app.quantum_engine import quantum_encrypt, quantum_decrypt
from app.models import EncryptedFileResponse


# =========================
# LIFESPAN (DB CONNECT)
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="Q-TDFP Backend",
    description="Quantum Entropy Trustless Data Flow Protocol",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
async def root():
    return {
        "status": "active",
        "protocol": "Q-TDFP",
        "version": "1.0.0"
    }


# =========================
# ENCRYPT ENDPOINT
# =========================

@app.post("/api/encrypt", response_model=EncryptedFileResponse)
async def encrypt_file(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    if not password or len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")

    encrypted, fingerprint, hash_val = quantum_encrypt(data, password)

    fs = get_fs()
    db = get_db()

    # Store encrypted binary in GridFS
    file_id = await fs.upload_from_stream(
        file.filename,
        io.BytesIO(encrypted)
    )

    # Store metadata separately
    await db.files.insert_one({
        "_id": file_id,
        "filename": file.filename,
        "fingerprint": fingerprint,
        "hash": hash_val,
        "original_size": len(data),
        "encrypted_size": len(encrypted),
        "created_at": datetime.utcnow()
    })

    return EncryptedFileResponse(
        id=str(file_id),
        filename=file.filename,
        original_size=len(data),
        encrypted_size=len(encrypted),
        created_at=datetime.utcnow()
    )


# =========================
# LIST FILES (OPTIONAL)
# =========================

@app.get("/api/files")
async def list_files():
    """
    Optional: used only if frontend wants to show DB files.
    Safe to keep even if not used.
    """
    db = get_db()
    files = []

    async for doc in db.files.find().sort("created_at", -1):
        files.append({
            "id": str(doc["_id"]),
            "filename": doc["filename"],
            "original_size": doc["original_size"],
            "encrypted_size": doc["encrypted_size"],
            "created_at": doc["created_at"]
        })

    return files


# =========================
# DECRYPT ENDPOINT
# =========================

@app.post("/api/decrypt/{file_id}")
async def decrypt_file(
    file_id: str,
    password: str = Form(...)
):
    if not password or len(password) < 8:
        raise HTTPException(400, "Invalid password")

    db = get_db()
    fs = get_fs()

    # 1️⃣ Fetch metadata
    meta = await db.files.find_one({"_id": ObjectId(file_id)})
    if not meta:
        raise HTTPException(404, "File not found")

    # 2️⃣ Download encrypted binary from GridFS
    encrypted_buffer = io.BytesIO()
    await fs.download_to_stream(ObjectId(file_id), encrypted_buffer)
    encrypted_buffer.seek(0)
    encrypted_data = encrypted_buffer.read()

    if not encrypted_data or len(encrypted_data) < 8:
        raise HTTPException(400, "Encrypted data corrupted")

    # 3️⃣ Quantum decrypt (binary-safe)
    decrypted = quantum_decrypt(
        encrypted=encrypted_data,
        password=password,
        expected_fingerprint=meta["fingerprint"],
        expected_hash=meta["hash"]
    )

    if decrypted is None:
        raise HTTPException(
            status_code=400,
            detail="Decryption failed: wrong password or corrupted data"
        )

    # 4️⃣ Stream back original file (NO MODIFICATION)
    return StreamingResponse(
        io.BytesIO(decrypted),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{meta["filename"]}"',
            "Content-Length": str(len(decrypted))
        }
    )


# =========================
# DELETE FILE (OPTIONAL)
# =========================

@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str):
    db = get_db()
    fs = get_fs()

    try:
        await fs.delete(ObjectId(file_id))
        await db.files.delete_one({"_id": ObjectId(file_id)})
        return {"status": "deleted"}
    except Exception:
        raise HTTPException(404, "File not found")


# =========================
# LOCAL RUN (OPTIONAL)
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
