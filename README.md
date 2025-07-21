# Document Review Pipeline with Vertex AI & Streamlit

This project implements a fully automated document review system using Google Cloud technologies. Documents uploaded to a GCS bucket are processed through Document AI and reviewed using the Gemini 2.0 Flash model on Vertex AI. Final decisions are stored in BigQuery and visualized through a Streamlit-based frontend.

Live Website: https://docai-agent-csandye3gq5q46x39t2zeq.streamlit.app/

---

## Architecture Overview

1. **Upload**  
   Users upload documents via a Streamlit web interface. These files are stored in a GCS bucket.

2. **Trigger Cloud Run**  
   The file upload triggers a Cloud Run service.

3. **Document Parsing**  
   The Cloud Run service retrieves the uploaded file and extracts text using **Google Document AI**.

4. **AI-Based Review**  
   The extracted text is passed into **Vertex AI's Gemini 2.0 Flash** model with the following prompt:
   
6. **Decision Parsing**  
  The response from Gemini is parsed to extract:
    - The document summary
    - Compliance insights
    - Final decision (`ESCALATE`, `APPROVE`, or `FLAG`)

6. **Storage**  
  Parsed results are stored in **BigQuery** for analytics and reporting.

7. **Frontend**  
  The Streamlit frontend polls BigQuery for results and displays the review and decision status to the user.

---

## Technologies Used

| Component      | Tool/Service                  |
|----------------|-------------------------------|
| Frontend       | Streamlit                     |
| Storage        | Google Cloud Storage (GCS)    |
| Event Trigger  | Google Cloud Run              |
| OCR / Parsing  | Google Document AI            |
| LLM Model      | Vertex AI (Gemini 2.0 Flash)  |
| Database       | BigQuery                      |
| Hosting        | Google Cloud Platform (GCP)   |

---

## Setup Instructions

### 1. Deploying the Backend

- Deploy the Cloud Run service using your preferred method (UI or `gcloud` CLI).
- Ensure the Cloud Run service has access to:
  - Read from GCS
  - Call Document AI
  - Call Vertex AI
  - Write to BigQuery

### 2. Configuring Triggers

- Set up a **GCS bucket** trigger that invokes the Cloud Run service on file upload.

### 3. Frontend (Streamlit)

- Install dependencies:
```bash
pip install -r requirements.txt
```
- Run the streamlit app
```
streamlit run app.py
```


