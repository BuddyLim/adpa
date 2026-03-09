import csv
import json
import os
from contextlib import asynccontextmanager

import anyio
import anyio.to_thread
import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from app.router import query
from app.db import database
from app.db.models import Dataset


def _run_migrations() -> None:
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def _seed_datasets() -> None:
    async with database.AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Dataset))
        if count and count > 0:
            return

        with open("./app/mock_data/data.json", "r") as f:
            records = json.load(f)

        for record in records:
            session.add(Dataset(
                title=record["title"],
                summary=record.get("summary"),
                file_path=record["dataset_file"],
            ))

        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("/app/data", exist_ok=True)
    await anyio.to_thread.run_sync(_run_migrations)
    await _seed_datasets()
    yield


logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()
logfire.instrument_httpx(capture_all=True)
logfire.instrument_sqlalchemy(engine=database.engine)
app = FastAPI(lifespan=lifespan)

logfire.instrument_fastapi(app)

origins = os.getenv("CORS_ORIGIN", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

app.include_router(query.router)


@app.get("/")
def root():
    return {"message": "Hello from APDA!"}


@app.get("/display_mock_data")
def mock_data():
    with open("./app/mock_data/data.json", "r") as file:
        # Parse the JSON data into a Python dictionary
        data = json.load(file)

        return data
