import os
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

PROJECT_ID = "my-data-479716"
DATASET_ID = "salesforce"

client = bigquery.Client(project=PROJECT_ID)

def create_dataset_if_not_exists(dataset_id: str):
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset '{dataset_id}' exists.")
    except NotFound:
        print(f"Dataset '{dataset_id}' not found. Creating dataset...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, timeout=30)
        print(f"Dataset '{dataset_id}' created successfully.")

def load_ndjson_file(file_path: str, table_name: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    table_ref = client.dataset(DATASET_ID).table(table_name)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Overwrites on re-run
    )

    print(f"\nUploading {file_path} to {PROJECT_ID}.{DATASET_ID}.{table_name}...")
    with open(file_path, "rb") as source_file:
        load_job = client.load_table_from_file(
            source_file,
            table_ref,
            job_config=job_config
        )

    load_job.result()  # Wait for job completion

    table = client.get_table(table_ref)
    print(f"Loaded {table.num_rows} rows into {table.project}.{table.dataset_id}.{table.table_id}.")

if __name__ == "__main__":
    create_dataset_if_not_exists(DATASET_ID)
    load_ndjson_file("salesforce_account.ndjson", "account")
    load_ndjson_file("salesforce_opportunity.ndjson", "opportunity")
    print("\nLoad complete. Both tables are populated in BigQuery.")