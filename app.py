import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import json
import os
import numpy as np
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
import io
import plotly.io as pio
import sqlite3
from datetime import datetime
import tempfile
import time
import re

# --- CONFIGURATION ---
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY', '')

if not OPENAI_API_KEY:
    st.error("⚠️ OPENAI_API_KEY not found! Please set it in your environment variables or Streamlit secrets.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(
    page_title="Startup Financial Integrity Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = 'financial_integrity.db'
CSV_FILE = 'financial_risk_clean.csv'

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1e3a8a;
        font-size: 2.8em;
        font-weight: 700;
        margin-bottom: 0.5em;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .sub-header {
        text-align: center;
        color: #64748b;
        font-size: 1.2em;
        margin-bottom: 2em;
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75em 2em;
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2em;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
def init_database():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT UNIQUE NOT NULL,
        revenue REAL, 
        expense REAL, 
        operating_profit REAL, 
        operating_profit_margin REAL,
        interest REAL, 
        depreciation REAL, 
        net_profit REAL, 
        net_profit_margin REAL,
        retained_earnings REAL, 
        cashflow_match REAL, 
        debt_to_equity REAL,
        current_ratio REAL, 
        interest_coverage REAL, 
        integrity_score INTEGER DEFAULT 0,
        final_risk TEXT DEFAULT 'Unrated', 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_name TEXT,
        audit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        integrity_score INTEGER,
        final_risk TEXT, 
        risk_factors TEXT, 
        summary TEXT, 
        reasoning TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS migration_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        csv_file TEXT,
        migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        records_migrated INTEGER)''')
    
    conn.commit()
    conn.close()

def check_if_csv_migrated():
    """Check if CSV has already been migrated"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM migration_status WHERE csv_file = ?", (CSV_FILE,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def auto_migrate_csv_to_db():
    """Automatically migrate CSV data to database on first run"""
    if not os.path.exists(CSV_FILE):
        return False, "CSV file not found"
    if check_if_csv_migrated():
        return True, "Already migrated"
    try:
        df = pd.read_csv(CSV_FILE)
        conn = sqlite3.connect(DB_NAME)
        records_migrated = 0
        for _, row in df.iterrows():
            data_dict = {
                'Company': row.get('Company', ''), 
                'Revenue': float(row.get('Revenue', 0)),
                'Expense': float(row.get('Expense', 0)), 
                'Operating Profit': float(row.get('Operating Profit', 0)),
                'Operating Profit Margin (%)': float(row.get('Operating Profit Margin (%)', 0)),
                'Interest': float(row.get('Interest', 0)), 
                'Depreciation': float(row.get('Depreciation', 0)),
                'Net Profit': float(row.get('Net Profit', 0)), 
                'Net Profit Margin (%)': float(row.get('Net Profit Margin (%)', 0)),
                'Retained Earnings': float(row.get('Retained Earnings', 0)), 
                'Cashflow Match (%)': float(row.get('Cashflow Match (%)', 0)),
                'Debt to Equity': float(row.get('Debt to Equity', 0)), 
                'Current Ratio': float(row.get('Current Ratio', 0)),
                'Interest Coverage': float(row.get('Interest Coverage', 0)), 
                'Integrity Score': int(row.get('Integrity Score', 0)),
                'Final Risk': str(row.get('Final Risk', 'Unrated'))
            }
            save_to_database(data_dict)
            records_migrated += 1
        cursor = conn.cursor()
        cursor.execute("INSERT INTO migration_status (csv_file, records_migrated) VALUES (?, ?)", 
                      (CSV_FILE, records_migrated))
        conn.commit()
        conn.close()
        return True, f"Successfully migrated {records_migrated} records"
    except Exception as e:
        return False, f"Migration error: {str(e)}"

def load_data_from_db():
    """Load all company data from database"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM companies ORDER BY company_name", conn)
    conn.close()
    if not df.empty:
        df = df.rename(columns={
            'company_name': 'Company', 
            'revenue': 'Revenue', 
            'expense': 'Expense',
            'operating_profit': 'Operating Profit', 
            'operating_profit_margin': 'Operating Profit Margin (%)',
            'interest': 'Interest', 
            'depreciation': 'Depreciation', 
            'net_profit': 'Net Profit',
            'net_profit_margin': 'Net Profit Margin (%)', 
            'retained_earnings': 'Retained Earnings',
            'cashflow_match': 'Cashflow Match (%)', 
            'debt_to_equity': 'Debt to Equity',
            'current_ratio': 'Current Ratio', 
            'interest_coverage': 'Interest Coverage',
            'integrity_score': 'Integrity Score', 
            'final_risk': 'Final Risk'
        })
    return df

def save_to_database(data_dict):
    """Save or update company data in database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""INSERT OR REPLACE INTO companies 
            (company_name, revenue, expense, operating_profit, operating_profit_margin, interest, 
             depreciation, net_profit, net_profit_margin, retained_earnings, cashflow_match, 
             debt_to_equity, current_ratio, interest_coverage, integrity_score, final_risk, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (data_dict['Company'], data_dict['Revenue'], data_dict['Expense'],
             data_dict['Operating Profit'], data_dict['Operating Profit Margin (%)'],
             data_dict['Interest'], data_dict['Depreciation'], data_dict['Net Profit'],
             data_dict['Net Profit Margin (%)'], data_dict['Retained Earnings'],
             data_dict['Cashflow Match (%)'], data_dict['Debt to Equity'],
             data_dict['Current Ratio'], data_dict['Interest Coverage'],
             data_dict.get('Integrity Score', 0), data_dict.get('Final Risk', 'Unrated')))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Database save error: {str(e)}")
        return False
    finally:
        conn.close()

def save_audit_history(company_name, audit):
    """Save audit results to history table"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO audit_history 
            (company_name, integrity_score, final_risk, risk_factors, summary, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (company_name, audit['integrity_score'], audit['final_risk'],
             json.dumps(audit['risk_factors']), audit['summary'], audit['reasoning']))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Audit history save error: {str(e)}")
        return False
    finally:
        conn.close()

def get_latest_audit_from_db(company_name):
    """Fetch the most recent audit for a company from the database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT integrity_score, final_risk, risk_factors, summary, reasoning
        FROM audit_history
        WHERE company_name = ?
        ORDER BY audit_date DESC
        LIMIT 1
    """, (company_name,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "integrity_score": row[0],
            "final_risk": row[1],
            "risk_factors": json.loads(row[2]) if row[2] else [],
            "summary": row[3],
            "reasoning": row[4]
        }
    return None

# --- AI ANALYSIS FUNCTION ---
def clean_json_response(text):
    """Clean and extract JSON from response"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text

def get_openai_audit(company_name, data):
    """Get AI-powered financial analysis from OpenAI"""
    try:
        prompt = f"""Analyze the financial integrity of {company_name} based on these metrics:

Revenue: ${data.get('Revenue', 0):,.2f}
Expense: ${data.get('Expense', 0):,.2f}
Operating Profit: ${data.get('Operating Profit', 0):,.2f}
Operating Profit Margin: {data.get('Operating Profit Margin (%)', 0):.2f}%
Interest: ${data.get('Interest', 0):,.2f}
Depreciation: ${data.get('Depreciation', 0):,.2f}
Net Profit: ${data.get('Net Profit', 0):,.2f}
Net Profit Margin: {data.get('Net Profit Margin (%)', 0):.2f}%
Retained Earnings: ${data.get('Retained Earnings', 0):,.2f}
Cashflow Match: {data.get('Cashflow Match (%)', 0):.2f}%
Debt to Equity: {data.get('Debt to Equity', 0):.2f}
Current Ratio: {data.get('Current Ratio', 0):.2f}
Interest Coverage: {data.get('Interest Coverage', 0):.2f}

IMPORTANT: Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
    "integrity_score": 75,
    "final_risk": "Medium Risk",
    "risk_factors": ["Negative cash flow", "High debt ratio"],
    "summary": "Brief 2-3 sentence summary here",
    "reasoning": "Detailed analysis here"
}}

Risk level must be exactly one of: "Low Risk", "Medium Risk", or "High Risk"."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial analyst. Respond ONLY with valid JSON, no markdown formatting, no extra text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        result = response.choices[0].message.content.strip() # type: ignore
        result = clean_json_response(result)
        parsed_result = json.loads(result)
        
        required_fields = ['integrity_score', 'final_risk', 'risk_factors', 'summary', 'reasoning']
        for field in required_fields:
            if field not in parsed_result:
                raise ValueError(f"Missing required field: {field}")
        
        valid_risks = ["Low Risk", "Medium Risk", "High Risk"]
        if parsed_result['final_risk'] not in valid_risks:
            parsed_result['final_risk'] = "Medium Risk"
        
        parsed_result['integrity_score'] = max(0, min(100, int(parsed_result['integrity_score'])))
        
        return parsed_result
        
    except json.JSONDecodeError as e:
        st.error(f"❌ JSON Parsing Error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ AI Analysis Error: {str(e)}")
        return None

# --- CHART FUNCTIONS ---
def create_gauge_chart(score):
    """Create integrity score gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Integrity Score", 'font': {'size': 24, 'color': '#1e3a8a'}},
        delta={'reference': 75, 'increasing': {'color': "#10b981"}, 'decreasing': {'color': "#ef4444"}},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 2, 'tickcolor': "#64748b"},
            'bar': {'color': "#667eea"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#cbd5e1",
            'steps': [
                {'range': [0, 40], 'color': '#fee2e2'},
                {'range': [40, 70], 'color': '#fef3c7'},
                {'range': [70, 100], 'color': '#d1fae5'}
            ],
            'threshold': {
                'line': {'color': "#dc2626", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Arial, sans-serif'}
    )
    return fig

def create_risk_pie_chart(df):
    """Create risk distribution pie chart"""
    risk_counts = df['Final Risk'].value_counts()
    colors_map = {
        'Low Risk': '#10b981',
        'Medium Risk': '#f59e0b',
        'High Risk': '#ef4444'
    }
    fig = go.Figure(data=[go.Pie(
        labels=risk_counts.index,
        values=risk_counts.values,
        hole=0.4,
        marker=dict(colors=[colors_map.get(x, '#94a3b8') for x in risk_counts.index]),
        textinfo='label+percent',
        textfont=dict(size=14, color='white', family='Arial')
    )])
    fig.update_layout(
        title={'text': 'Risk Distribution', 'font': {'size': 20, 'color': '#1e3a8a'}},
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig

def create_financial_metrics_chart(data):
    """Create financial metrics bar chart"""
    metrics = {
        'Op. Margin': data.get('Operating Profit Margin (%)', 0),
        'Net Margin': data.get('Net Profit Margin (%)', 0),
        'Cashflow Match': data.get('Cashflow Match (%)', 0)
    }
    fig = go.Figure(data=[
        go.Bar(
            x=list(metrics.keys()),
            y=list(metrics.values()),
            marker=dict(
                color=['#667eea', '#764ba2', '#f093fb'],
                line=dict(color='#1e3a8a', width=2)
            ),
            text=[f'{v:.1f}%' for v in metrics.values()],
            textposition='outside',
            textfont=dict(size=14, color='#1e3a8a', family='Arial')
        )
    ])
    fig.update_layout(
        title={'text': 'Key Financial Metrics', 'font': {'size': 20, 'color': '#1e3a8a'}},
        xaxis_title="Metrics",
        yaxis_title="Percentage (%)",
        height=300,
        margin=dict(l=20, r=20, t=60, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(248, 250, 252, 0.5)',
        font=dict(family='Arial, sans-serif')
    )
    return fig

# --- PDF GENERATION ---
def generate_enhanced_pdf(company_name, data, audit, df):
    """Generate professional PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    company_name_style = ParagraphStyle(
        'CompanyNameTitle',
        parent=styles['Title'],
        fontSize=28,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold',
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        spaceAfter=10,
        alignment=TA_JUSTIFY,
        fontName='Helvetica',
        leading=14
    )
    
    # Header
    story.append(Paragraph(f"<b>{company_name}</b>", company_name_style))
    story.append(Paragraph("Financial Integrity Analysis Report", subtitle_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", 
                          ParagraphStyle('DateStyle', parent=body_style, alignment=TA_CENTER, fontSize=10, textColor=colors.HexColor('#64748b'))))
    story.append(Spacer(1, 0.3*inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(audit['summary'], body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Financial Data Table
    story.append(Paragraph("Complete Financial Data", heading_style))
    
    financial_data = [
        ['Metric', 'Value'],
        ['Revenue', f"${data.get('Revenue', 0):,.2f}"],
        ['Expense', f"${data.get('Expense', 0):,.2f}"],
        ['Operating Profit', f"${data.get('Operating Profit', 0):,.2f}"],
        ['Operating Profit Margin', f"{data.get('Operating Profit Margin (%)', 0):.2f}%"],
        ['Interest', f"${data.get('Interest', 0):,.2f}"],
        ['Depreciation', f"${data.get('Depreciation', 0):,.2f}"],
        ['Net Profit', f"${data.get('Net Profit', 0):,.2f}"],
        ['Net Profit Margin', f"{data.get('Net Profit Margin (%)', 0):.2f}%"],
        ['Retained Earnings', f"${data.get('Retained Earnings', 0):,.2f}"],
        ['Cashflow Match', f"{data.get('Cashflow Match (%)', 0):.2f}%"],
        ['Debt to Equity', f"{data.get('Debt to Equity', 0):.2f}"],
        ['Current Ratio', f"{data.get('Current Ratio', 0):.2f}"],
        ['Interest Coverage', f"{data.get('Interest Coverage', 0):.2f}"]
    ]
    
    financial_table = Table(financial_data, colWidths=[3.5*inch, 2.5*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    story.append(financial_table)
    story.append(Spacer(1, 0.15*inch))
    
    # Assessment Metrics
    story.append(Paragraph("Key Assessment Metrics", heading_style))
    
    assessment_data = [
        ['Metric', 'Value'],
        ['Integrity Score', f"{audit['integrity_score']}/100"],
        ['Risk Level', audit['final_risk']]
    ]
    
    assessment_table = Table(assessment_data, colWidths=[3.5*inch, 2.5*inch])
    assessment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ede9fe')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8)
    ]))
    story.append(assessment_table)
    story.append(Spacer(1, 0.15*inch))
    
    # Risk Factors
    story.append(Paragraph("Risk Factors Identified", heading_style))
    
    if audit['risk_factors']:
        risk_data = [['Risk Factor']]
        for factor in audit['risk_factors']:
            risk_data.append([factor])
        
        risk_table = Table(risk_data, colWidths=[6*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fee2e2')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('VALIGN', (0, 1), (-1, -1), 'TOP')
        ]))
        story.append(risk_table)
    else:
        story.append(Paragraph("✓ No significant risk factors identified", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Detailed Analysis
    story.append(Paragraph("Detailed Financial Analysis", heading_style))
    story.append(Paragraph(audit['reasoning'], body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Visualizations
    story.append(Paragraph("Integrity Score Visualization", heading_style))
    
    gauge_img_path = None
    try:
        gauge_fig = create_gauge_chart(audit['integrity_score'])
        gauge_img_path = tempfile.mktemp(suffix='.png')
        gauge_fig.write_image(gauge_img_path, width=600, height=300, scale=2)
        gauge_img = RLImage(gauge_img_path, width=5*inch, height=2.5*inch)
        story.append(gauge_img)
    except Exception as e:
        story.append(Paragraph(f"[Chart visualization unavailable: {str(e)}]", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Financial Metrics Overview", heading_style))
    
    metrics_img_path = None
    try:
        metrics_fig = create_financial_metrics_chart(data)
        metrics_img_path = tempfile.mktemp(suffix='.png')
        metrics_fig.write_image(metrics_img_path, width=600, height=300, scale=2)
        metrics_img = RLImage(metrics_img_path, width=5*inch, height=2.5*inch)
        story.append(metrics_img)
    except Exception as e:
        story.append(Paragraph(f"[Chart visualization unavailable: {str(e)}]", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=body_style,
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER
    )
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("─────────────────────────────────────────────────────────", footer_style))
    story.append(Paragraph("This report is generated by AI-Powered Financial Integrity Checker", footer_style))
    story.append(Paragraph(f"Report Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    # Build PDF
    doc.build(story)
    
    # Clean up
    try:
        if gauge_img_path and os.path.exists(gauge_img_path):
            os.unlink(gauge_img_path)
        if metrics_img_path and os.path.exists(metrics_img_path):
            os.unlink(metrics_img_path)
    except:
        pass
    
    buffer.seek(0)
    return buffer

# --- INITIALIZE ---
init_database()
success, msg = auto_migrate_csv_to_db()

# Initialize session state
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = "Dashboard"
if 'selected_company' not in st.session_state:
    st.session_state['selected_company'] = None
if 'show_pdf_download' not in st.session_state:
    st.session_state['show_pdf_download'] = False
if 'pdf_buffer' not in st.session_state:
    st.session_state['pdf_buffer'] = None
if 'force_show_results' not in st.session_state:
    st.session_state['force_show_results'] = False
if 'show_new_results' not in st.session_state:
    st.session_state['show_new_results'] = False
if 'new_company_data' not in st.session_state:
    st.session_state['new_company_data'] = None
if 'new_company_audit' not in st.session_state:
    st.session_state['new_company_audit'] = None

# --- SIDEBAR ---
st.sidebar.title("🔍 Financial Integrity Checker")
st.sidebar.markdown("---")

# Navigation
view_mode = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Add New Company"],
    index=0 if st.session_state['view_mode'] == "Dashboard" else 1,
    key='nav_radio'
)

if view_mode != st.session_state['view_mode']:
    st.session_state['view_mode'] = view_mode
    st.session_state['show_pdf_download'] = False
    st.session_state['force_show_results'] = False
    st.session_state['show_new_results'] = False
    st.rerun()

# ADD NEW COMPANY FORM
if st.session_state['view_mode'] == "Add New Company":
    st.sidebar.markdown("### 🆕 Add New Company")
    
    with st.sidebar.form("add_company_form"):
        name = st.text_input("Company Name*", placeholder="e.g., Tech Startup Inc.")
        
        col1, col2 = st.columns(2)
        with col1:
            rev = st.number_input("Revenue ($)*", min_value=0.0, step=1000.0, format="%.2f")
            exp = st.number_input("Expense ($)*", min_value=0.0, step=1000.0, format="%.2f")
            int_val = st.number_input("Interest ($)*", min_value=0.0, step=100.0, format="%.2f")
            dep_val = st.number_input("Depreciation ($)*", min_value=0.0, step=100.0, format="%.2f")
            ret_earn = st.number_input("Retained Earnings ($)*", min_value=0.0, step=1000.0, format="%.2f")
        
        with col2:
            cfm = st.number_input("Cashflow Match (%)*", min_value=0.0, max_value=100.0, step=1.0, format="%.2f")
            dte = st.number_input("Debt to Equity*", min_value=0.0, step=0.1, format="%.2f")
            curr_ratio = st.number_input("Current Ratio*", min_value=0.0, step=0.1, format="%.2f")
            int_cov = st.number_input("Interest Coverage*", min_value=0.0, step=0.1, format="%.2f")
        
        submitted = st.form_submit_button("💾 Save and Analyze", type="primary", use_container_width=True)
        
        if submitted:
            if not name:
                st.error("❌ Company name is required!")
            else:
                # Calculate derived metrics
                op_profit = rev - exp
                op_margin = (op_profit / rev * 100) if rev > 0 else 0
                net_profit = op_profit - int_val - dep_val
                net_margin = (net_profit / rev * 100) if rev > 0 else 0
                
                temp_data = {
                    "Company": name,
                    "Revenue": rev,
                    "Expense": exp,
                    "Operating Profit": op_profit,
                    "Operating Profit Margin (%)": op_margin,
                    "Interest": int_val,
                    "Depreciation": dep_val,
                    "Net Profit": net_profit,
                    "Net Profit Margin (%)": net_margin,
                    "Retained Earnings": ret_earn,
                    "Cashflow Match (%)": cfm,
                    "Debt to Equity": dte,
                    "Current Ratio": curr_ratio,
                    "Interest Coverage": int_cov
                }
                
                # Get AI analysis
                with st.spinner(f"🔍 Analyzing {name}..."):
                    audit = get_openai_audit(name, temp_data)
                    if audit:
                        temp_data['Integrity Score'] = audit['integrity_score']
                        temp_data['Final Risk'] = audit['final_risk']
                        
                        # Save to database
                        if save_to_database(temp_data):
                            save_audit_history(name, audit)
                            
                            # Update session state
                            st.session_state['new_company_data'] = temp_data
                            st.session_state['new_company_audit'] = audit
                            st.session_state['show_new_results'] = True
                            
                            st.success(f"✅ {name} analyzed successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save company data. Please try again.")
                    else:
                        st.error("❌ AI analysis failed. Please check the error messages and try again.")

# DASHBOARD
df = load_data_from_db()

if st.session_state['view_mode'] == "Dashboard" and not df.empty:
    st.sidebar.markdown("---")
    options = df['Company'].unique().tolist()
    
    # Set default selection
    if st.session_state['selected_company'] and st.session_state['selected_company'] in options:
        default_idx = options.index(st.session_state['selected_company'])
    else:
        default_idx = 0
        st.session_state['selected_company'] = options[0]
    
    selected_comp = st.sidebar.selectbox(
        "🔍 Select Company",
        options=options,
        index=default_idx,
        key='company_selector'
    )
    
    # Update if selection changed
    if selected_comp != st.session_state['selected_company']:
        st.session_state['selected_company'] = selected_comp
        st.session_state['show_pdf_download'] = False
        st.session_state['force_show_results'] = False
        st.rerun()

# --- MAIN DASHBOARD ---
st.markdown('<h1 class="main-header">🔍 Startup Financial Integrity Checker</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-Powered Financial Analysis & Risk Assessment</p>', unsafe_allow_html=True)
st.divider()

if st.session_state['view_mode'] == "Dashboard" and not df.empty:
    selected_comp = st.session_state['selected_company']
    current_data = df[df['Company'] == selected_comp].iloc[0].to_dict()
    
    # Get or create audit
    audit = None
    
    # First check if we have a forced display (from adding new company)
    if st.session_state.get('force_show_results') and st.session_state.get('last_audit_comp') == selected_comp:
        audit = st.session_state.get('last_audit')
        st.session_state['force_show_results'] = False  # Reset flag after using it
    
    # Otherwise check for cached audit
    if not audit and st.session_state.get('last_audit_comp') == selected_comp:
        audit = st.session_state.get('last_audit')
    
    # Otherwise get from database
    if not audit:
        audit = get_latest_audit_from_db(selected_comp)
        if audit:
            st.session_state['last_audit'] = audit
            st.session_state['last_audit_comp'] = selected_comp
    
    # If still no audit, generate one
    if not audit or current_data.get('Integrity Score', 0) == 0:
        with st.spinner(f"🤖 AI analyzing {selected_comp}..."):
            audit = get_openai_audit(selected_comp, current_data)
            if audit:
                current_data['Integrity Score'] = audit['integrity_score']
                current_data['Final Risk'] = audit['final_risk']
                save_to_database(current_data)
                save_audit_history(selected_comp, audit)
                st.session_state['last_audit'] = audit
                st.session_state['last_audit_comp'] = selected_comp
                df = load_data_from_db()
                current_data = df[df['Company'] == selected_comp].iloc[0].to_dict()
                st.rerun()
    
    if audit:
        # Update sidebar
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 📊 Quick Stats")
        st.sidebar.metric("Integrity Score", f"{current_data.get('Integrity Score', 0)}/100")
        st.sidebar.metric("Risk Level", current_data.get('Final Risk', 'Unrated'))
        
        # TOP METRICS
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🎯 Integrity Score",
                f"{current_data['Integrity Score']}/100",
                delta=f"{current_data['Integrity Score'] - 75} vs benchmark"
            )
        
        with col2:
            risk_level = current_data['Final Risk']
            risk_emoji = "🟢" if "Low" in risk_level else "🟡" if "Medium" in risk_level else "🔴"
            st.metric(f"{risk_emoji} Risk Level", risk_level)
        
        with col3:
            st.metric(
                "📈 Operating Margin",
                f"{current_data.get('Operating Profit Margin (%)', 0):.1f}%"
            )
        
        with col4:
            st.metric(
                "💰 Net Margin",
                f"{current_data.get('Net Profit Margin (%)', 0):.1f}%"
            )
        
        st.markdown("---")
        
        # VISUALIZATIONS
        st.subheader("📊 Financial Analysis Dashboard")
        
        viz_col1, viz_col2, viz_col3 = st.columns(3)
        
        with viz_col1:
            st.plotly_chart(create_gauge_chart(current_data['Integrity Score']), 
                          use_container_width=True)
        
        with viz_col2:
            st.plotly_chart(create_risk_pie_chart(df), use_container_width=True)
        
        with viz_col3:
            st.plotly_chart(create_financial_metrics_chart(current_data), 
                          use_container_width=True)
        
        st.markdown("---")
        
        # RISK FACTORS
        st.subheader("🚩 Risk Factors Identified")
        
        if audit['risk_factors']:
            risk_cols = st.columns(2)
            for idx, factor in enumerate(audit['risk_factors']):
                with risk_cols[idx % 2]:
                    st.warning(f"⚠️ {factor}")
        else:
            st.success("✅ No significant risk factors identified")
        
        st.markdown("---")
        
        # EXECUTIVE SUMMARY
        st.subheader("📝 Executive Summary")
        st.info(f"**{audit['summary']}**")
        
        with st.expander("🔍 View Detailed Analysis"):
            st.markdown(f"**Detailed Reasoning:**\n\n{audit['reasoning']}")
        
        st.markdown("---")
        
        # FINANCIAL DATA TABLE
        st.subheader("📑 Complete Financial Data")
        
        display_data = {k: v for k, v in current_data.items() 
                       if k not in ['id', 'created_at', 'updated_at']}
        
        formatted_df = pd.DataFrame([display_data]).T
        formatted_df.columns = ['Value']
        formatted_df.index.name = 'Metric'
        
        st.dataframe(
            formatted_df,
            use_container_width=True,
            height=400
        )
        
        st.markdown("---")
        
        # PDF GENERATION
        st.subheader("📥 Export Report")
        
        col1, col2, col3 = st.columns([2, 1, 2])
        
        with col2:
            if st.button("📄 Generate PDF Report", type="primary", use_container_width=True, key='pdf_button'):
                try:
                    with st.spinner("📝 Creating professional PDF report..."):
                        pdf_buffer = generate_enhanced_pdf(selected_comp, current_data, audit, df)
                        st.session_state['pdf_buffer'] = pdf_buffer
                        st.session_state['show_pdf_download'] = True
                        st.success("✅ PDF Report Ready!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ PDF generation failed: {str(e)}")
        
        # Show download button if PDF is ready
        if st.session_state.get('show_pdf_download') and st.session_state.get('pdf_buffer'):
            col1, col2, col3 = st.columns([2, 1, 2])
            with col2:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=st.session_state['pdf_buffer'],
                    file_name=f"{selected_comp.replace(' ', '_')}_Financial_Report.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                    key='download_pdf_button'
                )

elif st.session_state['view_mode'] == "Dashboard" and df.empty:
    st.info("👋 Welcome! Please add a company to begin your financial integrity analysis.")
    
    if st.button("➕ Add Your First Company", type="primary"):
        st.session_state['view_mode'] = "Add New Company"
        st.rerun()

elif st.session_state['view_mode'] == "Add New Company":
    st.markdown("### 🆕 Adding New Company")
    
    # Check if we have new results to display
    if st.session_state.get('show_new_results'):
        new_data = st.session_state.get('new_company_data')
        new_audit = st.session_state.get('new_company_audit')
        
        if new_data and new_audit:
            st.success(f"✅ **{new_data['Company']}** has been successfully analyzed!")
            
            st.markdown("---")
            st.markdown("## 📊 Analysis Results")
            
            # TOP METRICS
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "🎯 Integrity Score",
                    f"{new_audit['integrity_score']}/100"
                )
            
            with col2:
                risk_level = new_audit['final_risk']
                risk_emoji = "🟢" if "Low" in risk_level else "🟡" if "Medium" in risk_level else "🔴"
                st.metric(f"{risk_emoji} Risk Level", risk_level)
            
            with col3:
                st.metric(
                    "📈 Operating Margin",
                    f"{new_data.get('Operating Profit Margin (%)', 0):.1f}%"
                )
            
            with col4:
                st.metric(
                    "💰 Net Margin",
                    f"{new_data.get('Net Profit Margin (%)', 0):.1f}%"
                )
            
            st.markdown("---")
            
            # VISUALIZATIONS
            st.subheader("📊 Financial Analysis Dashboard")
            
            viz_col1, viz_col2, viz_col3 = st.columns(3)
            
            with viz_col1:
                st.plotly_chart(create_gauge_chart(new_audit['integrity_score']), 
                              use_container_width=True)
            
            with viz_col2:
                df_temp = load_data_from_db()
                st.plotly_chart(create_risk_pie_chart(df_temp), use_container_width=True)
            
            with viz_col3:
                st.plotly_chart(create_financial_metrics_chart(new_data), 
                              use_container_width=True)
            
            st.markdown("---")
            
            # RISK FACTORS
            st.subheader("🚩 Risk Factors Identified")
            
            if new_audit['risk_factors']:
                risk_cols = st.columns(2)
                for idx, factor in enumerate(new_audit['risk_factors']):
                    with risk_cols[idx % 2]:
                        st.warning(f"⚠️ {factor}")
            else:
                st.success("✅ No significant risk factors identified")
            
            st.markdown("---")
            
            # EXECUTIVE SUMMARY
            st.subheader("📝 Executive Summary")
            st.info(f"**{new_audit['summary']}**")
            
            with st.expander("🔍 View Detailed Analysis"):
                st.markdown(f"**Detailed Reasoning:**\n\n{new_audit['reasoning']}")
            
            st.markdown("---")
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("➕ Add Another Company", use_container_width=True):
                    st.session_state['show_new_results'] = False
                    st.session_state['new_company_data'] = None
                    st.session_state['new_company_audit'] = None
                    st.rerun()
            
            with col2:
                if st.button("📊 View in Dashboard", type="primary", use_container_width=True):
                    st.session_state['selected_company'] = new_data['Company']
                    st.session_state['view_mode'] = "Dashboard"
                    st.session_state['show_new_results'] = False
                    st.session_state['last_audit'] = new_audit
                    st.session_state['last_audit_comp'] = new_data['Company']
                    st.rerun()
            
            with col3:
                if st.button("📄 Generate PDF", use_container_width=True):
                    try:
                        with st.spinner("📝 Creating PDF report..."):
                            df_temp = load_data_from_db()
                            pdf_buffer = generate_enhanced_pdf(new_data['Company'], new_data, new_audit, df_temp)
                            st.download_button(
                                label="⬇️ Download PDF Report",
                                data=pdf_buffer,
                                file_name=f"{new_data['Company'].replace(' ', '_')}_Financial_Report.pdf",
                                mime="application/pdf",
                                type="primary",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"❌ PDF generation failed: {str(e)}")
            
            st.stop()  # Don't show the form if results are being displayed
    
    st.info("👈 Please fill in the company details in the sidebar form and click 'Save and Analyze'")
    
    with st.expander("📚 Financial Metrics Guide", expanded=True):
        st.markdown("""
        **Key Metrics Explained:**
        
        - **Revenue**: Total income from sales
        - **Expense**: Total operational costs
        - **Operating Profit**: Revenue minus Expenses
        - **Interest**: Interest payments on debt
        - **Depreciation**: Asset value reduction over time
        - **Retained Earnings**: Accumulated profits kept in the business
        - **Cashflow Match**: How well cash flow aligns with profits (0-100%)
        - **Debt to Equity**: Ratio of debt to shareholder equity
        - **Current Ratio**: Ability to pay short-term obligations
        - **Interest Coverage**: Ability to pay interest from operating profit
        """)
    
    