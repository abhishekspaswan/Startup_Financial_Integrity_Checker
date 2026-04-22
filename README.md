🔍 Startup Financial Integrity Checker
📌 Overview

Startup Financial Integrity Checker is an AI-powered system designed to detect anomalies and validate financial data of startups. It helps identify inconsistencies, suspicious transactions, and financial risks using Machine Learning and AI techniques.

According to the project document , the system focuses on detecting fraudulent accounting entries and improving trust in financial reporting.

🚨 Problem Statement

Fraudulent accounting entries and hidden manipulations often escape manual audits. This leads to:

 Financial fraud
 Incorrect reporting
 Poor investment decisions

💡 Solution

An AI-driven anomaly detection system that:

 Detects inconsistent ledger entries
 Identifies suspicious financial patterns
 Analyzes cashflow mismatches
 Generates integrity scores and risk levels

🤖 AI Technique

 Machine Learning based anomaly detection
 Data-driven financial risk scoring
 AI-generated audit insights

🛠️ Tech Stack

 Python
 Pandas, NumPy
 Plotly (visualization)
 Streamlit (web app)
 SQLite (database)
 OpenAI API (AI analysis) 

⚙️ Features

 📊 Financial data analysis dashboard
 🤖 AI-powered audit & risk detection
 📈 Integrity score calculation (0–100)
 🚩 Risk classification (Low / Medium / High)
 📄 Automated PDF report generation
 🗄️ Database storage for companies & audit history

 📊 Sample Output

The system generates:

 Integrity Score
 Risk Level
 Risk Factors
 Executive Summary

Example (from dataset) :

 FinServe AI → 92 (Low Risk)
 EcoBuild → 77 (Moderate Risk)
 HealthNova → 48 (High Risk)

 ▶️ How to Run

 1. Install dependencies

pip install -r requirements.txt

Dependencies include :

 streamlit
 pandas
 plotly
 openai
 reportlab
 numpy

2. Set API Key

Set your OpenAI API key:

export OPENAI_API_KEY=your_api_key

3. Run the app

streamlit run app.py


📈 Use Cases

 Startup financial auditing
 Fraud detection
 Investment risk analysis
 Financial health monitoring

🚀 Future Improvements

 Real-time API integration
 Advanced ML/DL models
 Interactive dashboards
 Automated investor reports

🎯 Impact

 Early fraud detection
 Better financial transparency
 Improved investor trust
 Reduced financial risk
