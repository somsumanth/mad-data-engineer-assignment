
import json
import sqlite3
import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
API_URL = "https://api.github.com/search/repositories"
DB_NAME = "github_analytics.db"
PER_PAGE = 20
MAX_PAGES = 3


def create_session():
    """Create an HTTP session with retries for temporary failures."""

    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)

    session.headers.update({
        "Accept": "application/vnd.github+json",
        "User-Agent": "MAD-Data-Engineering-Assignment",
    })

    return session


def fetch_github_repositories():
    """Fetch popular Python repositories using paginated GitHub API requests."""

    all_repositories = []
    session = create_session()

    try:
        for page in range(1, MAX_PAGES + 1):
            params = {
                "q": "language:python",
                "sort": "stars",
                "order": "desc",
                "per_page": PER_PAGE,
                "page": page,
            }

            response = session.get(
                API_URL,
                params=params,
                timeout=30,
            )

            # GitHub may use 403 to indicate a rate limit.
            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_time = response.headers.get("X-RateLimit-Reset")

                if remaining == "0":
                    if reset_time:
                        reset_at = datetime.fromtimestamp(
                            int(reset_time), tz=timezone.utc
                        )
                        raise RuntimeError(
                            f"GitHub API rate limit reached. "
                            f"Limit resets at {reset_at.isoformat()}."
                        )

                    raise RuntimeError("GitHub API rate limit reached.")

            response.raise_for_status()

            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError as error:
                raise ValueError("GitHub returned invalid JSON.") from error

            if not isinstance(data, dict):
                raise ValueError("Unexpected API response: expected a JSON object.")

            repositories = data.get("items")

            if not isinstance(repositories, list):
                raise ValueError(
                    "Unexpected API response: 'items' is not a list."
                )

            all_repositories.extend(repositories)

            print(
                f"Fetched page {page}: "
                f"{len(repositories)} repositories."
            )

            if len(repositories) < PER_PAGE:
                break

            # Small pause between pages to avoid unnecessary rapid requests.
            if page < MAX_PAGES:
                time.sleep(1)

    finally:
        session.close()

    if not all_repositories:
        raise ValueError("GitHub API returned no repositories.")

    combined_response = {
        "total_count": len(all_repositories),
        "items": all_repositories,
    }

    print(f"Total repositories fetched: {len(all_repositories)}")

    return combined_response, all_repositories


def store_raw_data(api_response):
    """Store the original combined API response in SQLite."""

    fetched_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS raw_api_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                response_json TEXT NOT NULL
            )
        """)

        connection.execute(
            """
            INSERT INTO raw_api_responses
                (source, fetched_at, response_json)
            VALUES (?, ?, ?)
            """,
            (
                "GitHub Search API",
                fetched_at,
                json.dumps(api_response),
            ),
        )

    print("Raw API response saved to SQLite.")
    return fetched_at


def safe_non_negative_int(value):
    """Convert a value to a non-negative integer, defaulting invalid values to zero."""

    if isinstance(value, bool):
        return 0

    try:
        number = int(value or 0)
        return max(0, number)
    except (TypeError, ValueError, OverflowError):
        return 0


def transform_raw_data():
    """Transform raw JSON into a structured repository table."""

    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                repo_id INTEGER PRIMARY KEY,
                repo_name TEXT NOT NULL,
                owner TEXT,
                language TEXT,
                stars INTEGER NOT NULL DEFAULT 0,
                forks INTEGER NOT NULL DEFAULT 0,
                open_issues INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                fetched_at TEXT NOT NULL
            )
        """)

        row = connection.execute(
            """
            SELECT response_json, fetched_at
            FROM raw_api_responses
            WHERE source = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("GitHub Search API",),
        ).fetchone()

        if row is None:
            raise ValueError(
                "No raw API response found. Run extraction first."
            )

        response_json, fetched_at = row

        try:
            response_data = json.loads(response_json)
        except json.JSONDecodeError as error:
            raise ValueError("Stored API response contains invalid JSON.") from error

        repositories = response_data.get("items", [])

        if not isinstance(repositories, list):
            raise ValueError("Invalid repository data in raw response.")

        valid_count = 0
        skipped_count = 0

        for repo in repositories:
            if not isinstance(repo, dict):
                skipped_count += 1
                continue

            repo_id = repo.get("id")
            repo_name = repo.get("full_name") or repo.get("name")

            # Essential fields must be present.
            if repo_id is None or not repo_name:
                skipped_count += 1
                continue

            owner_data = repo.get("owner") or {}
            owner = (
                owner_data.get("login")
                if isinstance(owner_data, dict)
                else None
            )

            connection.execute(
                """
                INSERT INTO repositories (
                    repo_id,
                    repo_name,
                    owner,
                    language,
                    stars,
                    forks,
                    open_issues,
                    created_at,
                    updated_at,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id) DO UPDATE SET
                    repo_name = excluded.repo_name,
                    owner = excluded.owner,
                    language = excluded.language,
                    stars = excluded.stars,
                    forks = excluded.forks,
                    open_issues = excluded.open_issues,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    fetched_at = excluded.fetched_at
                """,
                (
                    repo_id,
                    repo_name,
                    owner,
                    repo.get("language"),
                    safe_non_negative_int(repo.get("stargazers_count")),
                    safe_non_negative_int(repo.get("forks_count")),
                    safe_non_negative_int(repo.get("open_issues_count")),
                    repo.get("created_at"),
                    repo.get("updated_at"),
                    fetched_at,
                ),
            )

            valid_count += 1

    print(f"Cleaned and loaded {valid_count} repository records.")
    if skipped_count:
        print(f"Skipped {skipped_count} invalid repository records.")


def create_reporting_view():
    """Create a reporting-ready SQL view for repository metrics."""

    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            CREATE VIEW IF NOT EXISTS repository_report AS
            SELECT
                repo_id,
                repo_name,
                owner,
                language,
                stars,
                forks,
                open_issues,
                created_at,
                updated_at,
                fetched_at
            FROM repositories
        """)

    print("Reporting view is ready.")


def show_summary():
    """Display aggregated metrics using the reporting view."""

    with sqlite3.connect(DB_NAME) as connection:
        result = connection.execute("""
            SELECT
                COUNT(*) AS repository_count,
                COALESCE(SUM(stars), 0) AS total_stars,
                COALESCE(ROUND(AVG(stars)), 0) AS average_stars,
                COALESCE(SUM(forks), 0) AS total_forks
            FROM repository_report
        """).fetchone()

    print("\n--- Repository Summary ---")
    print(f"Repositories: {result[0]}")
    print(f"Total stars: {result[1]:,}")
    print(f"Average stars: {result[2]:,.0f}")
    print(f"Total forks: {result[3]:,}")


def main():
    """Run the complete extraction and transformation pipeline."""

    try:
        api_response, _ = fetch_github_repositories()
        store_raw_data(api_response)
        transform_raw_data()
        create_reporting_view()
        show_summary()

        print("\nPipeline completed successfully.")

    except requests.exceptions.RequestException as error:
        print(f"API request failed: {error}")

    except (ValueError, RuntimeError, sqlite3.Error, OSError) as error:
        print(f"Pipeline failed: {error}")


if __name__ == "__main__":
    main()
