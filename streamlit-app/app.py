import streamlit as st
from google.oauth2 import service_account
from google.cloud import bigquery, storage
import tempfile
import pandas as pd
import time
import os
from datetime import datetime

GCP_PROJECT_ID = "docai-final"
BUCKET_NAME = "document-input-2"
DATASET = "document_processing_logs"
TABLE = "summary_results"

try:
    service_account_info = st.secrets["gcp_service_account"]
    creds = json.loads(json.dumps(service_account_info))
    bq_client = bigquery.Client(credentials=creds, project=GCP_PROJECT_ID)
    storage_client = storage.Client(credentials=creds, project=GCP_PROJECT_ID)
except Exception as e:
    st.error(f"Failed to initialize GCP clients. Please check your service account file and permissions. Error: {e}")
    st.stop()

st.title("Document Upload & Analysis")
st.markdown("Upload your PDF or image file to analyze it. Duplicate filenames will be handled by adding a timestamp.")

uploaded_file = st.file_uploader("Upload your document", type=["pdf", "png", "jpg"])

if uploaded_file:
    original_file_name = uploaded_file.name
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    name_parts = os.path.splitext(original_file_name)
    unique_file_name = f"{name_parts[0]}_{timestamp}{name_parts[1]}"

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        blob = storage_client.bucket(BUCKET_NAME).blob(unique_file_name)
        blob.upload_from_filename(tmp_path)
        st.success(f"Uploaded '{original_file_name}' as '{unique_file_name}' to Google Cloud Storage bucket '{BUCKET_NAME}'.")
        st.info("The backend will process the file using its unique name.")
    except Exception as e:
        st.error(f"Failed to upload file to Google Cloud Storage. Error: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        st.stop()

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    st.info(f"Waiting for processing results for '{unique_file_name}' in BigQuery...")

    query = f"""
        SELECT * FROM `{GCP_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE file_name = @file_name
        ORDER BY timestamp DESC
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("file_name", "STRING", unique_file_name)
        ]
    )

    result_row = None
    progress_text = "Processing... This may take a few seconds."
    my_bar = st.progress(0, text=progress_text)

    for i in range(20):
        try:
            df = bq_client.query(query, job_config=job_config).result().to_dataframe()
            if not df.empty:
                result_row = df.iloc[0]
                my_bar.progress(100, text="Document processed!")
                break
            
            my_bar.progress(min((i + 1) * 5, 100), text=f"{progress_text} ({i*3}s elapsed)")
            time.sleep(3)
        except Exception as e:
            st.error(f"Error querying BigQuery: {e}")
            my_bar.empty()
            st.stop()

    if result_row is not None:
        st.success("Document processing complete and results found!")
        st.subheader("Extracted Information")
        st.markdown("Here's what was extracted from your document based on the BigQuery schema:")

        agent_decision = result_row.get("agent_decision", "UNKNOWN")

        if agent_decision.upper() in ["ESCALATE", "FLAG"]:
            st.error(f"This document was flagged for review. Agent Decision: '{agent_decision}'. Further action may be required.")
        else:
            st.success(f"This document was processed successfully. Agent Decision: '{agent_decision}'.")

        # Summary (using gemini_summary as per schema)
        gemini_summary = result_row.get("gemini_summary", "")
        if gemini_summary and pd.notnull(gemini_summary):
            st.markdown("### Summary")
            st.info(f"> {gemini_summary}")
        else:
            st.info("No Gemini summary available for this document.")

        st.markdown("### Details from BigQuery")
        schema_fields = {
            "file_name": "Unique File Name (in GCS/BQ)",
            "document_bucket": "Document Bucket",
            "extracted_text_length": "Extracted Text Length (chars)",
            "cloud_function_invocation_id": "Cloud Function Invocation ID"
        }

        st.markdown(f"**Original Uploaded Name:** `{original_file_name}`")
        details_found = False

        for field, label in schema_fields.items():
            value = result_row.get(field, None)
            if pd.notnull(value) and value != "":
                st.markdown(f"**{label}:** `{value}`")
                details_found = True
        if not details_found:
            st.info("No additional details extracted or available for this document based on the current BigQuery schema.")

    else:
        st.error("No processing result found in BigQuery within the expected time. Please ensure the backend processing is functioning correctly and verify the file name match.")
        st.markdown("You can try uploading the document again or check your BigQuery logs for more details.")
