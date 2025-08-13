# DCF + WACC Valuation Tool

## Features
- Three-stage DCF growth model
- Share buyback adjustments
- WACC helper with auto data fetch & US 10Y yield
- Batch PDF export with WACC breakdown
- Auto-run WACC on ticker change
- Color-coded WACC output

## Deployment (Streamlit Cloud)
1. Create a new GitHub repository
2. Upload all files from this folder
3. Go to [Streamlit Cloud](https://streamlit.io/cloud)
4. Sign in with GitHub and click "New app"
5. Select your repo and `streamlit_app.py` as the main file
6. Click **Deploy** — your app will be live in 1–2 minutes

## Local Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
