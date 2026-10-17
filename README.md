
# GitHub Repository Analytics Pipeline

## 1. Project Overview

This project extracts repository data from the GitHub Search API, stores the raw API response in SQLite, transforms it into structured repository records, and presents key metrics through an interactive Streamlit dashboard.

The project demonstrates API integration, pagination, retry handling, data validation, SQL-based reporting, and data visualization.

## 2. Architecture

GitHub Search API
       |
       v
Python Data Extraction
       |
       v
Raw JSON Stored in SQLite
       |
       v
Data Validation and Transformation
       |
       v
Structured Repository Table
       |
       v
SQL Reporting View and Aggregations
       |
       v
Streamlit Dashboard

## 3. Technology Stack

- Python
- GitHub REST API
- Requests
- SQLite
- SQL
- Pandas
- Streamlit
- Plotly

## 4. Data Pipeline

### Extraction

- Retrieves popular Python repositories sorted by stars.
- Fetches up to three pages, with 20 repositories per page.
- Uses request timeouts and retries for selected temporary HTTP failures.
- Checks API responses and handles detected rate-limit exhaustion.

### Raw Data Storage

The original combined API response is stored in the `raw_api_responses` table as JSON, along with its source and extraction timestamp.

### Transformation

The pipeline converts repository JSON into structured records in the `repositories` table.

Fields include:

- Repository ID and name
- Owner
- Programming language
- Stars and forks
- Open issues
- Creation and last-update timestamps
- Extraction timestamp

Records without essential identifiers are skipped. Numeric metrics are validated and default to zero when invalid.

Existing repository IDs are updated using SQLite upsert logic to avoid duplicate records.

### Reporting

The `repository_report` SQL view exposes structured repository information for reporting.

The pipeline calculates:

- Number of repositories
- Total stars
- Average stars
- Total forks

## 5. Dashboard

The Streamlit dashboard provides:

- Summary metrics
- A bar chart of the most-starred repositories
- A scatter plot comparing stars and forks
- A searchable repository table
- CSV export functionality

The dashboard reports a snapshot of the latest fetched repository data. It does not claim to measure historical star growth.

## 6. Setup Instructions

### Prerequisites

- Python 3.10 or later
- Git

### Install dependencies

Clone or download this repository, open a terminal in the project directory, and run:

```bash
python -m venv .venv
```

On Windows PowerShell, install dependencies with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux, activate the virtual environment and install dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the pipeline

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe pipeline.py
```

On macOS or Linux:

```bash
python pipeline.py
```

The pipeline creates and populates `github_analytics.db`.

### Launch the dashboard

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS or Linux:

```bash
streamlit run app.py
```

Open the local URL printed in the terminal, usually `http://localhost:8501`.

Run the pipeline at least once before opening the dashboard.

## 7. Assumptions and Trade-offs

- The project uses the free GitHub Search API and does not require an access token for its basic use.
- The pipeline fetches at most 60 repositories per run to keep the assignment small and manageable.
- API requests may fail because of network problems or rate limits; the pipeline reports failures rather than silently treating them as successful runs.
- Missing or invalid numeric metrics are set to zero. This is a simplifying assumption and may not distinguish invalid data from a genuine zero.
- SQLite is used instead of a cloud database to keep setup simple.
- The database stores the latest values for each repository ID, while raw API responses are retained for inspection.
- Star and fork counts are snapshots, not historical trends.
- The pipeline currently runs on demand rather than through a production scheduler.
- The reporting view exposes repository-level records; the summary metrics are calculated with SQL aggregation.

## 8. AI Assistance

AI assistance was used to help structure the pipeline, implement pagination and retry configuration, develop SQL transformations, and build the Streamlit dashboard.

The implementation was tested locally by running the pipeline, checking the resulting metrics, and verifying that the dashboard displayed the updated dataset.

## 9. Future Improvements

- Add automated tests for extraction, transformation, and data quality.
- Add more comprehensive handling for GitHub rate limits and malformed API responses.
- Add scheduled execution and monitoring.
- Track timestamped snapshots to analyze changes in repository popularity over time.
- Add more reporting dimensions and data-quality checks.
