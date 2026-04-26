# 🏥 MLS Virtual Hospital

[![License: All Rights Reserved](https://img.shields.io/badge/License-All%20Rights%20Reserved-red.svg)](./LICENSE)

> ⚠️ **Proprietary Software** — All Rights Reserved.  
> This code is publicly visible for reference but **may not be copied, reused, 
> or distributed** without written permission. See [LICENSE](./LICENSE) for details.

---
# 🏥 MLS Virtual Hospital — Setup Guide

## Files Required
```
virtual_hospital/
├── app.py               ← Main Streamlit app
├── case_studies.xlsx    ← YOUR patient cases database
├── requirements.txt     ← Python dependencies
└── README.md
```

## Setup Instructions

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run app.py
```

The app opens automatically at: **http://localhost:8501**

---

## How the App Uses Your Excel File

Your `case_studies.xlsx` has these sheets that the app reads:

| Sheet | Used For |
|-------|----------|
| `case Metadata` | Case ID, title, system, difficulty |
| `Initial Presentation` | Age/sex, chief complaint, duration, context |
| `History taking` | HPI, PMH, family/social history, medications |
| `physical examination` | Vitals, appearance, physical findings |
| `investigation` | Labs, urinalysis, imaging tests |
| `final diagnosis` | True diagnosis (hidden from student, used for evaluation) |

---

## Features

| Module | Description |
|--------|-------------|
| 🚨 Emergency Room | Presents the case: vitals, appearance, context |
| 💬 Patient Interview | AI plays the patient — answers questions naturally |
| 🧪 Laboratory | Student orders tests, sees real results from your Excel |
| 🔬 Imaging Room | Student orders imaging, sees real findings from your Excel |
| 📝 Submit Diagnosis | Student submits diagnosis + treatment → AI evaluates |
| 🤖 AI Tutor | Socratic clinical hints, never gives answer directly |
| 📚 Case Library | Browse all cases by system/difficulty/search |

---

## Adding New Cases
Simply add rows to your `case_studies.xlsx` following the same column format.
The app re-reads the file automatically on restart.

---

## Note on AI
The app uses **Claude Sonnet** via the Anthropic API.  
The API key is handled automatically when running inside Claude.ai.  
For standalone deployment, add your API key as an environment variable:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```
Then update `app.py` to pass it in the request headers:
```python
headers={"Content-Type":"application/json","x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version":"2023-06-01"}
```
