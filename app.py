
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

DB_NAME = "github_analytics.db"

st.set_page_config(
    page_title="GitHub Repository Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("GitHub Repository Analytics")
st.caption(
    "Explore popular Python repositories using live GitHub API data."
)


@st.cache_data(ttl=60)
def load_data():
    """Load cleaned repository records from SQLite."""

    with sqlite3.connect(DB_NAME) as connection:
        return pd.read_sql_query(
            """
            SELECT
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
            ORDER BY stars DESC
            """,
            connection,
        )


try:
    df = load_data()

    if df.empty:
        st.warning("No repository data found. Run pipeline.py first.")
        st.stop()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Repositories", f"{len(df):,}")
    col2.metric("Total Stars", f"{df['stars'].sum():,}")
    col3.metric("Average Stars", f"{df['stars'].mean():,.0f}")
    col4.metric("Total Forks", f"{df['forks'].sum():,}")

    st.divider()

    # Chart 1: Most-starred repositories
    st.subheader("Top Repositories by Stars")

    top_n = st.slider(
        "Number of repositories to display",
        min_value=5,
        max_value=max(5, min(20, len(df))),
        value=min(10, max(5, len(df))),
    )

    top_repositories = df.nlargest(top_n, "stars")

    fig_stars = px.bar(
        top_repositories.sort_values("stars"),
        x="stars",
        y="repo_name",
        orientation="h",
        title="Most-starred Python repositories",
        labels={
            "stars": "GitHub Stars",
            "repo_name": "Repository",
        },
        hover_data=["forks", "open_issues", "owner"],
    )

    st.plotly_chart(fig_stars, width="stretch")

    # Chart 2: Stars versus forks
    st.subheader("Stars vs. Forks")

    fig_scatter = px.scatter(
        df,
        x="stars",
        y="forks",
        hover_name="repo_name",
        hover_data=["owner", "open_issues"],
        title="Repository popularity: stars and forks",
        labels={
            "stars": "GitHub Stars",
            "forks": "GitHub Forks",
        },
    )

    st.plotly_chart(fig_scatter, width="stretch")

    # Searchable repository table
    st.subheader("Repository Details")

    search = st.text_input("Search repository or owner")

    filtered_df = df.copy()

    if search:
        matches = (
            filtered_df["repo_name"].str.contains(
                search, case=False, na=False, regex=False
            )
            | filtered_df["owner"].str.contains(
                search, case=False, na=False, regex=False
            )
        )
        filtered_df = filtered_df[matches]

    st.dataframe(
        filtered_df,
        width="stretch",
        hide_index=True,
    )

    # Download filtered records as CSV
    csv_data = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download repository data as CSV",
        data=csv_data,
        file_name="github_repositories.csv",
        mime="text/csv",
    )

    st.caption(
        "Metrics describe the repositories in the latest fetched dataset. "
        "These are snapshots, not historical growth measurements."
    )

except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error(f"Could not read the database: {error}")
    st.info("Run pipeline.py first to create and populate the database.")
except (OSError, ValueError) as error:
    st.error(f"Could not load repository data: {error}")
    st.info("Check that the database exists and run pipeline.py first.")
