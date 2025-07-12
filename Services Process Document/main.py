import functions_framework
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
#from vertexai.preview.language_models import TextGenerationModel
from vertexai.generative_models import GenerativeModel
import os
import base64
import logging
import vertexai
from google.cloud import bigquery
import re

@functions_framework.cloud_event
def processDocument(cloud_event):
    print(f"Entry point has been reached.")

    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Triggered by file: {file_name} in bucket: {bucket_name}")

    project_id = os.environ.get("PROJECT_ID")
    processor_id = os.environ.get("PROCESSOR_ID")
    location = os.environ.get("LOCATION", "us-central1")

    # BigQuery Configuration
    bigquery_dataset_id = os.environ.get("BIGQUERY_DATASET_ID")
    bigquery_table_id = os.environ.get("BIGQUERY_TABLE_ID")

    # Create Document AI client
    client = documentai.DocumentProcessorServiceClient()
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    # Read the file from Cloud Storage
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    document_content = blob.download_as_bytes()

    # Configure the process request
    raw_document = documentai.RawDocument(content=document_content, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    try:
        print("Trying to process the documenty.")

        result = client.process_document(request=request)
        doc_text = result.document.text
        print("Document processed successfully.")
        #print(f"Extracted text:\n{doc_text[:1000]}") # Log first 1000 chars

        vertexai.init(project=project_id, location="us-central1")
        print(f"Initialized Vertex AI for project {project_id} in location {location}.")

        model = GenerativeModel("gemini-2.0-flash")
        prompt = (
            "Summarize this document and identify missing or non-compliant clauses. "
            "At the end, you MUST explicitly state your decision as one of the following: "
            "'Decision: ESCALATE', 'Decision: APPROVE', or 'Decision: FLAG'."
            "\n\nDocument Text:\n" + doc_text
        )

        response = model.generate_content(prompt)
        responseText = response.text
        responseText = re.sub(r'[\*_#]', '', responseText)

        summary = responseText # Default value
        decision = "UNKNOWN"
        pattern = re.compile(r"^(.*)\s+Decision:\s*(ESCALATE|APPROVE|FLAG)\s*$", re.DOTALL | re.IGNORECASE)
        match = pattern.search(responseText)

        if match:
            # Group 1 is the summary.
            summary = match.group(1).strip()
            # Group 2 is the decision word, which we convert to uppercase.
            decision = match.group(2).upper()

        # Now, 'summary' and 'decision' variables are correctly populated.
        print("--- PARSED SUMMARY ---")
        print(summary)
        print("\n--- PARSED DECISION ---")
        print(decision)
        
        print(f"Extracted Decision: {decision}, Extracted Summary (first 100 chars): {summary[:100]}...")

        if bigquery_dataset_id and bigquery_table_id:
            try:
                bq_client = bigquery.Client(project=project_id)
                table_id = f"{project_id}.{bigquery_dataset_id}.{bigquery_table_id}"
                
                rows_to_insert = [{
                    #"timestamp": bigquery.ScalarQueryParameter("TIMESTAMP", None), # BigQuery will use current timestamp
                    "file_name": file_name,
                    "document_bucket": bucket_name,
                    "extracted_text_length": len(doc_text),
                    "gemini_summary": summary,
                    "agent_decision": decision,
                    "cloud_function_invocation_id": os.environ.get("K_REVISION", "unknown") # Cloud Function revision as invocation ID
                }]
                
                errors = bq_client.insert_rows_json(table_id, rows_to_insert)
                if errors:
                    print(f"Errors while inserting rows into BigQuery: {errors}")
                else:
                    print(f"Data successfully inserted into BigQuery table: {table_id}")
            except Exception as e:
                print(f"Failed to log to BigQuery: {e}")
        else:
            print("BigQuery dataset or table ID not configured. Skipping BigQuery logging.")

    except Exception as e:
        print(f"Failed to process document: {str(e)}")