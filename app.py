import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from google.cloud import bigquery

st.set_page_config(layout="wide", page_title="Salesforce Copilot", page_icon="🧠")
st.markdown("<style>.stApp { background-color: #1A1A1A; color: #E0E0E0; }</style>", unsafe_allow_html=True)

# --- Configuration & Credentials ---
GCP_PROJECT = os.environ.get("GCP_PROJECT", "my-data-479716")
DATASET_ID = os.environ.get("BIGQUERY_DATASET", "salesforce")
KEY_PATH = "/app/credentials/gemini_api_key.txt" if os.path.exists("/.dockerenv") else "/home/briean/.gcp/gemini_api_key.txt"

def get_gemini_key():
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get("GEMINI_API_KEY", "")

# Initialize BigQuery Client directly
@st.cache_resource
def get_bq_client():
    return bigquery.Client(project=GCP_PROJECT)

bq_client = get_bq_client()

# --- Direct BigQuery Tools for Gemini ---

@st.cache_data(ttl=600)
def get_schema_info() -> str:
    """Returns the names and schemas of BigQuery tables and views using INFORMATION_SCHEMA."""
    query = f"""
        SELECT table_name, column_name, data_type
        FROM `{GCP_PROJECT}.{DATASET_ID}.INFORMATION_SCHEMA.COLUMNS`
        ORDER BY table_name, ordinal_position
    """
    try:
        query_job = bq_client.query(query)
        # Timeout after 15s to prevent hanging on missing GCP credentials
        df = query_job.result(timeout=15).to_dataframe()
        
        if df.empty:
            return f"No tables or views found in dataset `{GCP_PROJECT}.{DATASET_ID}`."
        
        tables = {}
        for _, row in df.iterrows():
            tables.setdefault(row["table_name"], []).append(
                f"{row['column_name']} ({row['data_type']})"
            )
            
        return "\n\n".join(
            [f"Table: {t}\nColumns: {', '.join(cols)}" for t, cols in tables.items()]
        )
    except Exception as e:
        return f"Error retrieving schema: {str(e)}"

def execute_readonly_query(sql_query: str) -> str:
    """Executes a read-only SELECT query against BigQuery and returns tabular markdown."""
    clean_sql = sql_query.strip().strip(";").lower()
    
    # Basic safety enforcement against destructive statements
    if not (clean_sql.startswith("select") or clean_sql.startswith("with")):
        return "Error: Only read-only SELECT or WITH statements are permitted."

    if "queries_run" not in st.session_state:
        st.session_state.queries_run = []
    st.session_state.queries_run.append(sql_query)

    try:
        query_job = bq_client.query(sql_query)
        # Fail fast after 20s if the query hangs or hits permission blocks
        df = query_job.result(max_results=100, timeout=20).to_dataframe()
        if df.empty:
            return "Query executed successfully, but returned 0 rows."
        return df.to_markdown(index=False)
    except Exception as e:
        return f"BigQuery Execution Error: {str(e)}"

# --- UI & Chat Setup ---

def parse_markdown_table(text):
    lines = [l.strip() for l in text.strip().split("\n") if l.strip().startswith("|")]
    if len(lines) < 3:
        return None
    try:
        header = [p.strip() for p in lines[0].split("|")[1:-1]]
        data = []
        for l in lines[2:]:
            vals = [p.strip() for p in l.split("|")[1:-1]]
            if len(vals) == len(header):
                data.append(vals)
        df = pd.DataFrame(data, columns=header)
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except ValueError:
                pass
        return df
    except Exception:
        return None

with st.sidebar:
    LOGO_PATH = "/home/briean/repos/salesforce_ai/Optimize-with-MODULO-Logo2.png"
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.title("BigQuery Direct")
    st.info(f"Targeting dataset: `{GCP_PROJECT}.{DATASET_ID}`")
    st.markdown("""
- **`account`**: Revenue, industry, location.
- **`opportunity`**: Source, stage.
    """)

st.title("Salesforce AI Copilot")
st.caption("AI insights running directly over BigQuery native API.")

api_key = get_gemini_key()
if not api_key:
    st.error(f"❌ Gemini API Key not found at `{KEY_PATH}`.")
    st.stop()

genai.configure(api_key=api_key)

if "chat_session" not in st.session_state:
    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        tools=[get_schema_info, execute_readonly_query],
        system_instruction=(
            f"You are an elite Salesforce analytics assistant querying Google BigQuery dataset `{GCP_PROJECT}.{DATASET_ID}`. "
            "Always inspect schemas via `get_schema_info` before writing queries. "
            "Write standard GoogleSQL queries referencing fully-qualified table names (`project.dataset.table`). "
            "Format data outputs as Markdown tables so the dashboard can render them as charts. "
            "Keep insights concise, encouraging, and analytical."
        )
    )
    st.session_state.chat_session = model.start_chat(enable_automatic_function_calling=True)
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("queries"):
            for q in msg["queries"]:
                with st.expander("🔍 SQL Query", expanded=False):
                    st.code(q, language="sql")
        if msg.get("df") is not None:
            st.dataframe(msg["df"], use_container_width=True)

if prompt := st.chat_input("Ask about sales, accounts, opportunities, trends..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.queries_run = []

    with st.chat_message("assistant"):
        with st.spinner("Executing BigQuery SQL..."):
            try:
                response = st.session_state.chat_session.send_message(prompt)
                ans_text = response.text
                st.markdown(ans_text)
                
                queries = list(st.session_state.get("queries_run", []))
                for q in queries:
                    with st.expander("🔍 SQL Query Executed", expanded=False):
                        st.code(q, language="sql")
                
                df = parse_markdown_table(ans_text)
                if df is not None:
                    st.dataframe(df, use_container_width=True)
                    num_cols = df.select_dtypes(include="number").columns.tolist()
                    if len(num_cols) >= 1 and len(df) > 1:
                        st.line_chart(df, y=num_cols[0], use_container_width=True)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": ans_text,
                    "queries": queries,
                    "df": df
                })
            except Exception as e:
                st.error(f"Failed to generate response: {e}")