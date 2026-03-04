import csv
import json

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import query

logfire.configure()

logfire.instrument_openai()
logfire.instrument_google_genai()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
