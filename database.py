import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "qtdfp")

class Database:
    client: AsyncIOMotorClient | None = None
    db = None
    fs: AsyncIOMotorGridFSBucket | None = None

db = Database()

async def connect_db():
    db.client = AsyncIOMotorClient(MONGODB_URL)
    db.db = db.client[DATABASE_NAME]
    db.fs = AsyncIOMotorGridFSBucket(db.db)

    await db.db.files.create_index("created_at")

async def close_db():
    if db.client:
        db.client.close()

def get_db():
    return db.db

def get_fs():
    return db.fs
