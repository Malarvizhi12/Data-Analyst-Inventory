"""IT Services Analytics Dashboard (Streamlit + Plotly).

Run:  streamlit run app.py
Loads data/it_services_sample.xlsx by default; upload your own file from the sidebar.
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="IT Services Dashboard", page_icon="📊", layout="wide")

DEFAULT_FILE = Path(__file__).parent / "data" / "it_services_sample.xlsx"
NUMERIC = ["Quantity", "Revenue_CAD", "Cost_CAD", "Profit_CAD", "Support_Tickets",
           "SLA_Compliance_Pct", "Customer_Satisfaction"]
SLICERS = ["City", "Industry", "Service_Category", "Technology",
           "Customer_Segment", "Order_Status", "Data_Type"]
COLORS = px.colors.qualitative.Safe


# ----------------------------------------------------------------- data layer
@st.cache_data(show_spinner=False)
def load_data(raw: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(raw))
    df.columns = df.columns.str.strip()
    df["Order_Date"] = pd.to_datetime(df["Order_Date"], errors="coerce")
    df = df.dropna(subset=["Order_Date"]).copy()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if df["SLA_Compliance_Pct"].max() <= 1.5:      # 0-1 scale -> percent
        df["SLA_Compliance_Pct"] *= 100
    for c in SLICERS:
        df[c] = df[c].fillna("(blank)").astype(str)
    df["Month"] = df["Order_Date"].dt.to_period("M").dt.to_timestamp()
    return df


def summarize(d: pd.DataFrame, by) -> pd.DataFrame:
    g = d.groupby(by).agg(
        Orders=("Order_Date", "count"), Qty=("Quantity", "sum"),
        Revenue=("Revenue_CAD", "sum"), Cost=("Cost_CAD", "sum"),
        Profit=("Profit_CAD", "sum"), Tickets=("Support_Tickets", "sum"),
        SLA=("SLA_Compliance_Pct", "mean"), CSAT=("Customer_Satisfaction", "mean"),
    ).reset_index()
    g["Margin"] = np.where(g["Revenue"] > 0, g["Profit"] / g["Revenue"] * 100, 0)
    return g


def kpis(d: pd.DataFrame) -> dict:
    n, rev, pr = len(d), d["Revenue_CAD"].sum(), d["Profit_CAD"].sum()
    return {
        "Total revenue": rev, "Total cost": d["Cost_CAD"].sum(), "Total profit": pr,
        "Profit margin %": pr / rev * 100 if rev else 0, "Orders": n,
        "Units sold": d["Quantity"].sum(), "Avg order value": rev / n if n else 0,
        "Support tickets": d["Support_Tickets"].sum(),
        "Avg SLA compliance %": d["SLA_Compliance_Pct"].mean() if n else 0,
        "Avg satisfaction": d["Customer_Satisfaction"].mean() if n else 0,
    }


def money(x): return f"${x/1e6:,.2f}M" if abs(x) >= 1e6 else f"${x/1e3:,.1f}K" if abs(x) >= 1e3 else f"${x:,.0f}"


def fmt(label, v):
    if "%" in label: return f"{v:.1f}%"
    if label == "Avg satisfaction": return f"{v:.2f}"
    if label in ("Orders", "Units sold", "Support tickets"): return f"{v:,.0f}"
    return money(v)


# -------------------------------------------------------------------- sidebar
st.sidebar.title("Data and filters")
up = st.sidebar.file_uploader("Upload Excel file", type=["xlsx", "xls"])
raw = up.getvalue() if up else DEFAULT_FILE.read_bytes()
try:
    df = load_data(raw)
except Exception as e:
    st.error(f"Could not read the file: {e}. Check that the column headers match the expected names.")
    st.stop()

dmin, dmax = df["Order_Date"].min().date(), df["Order_Date"].max().date()
rng = st.sidebar.date_input("Timeline", (dmin, dmax), min_value=dmin, max_value=dmax)
start, end = (rng if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax))
sla_target = st.sidebar.slider("SLA target %", 80, 100, 95)

mask_cat = pd.Series(True, index=df.index)
for c in SLICERS:
    opts = sorted(df[c].unique())
    if len(opts) > 1:
        pick = st.sidebar.multiselect(c.replace("_", " "), opts)
        if pick:
            mask_cat &= df[c].isin(pick)

in_range = df["Order_Date"].between(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1))
d = df[mask_cat & in_range]
span = pd.Timestamp(end) - pd.Timestamp(start)
prev = df[mask_cat & df["Order_Date"].between(pd.Timestamp(start) - span - pd.Timedelta(days=1),
                                               pd.Timestamp(start) - pd.Timedelta(days=1))]
if d.empty:
    st.warning("No rows match the current filters. Widen the timeline or clear a slicer.")
    st.stop()

# ------------------------------------------------------------------- KPI rows
st.title("IT Services Analytics Dashboard")
st.caption(f"{len(d):,} of {len(df):,} orders | {start} to {end} | change vs. the previous period of equal length")
cur, old = kpis(d), kpis(prev)
for row in (list(cur)[:5], list(cur)[5:]):
    for col, k in zip(st.columns(5), row):
        delta = None
        if len(prev):
            delta = (f"{cur[k]-old[k]:+.1f} pts" if "%" in k or k == "Avg satisfaction"
                     else f"{(cur[k]/old[k]-1)*100:+.1f}%" if old[k] else None)
        col.metric(k, fmt(k, cur[k]), delta,
                   delta_color="inverse" if k in ("Total cost", "Support tickets") else "normal")

t1, t2, t3, t4 = st.tabs(["Overview", "Profitability", "Service quality", "Deep analysis"])

# ------------------------------------------------------------------- overview
with t1:
    m = summarize(d, "Month").sort_values("Month")
    fig = go.Figure()
    fig.add_bar(x=m["Month"], y=m["Revenue"], name="Revenue", marker_color=COLORS[0])
    fig.add_bar(x=m["Month"], y=m["Cost"], name="Cost", marker_color=COLORS[1])
    fig.add_scatter(x=m["Month"], y=m["Profit"], name="Profit", mode="lines+markers", line=dict(color=COLORS[2]))
    fig.add_scatter(x=m["Month"], y=m["Margin"], name="Margin %", yaxis="y2", line=dict(dash="dot", color=COLORS[3]))
    fig.update_layout(title="1. Monthly revenue, cost, profit and margin", barmode="group",
                      yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Margin %"),
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

    a, b = st.columns(2)
    c = summarize(d, "City").sort_values("Revenue")
    a.plotly_chart(px.bar(c, y="City", x=["Revenue", "Profit"], orientation="h", barmode="group",
                          title="2. Revenue and profit by city", color_discrete_sequence=COLORS),
                   use_container_width=True)
    i = summarize(d, ["Industry"])
    b.plotly_chart(px.treemap(i, path=["Industry"], values="Revenue", color="Margin",
                              color_continuous_scale="RdYlGn", title="3. Industry revenue (colour = margin %)"),
                   use_container_width=True)

# -------------------------------------------------------------- profitability
with t2:
    a, b = st.columns(2)
    h = summarize(d, ["Service_Category", "Technology"]).pivot(index="Service_Category", columns="Technology", values="Margin")
    a.plotly_chart(px.imshow(h, text_auto=".1f", aspect="auto", color_continuous_scale="RdYlGn",
                             title="4. Margin % heatmap: service x technology"), use_container_width=True)
    seg = d.groupby(["Customer_Segment", "Order_Status"]).size().reset_index(name="Orders")
    b.plotly_chart(px.bar(seg, x="Customer_Segment", y="Orders", color="Order_Status", barmode="stack",
                          title="5. Orders by segment and status", color_discrete_sequence=COLORS),
                   use_container_width=True)
    s = summarize(d, "Service_Category")
    a, b = st.columns(2)
    a.plotly_chart(px.scatter(s, x="Revenue", y="Margin", size="Qty", color="Service_Category", size_max=45,
                              title="6. Service categories: revenue vs margin (bubble = units)",
                              color_discrete_sequence=COLORS), use_container_width=True)
    t = summarize(d, "Technology").sort_values("Revenue", ascending=False)
    t["Cumulative %"] = t["Revenue"].cumsum() / t["Revenue"].sum() * 100
    p = go.Figure()
    p.add_bar(x=t["Technology"], y=t["Revenue"], name="Revenue", marker_color=COLORS[4])
    p.add_scatter(x=t["Technology"], y=t["Cumulative %"], name="Cumulative %", yaxis="y2", line=dict(color=COLORS[1]))
    p.update_layout(title="7. Pareto: revenue by technology",
                    yaxis2=dict(overlaying="y", side="right", range=[0, 105], showgrid=False))
    b.plotly_chart(p, use_container_width=True)

# ------------------------------------------------------------ service quality
with t3:
    a, b = st.columns(2)
    s = summarize(d, "Service_Category")
    scale = 20 if d["Customer_Satisfaction"].max() <= 5 else 10 if d["Customer_Satisfaction"].max() <= 10 else 1
    r = go.Figure()
    r.add_scatterpolar(r=s["SLA"], theta=s["Service_Category"], fill="toself", name="SLA %")
    r.add_scatterpolar(r=s["CSAT"] * scale, theta=s["Service_Category"], fill="toself", name=f"Satisfaction x{scale}")
    r.update_layout(title="8. SLA vs satisfaction by service", polar=dict(radialaxis=dict(range=[50, 100])))
    a.plotly_chart(r, use_container_width=True)

    sc = px.scatter(d, x="Support_Tickets", y="Customer_Satisfaction", color="Order_Status",
                    title="9. Support tickets vs satisfaction", color_discrete_sequence=COLORS, opacity=0.7)
    if len(d) > 2 and d["Support_Tickets"].std() > 0:
        k, q = np.polyfit(d["Support_Tickets"], d["Customer_Satisfaction"], 1)
        xs = np.array([d["Support_Tickets"].min(), d["Support_Tickets"].max()])
        sc.add_scatter(x=xs, y=k * xs + q, mode="lines", name="Trend", line=dict(color="gray", dash="dash"))
    b.plotly_chart(sc, use_container_width=True)

    m = summarize(d, "Month").sort_values("Month")
    q = go.Figure()
    q.add_scatter(x=m["Month"], y=m["SLA"], name="SLA %", line=dict(color=COLORS[0]))
    q.add_scatter(x=m["Month"], y=m["CSAT"], name="Satisfaction", yaxis="y2", line=dict(color=COLORS[3]))
    q.add_hline(y=sla_target, line_dash="dot", annotation_text=f"SLA target {sla_target}%")
    q.update_layout(title="10. Monthly SLA compliance and satisfaction",
                    yaxis2=dict(overlaying="y", side="right", showgrid=False))
    st.plotly_chart(q, use_container_width=True)

# ------------------------------------------------------------- deep analysis
with t4:
    ins = []
    cty = summarize(d, "City").query("Revenue > 0").sort_values("Margin", ascending=False)
    if len(cty) > 1:
        ins.append(f"**Cities:** {cty.iloc[0]['City']} has the best margin ({cty.iloc[0]['Margin']:.1f}%); "
                   f"{cty.iloc[-1]['City']} the weakest ({cty.iloc[-1]['Margin']:.1f}%).")
    ind = summarize(d, "Industry").sort_values("Revenue", ascending=False)
    ins.append(f"**Industry:** {ind.iloc[0]['Industry']} leads with {ind.iloc[0]['Revenue']/d['Revenue_CAD'].sum()*100:.0f}% of revenue.")
    mm = summarize(d, "Month").sort_values("Month")
    if len(mm) > 1 and mm.iloc[-2]["Revenue"]:
        ins.append(f"**Momentum:** latest month revenue is {(mm.iloc[-1]['Revenue']/mm.iloc[-2]['Revenue']-1)*100:+.1f}% vs the month before.")
    if len(mm) > 3 and mm["Revenue"].std() > 0:
        z = (mm["Revenue"] - mm["Revenue"].mean()) / mm["Revenue"].std()
        odd = mm.loc[z.abs() > 2, "Month"].dt.strftime("%Y-%m").tolist()
        ins.append("**Anomalies:** " + (", ".join(odd) if odd else "no month is beyond 2 standard deviations."))
    if d["Support_Tickets"].std() > 0:
        rr = d["Support_Tickets"].corr(d["Customer_Satisfaction"])
        ins.append(f"**Tickets vs satisfaction:** correlation {rr:.2f}.")
    sv = summarize(d, "Service_Category")
    below = sv[sv["SLA"] < sla_target]
    ins.append(f"**SLA:** {len(below)} of {len(sv)} service categories are below the {sla_target}% target"
               + (f" (lowest: {sv.loc[sv['SLA'].idxmin(), 'Service_Category']}, {sv['SLA'].min():.1f}%)." if len(sv) else "."))
    canc = (d["Order_Status"].str.lower() == "cancelled").mean() * 100
    ins.append(f"**Cancellations:** {canc:.1f}% of orders; revenue tied to them: {money(d.loc[d['Order_Status'].str.lower()=='cancelled','Revenue_CAD'].sum())}.")
    for line in ins:
        st.markdown("- " + line)

    a, b = st.columns(2)
    a.subheader("Correlation matrix")
    a.plotly_chart(px.imshow(d[NUMERIC].corr(), text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1),
                   use_container_width=True)
    b.subheader("Lowest-margin service x technology pairs")
    pairs = summarize(d, ["Service_Category", "Technology"]).query("Orders >= 2").sort_values("Margin").head(8)
    b.dataframe(pairs[["Service_Category", "Technology", "Orders", "Revenue", "Profit", "Margin"]].round(1),
                use_container_width=True, hide_index=True)
    st.subheader("Orders needing attention: SLA below target and satisfaction below 4")
    risk = d[(d["SLA_Compliance_Pct"] < sla_target) & (d["Customer_Satisfaction"] < 4)]
    st.dataframe(risk.sort_values("Revenue_CAD", ascending=False).drop(columns=["Month"]),
                 use_container_width=True, hide_index=True)
    st.download_button("Download filtered data (CSV)", d.to_csv(index=False).encode(), "filtered_orders.csv")
