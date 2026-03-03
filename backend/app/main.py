import csv

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import query

logfire.configure()
logfire.instrument_google_genai()
logfire.instrument_openai()

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


@app.get("/mock")
def mock_data():
    with open(
        "./app/mock_data/ResidentWorkingPersonsAged15YearsandOverbyUsualModeofTransporttoWorkAgeGroupandSexGeneralHouseholdSurvey2015.csv",
        newline="",
    ) as f:
        csv_reader = csv.reader(f)
        csv_headings = next(csv_reader)

        return csv_headings
