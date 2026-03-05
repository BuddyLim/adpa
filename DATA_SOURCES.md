# Data source used

From data.gov.sg:

https://data.gov.sg/datasets/d_262f416196db6fef2bf31332e301857b/view
https://data.gov.sg/datasets/d_78babe3993db6c605dc64581ad644ea1/view
https://data.gov.sg/datasets/d_dbd057fd5d657016ce35644144c30489/view

# Methodology

1. Downloading these files locally into `/backend/mock_data` and copying the file contents over to the container file system
2. Initial analysis to curate title and summary for the dataset has already been created from the get go
3. On first time container start, an initial db creation and data population will happen under `backend/app/main.py/_seed_datasets`

# Rational

This approach was taken because this was the quickest way to validate the system end to end while also maintaining relevance to the original assessment.

Ideally in a production system to scale these workflows, these should happen:

- Dataset storage should be in a blob storage like S3 (in which we can configure appropriate access security)
- The application should have a dataset ingestion pipeline in which it could depend on existing agents or newer to do dataset summarisation that conforms to the db schema
- Migration of sqlite to postgres
