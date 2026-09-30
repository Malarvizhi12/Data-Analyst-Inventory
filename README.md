# IT Services Analytics Dashboard

Interactive Streamlit dashboard for the IT services Excel sheet: 10 KPIs, 10 charts,
slicers, a date timeline, and an automatic deep-analysis tab.

## Run it
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Opens at http://localhost:8501. Use **Upload Excel file** in the sidebar to load your own workbook
(first sheet, same column headers as the sample).

## Project layout
- `app.py` - data loading, filters, KPIs, charts, analysis
- `data/it_services_sample.xlsx` - default dataset
- `requirements.txt` - dependencies

## Expected columns
Record_ID, Order_Date, City, Industry, Service_Category, Technology, Customer_Segment, Quantity,
Revenue_CAD, Cost_CAD, Profit_CAD, Support_Tickets, SLA_Compliance_Pct, Customer_Satisfaction,
Order_Status, Data_Type
