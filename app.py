"""Customer churn & subscriptions — three-chart interactive Streamlit dashboard.

GitHub/Streamlit Cloud entrypoint: app.py
Runs with the privacy-safe 15-row summary in data/; if missing, uses matching
bundled aggregate counts to avoid a FileNotFoundError during deployment.
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Customer Churn & Subscriptions",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PLANS = ("Basic", "Standard", "Premium")
BANDS = ("4.99–<8", "8–<11", "11–<14", "14–<17", "17–<20")
ALL = "All plans"
ALL_BANDS = "All charge bands"
COLORS = {ALL: "#596EDC", "Basic": "#D66E54", "Standard": "#159A91", "Premium": "#806BC8"}
INK = "#1D2C46"
MUTED = "#65758C"
GRID = "#E8EDF5"
DATA_PATH = Path(__file__).resolve().parent / "data" / "plan_charge_summary.csv"

# Verified totals from the uploaded 243,787-row subscription_churn_full CSV.
# (SubscriptionType, ChargeBand, Customers, Cancelled)
BACKUP_COUNTS = (
    ("Basic", "4.99–<8", 16257, 2328),
    ("Basic", "8–<11", 16095, 2686),
    ("Basic", "11–<14", 16092, 3141),
    ("Basic", "14–<17", 16565, 3675),
    ("Basic", "17–<20", 16041, 4098),
    ("Standard", "4.99–<8", 16498, 2160),
    ("Standard", "8–<11", 16319, 2493),
    ("Standard", "11–<14", 16242, 3031),
    ("Standard", "14–<17", 16412, 3429),
    ("Standard", "17–<20", 16449, 3986),
    ("Premium", "4.99–<8", 16170, 1874),
    ("Premium", "8–<11", 16261, 2244),
    ("Premium", "11–<14", 16073, 2584),
    ("Premium", "14–<17", 16313, 2998),
    ("Premium", "17–<20", 16000, 3455),
)


@st.cache_data(show_spinner=False)
def load_counts(csv_path: str) -> pd.DataFrame:
    """Load aggregated data safely, falling back if the CSV is absent."""
    path = Path(csv_path)
    if path.is_file():
        frame = pd.read_csv(path)
    else:
        frame = pd.DataFrame(BACKUP_COUNTS, columns=[
            "SubscriptionType", "ChargeBand", "Customers", "Cancelled"
        ])
    required = {"SubscriptionType", "ChargeBand", "Customers", "Cancelled"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns in summary CSV: {', '.join(sorted(missing))}")
    frame = frame[list(required)].copy()
    for column in ("Customers", "Cancelled"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[column].isna().any() or (frame[column] < 0).any():
            raise ValueError(f"Invalid {column} values in summary CSV.")
        if (frame[column] % 1 != 0).any():
            raise ValueError(f"{column} counts must be whole numbers.")
        frame[column] = frame[column].astype("int64")
    if (frame["Cancelled"] > frame["Customers"]).any():
        raise ValueError("Cancelled cannot exceed Customers.")
    if not set(frame["SubscriptionType"]).issubset(PLANS):
        raise ValueError("Unknown subscription plan in summary CSV.")
    if not set(frame["ChargeBand"]).issubset(BANDS):
        raise ValueError("Unknown charge band in summary CSV.")
    if frame.duplicated(["SubscriptionType", "ChargeBand"]).any():
        raise ValueError("Each plan/charge-band group should appear once.")
    # Keep all 15 groups: missing groups are represented as zero, not silently ignored.
    ordered = pd.MultiIndex.from_product([PLANS, BANDS], names=["SubscriptionType", "ChargeBand"])
    frame = frame.set_index(["SubscriptionType", "ChargeBand"]).reindex(
        ordered, fill_value=0
    ).reset_index()
    return frame


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    result = frame.groupby(group_cols, as_index=False, sort=False)[["Customers", "Cancelled"]].sum()
    result["Rate"] = result["Cancelled"].div(result["Customers"].replace(0, float("nan"))).mul(100)
    return result


def selected_rows(frame: pd.DataFrame, plan: str = ALL, band: str = ALL_BANDS) -> pd.DataFrame:
    if plan != ALL:
        frame = frame.loc[frame["SubscriptionType"] == plan]
    if band != ALL_BANDS:
        frame = frame.loc[frame["ChargeBand"] == band]
    return frame


def group_rate(frame: pd.DataFrame) -> float:
    customers = int(frame["Customers"].sum())
    return float(frame["Cancelled"].sum()) / customers * 100 if customers else float("nan")


def formatted_delta(a: float, b: float) -> str:
    difference = a - b
    if abs(difference) < 0.005:
        return "the same as"
    return f"{abs(difference):.2f} percentage points {'above' if difference > 0 else 'below'}"


def plan_insight(frame: pd.DataFrame, plan: str) -> tuple[str, str, str]:
    plans = summarize(frame, ["SubscriptionType"]).set_index("SubscriptionType").reindex(PLANS)
    rates = plans["Rate"]
    if plan == ALL:
        hi, lo = rates.idxmax(), rates.idxmin()
        return (
            f"{hi} leads at {rates[hi]:.2f}%",
            f"{hi} has the highest observed cancellation rate, compared with {rates[lo]:.2f}% for {lo}.",
            f"{rates[hi] - rates[lo]:.2f} pp difference across plans",
        )
    chosen = plans.loc[plan]
    overall = group_rate(frame)
    return (
        f"{plan}: {chosen['Rate']:.2f}% cancelled",
        f"This is {formatted_delta(float(chosen['Rate']), overall)} the overall rate of {overall:.2f}%.",
        f"{int(chosen['Cancelled']):,} cancellations / {int(chosen['Customers']):,} customers",
    )


def trend_insight(frame: pd.DataFrame, plan: str, band: str) -> tuple[str, str, str]:
    focus = selected_rows(frame, plan=plan)
    trend = summarize(focus, ["ChargeBand"]).set_index("ChargeBand").reindex(BANDS)
    group_name = "All plans" if plan == ALL else plan
    if band == ALL_BANDS:
        low = float(trend.iloc[0]["Rate"])
        high = float(trend.iloc[-1]["Rate"])
        return (
            f"{high - low:+.2f} pp from first to last band",
            f"For {group_name}, cancellation moves from {low:.2f}% in the lowest to {high:.2f}% in the highest charge band.",
            f"{int(focus['Customers'].sum()):,} customers across all charge bands",
        )
    chosen = trend.loc[band]
    overall = group_rate(focus)
    return (
        f"{band}: {chosen['Rate']:.2f}% cancelled",
        f"For {group_name}, this charge band's rate is {formatted_delta(float(chosen['Rate']), overall)} its full-band rate ({overall:.2f}%).",
        f"{int(chosen['Cancelled']):,} cancellations / {int(chosen['Customers']):,} customers",
    )


def hotspot_insight(frame: pd.DataFrame, plan: str, band: str) -> tuple[str, str, str]:
    subset = selected_rows(frame, plan, band)
    cells = summarize(subset, ["SubscriptionType", "ChargeBand"])
    cells = cells.loc[cells["Customers"] > 0]
    strongest = cells.sort_values("Rate", ascending=False).iloc[0]
    return (
        f"{strongest['SubscriptionType']} · {strongest['ChargeBand']}",
        f"Highest cancellation within the selected heatmap area: {strongest['Rate']:.2f}%.",
        f"{int(strongest['Cancelled']):,} cancelled of {int(strongest['Customers']):,} customers",
    )


def plot_base(height: int = 370) -> dict:
    return dict(
        template="plotly_white", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, Arial, sans-serif", size=12, color=INK),
        margin=dict(l=56, r=24, t=28, b=52), showlegend=False,
        hoverlabel=dict(bgcolor="#243756", font_color="white", font_size=12),
    )


def plan_chart(frame: pd.DataFrame, selected: str) -> go.Figure:
    table = summarize(frame, ["SubscriptionType"]).set_index("SubscriptionType").reindex(PLANS).reset_index()
    fig = go.Figure()
    fig.add_bar(
        x=table["SubscriptionType"], y=table["Rate"],
        marker_color=[COLORS[p] for p in PLANS],
        marker_opacity=[1 if selected in (ALL, p) else .34 for p in PLANS],
        width=.52,
        text=[f"{r:.2f}%" for r in table["Rate"]], textposition="outside",
        textfont=dict(size=16, color=INK),
        customdata=table[["Customers", "Cancelled"]].to_numpy(),
        hovertemplate="<b>%{x}</b><br>Cancellation rate: <b>%{y:.2f}%</b>"
        "<br>Customers: %{customdata[0]:,}<br>Cancelled: %{customdata[1]:,}<extra></extra>",
    )
    fig.update_layout(**plot_base(325), bargap=.38)
    fig.update_yaxes(title="Cancellation rate (%)", range=[0, 28], dtick=5, ticksuffix="%",
                     gridcolor=GRID, zeroline=False)
    fig.update_xaxes(showgrid=False, linecolor="#DFE6EF", title=None)
    return fig


def trend_chart(frame: pd.DataFrame, selected: str, compare: bool, focus_band: str = ALL_BANDS) -> go.Figure:
    fig = go.Figure()
    series = PLANS if compare else (selected,)
    for plan in series:
        rows = selected_rows(frame, plan=plan)
        table = summarize(rows, ["ChargeBand"]).set_index("ChargeBand").reindex(BANDS)
        value = table["Rate"]
        fig.add_trace(go.Scatter(
            x=list(BANDS), y=value.to_numpy(),
            mode="lines+markers" if compare else "lines+markers+text",
            name="All customers" if plan == ALL else plan,
            text=None if compare else [f"{x:.1f}%" for x in value],
            textposition="top center", textfont=dict(color=COLORS[plan], size=12),
            line=dict(color=COLORS[plan], width=3.5 if plan == selected else 2.7),
            marker=dict(size=10, line=dict(color="white", width=2)),
            customdata=table[["Customers", "Cancelled"]].to_numpy(),
            hovertemplate=f"<b>{html.escape(plan)}</b><br>Charge band: %{{x}}"
            "<br>Cancellation rate: %{y:.2f}%"
            "<br>Customers: %{customdata[0]:,}<br>Cancelled: %{customdata[1]:,}<extra></extra>",
        ))
    fig.update_layout(**plot_base(352))
    fig.update_layout(showlegend=compare,
                      legend=dict(orientation="h", x=0, y=1.14, yanchor="bottom"),
                      margin=dict(l=56, r=28, t=49, b=65))
    fig.update_yaxes(title="Cancellation rate (%)", range=[0, 33], dtick=5, ticksuffix="%",
                     gridcolor=GRID, zeroline=False)
    if focus_band != ALL_BANDS:
        fig.add_vrect(x0=BANDS.index(focus_band)-.35, x1=BANDS.index(focus_band)+.35,
                      line_width=0, fillcolor="#B8CCFF", opacity=.26, layer="below")
    fig.update_xaxes(title="Monthly-charge band (currency not supplied)",
                     categoryorder="array", categoryarray=list(BANDS),
                     linecolor="#DFE6EF", tickfont=dict(size=11))
    return fig


def heatmap_chart(frame: pd.DataFrame, plan: str, band: str) -> go.Figure:
    cells = summarize(frame, ["SubscriptionType", "ChargeBand"])
    indexed = cells.set_index(["SubscriptionType", "ChargeBand"])
    z = []
    info = []
    for p in PLANS:
        zrow, ir = [], []
        for b in BANDS:
            cell = indexed.loc[(p, b)]
            zrow.append(float(cell["Rate"]))
            ir.append([p, b, int(cell["Customers"]), int(cell["Cancelled"])])
        z.append(zrow)
        info.append(ir)

    fig = go.Figure(go.Heatmap(
        z=z, x=list(range(len(BANDS))), y=list(range(len(PLANS))),
        customdata=info, zmin=10, zmax=30,
        colorscale=[
            [0.0, "#F2F7FF"], [.22, "#C8DFF5"], [.46, "#83B6D5"],
            [.7, "#487AAE"], [1, "#253E78"],
        ],
        xgap=5, ygap=5, showscale=True,
        colorbar=dict(title=dict(text="Rate (%)", side="top"), len=.86, thickness=14,
                      tickvals=[10, 15, 20, 25, 30], ticksuffix="%", x=1.03),
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}"
                       "<br>Cancellation rate: <b>%{z:.2f}%</b>"
                       "<br>Customers: %{customdata[2]:,}"
                       "<br>Cancelled: %{customdata[3]:,}<extra></extra>"),
    ))
    for i, p in enumerate(PLANS):
        for j, b in enumerate(BANDS):
            rate = z[i][j]
            fig.add_annotation(x=j, y=i, text=f"<b>{rate:.1f}%</b>", showarrow=False,
                               font=dict(color="white" if rate >= 19.5 else "#203351", size=14))

    # Filters emphasise the corresponding cells while retaining the full heatmap for comparison.
    if plan != ALL or band != ALL_BANDS:
        i_values = range(len(PLANS)) if plan == ALL else (PLANS.index(plan),)
        j_values = range(len(BANDS)) if band == ALL_BANDS else (BANDS.index(band),)
        for i in i_values:
            for j in j_values:
                fig.add_shape(type="rect", x0=j-.47, x1=j+.47, y0=i-.46, y1=i+.46,
                              line=dict(color="#F6A841", width=3),
                              fillcolor="rgba(0,0,0,0)")
    fig.update_layout(**plot_base(350))
    fig.update_layout(margin=dict(l=88, r=98, t=20, b=74),
                      dragmode=False)
    fig.update_xaxes(tickvals=list(range(len(BANDS))), ticktext=list(BANDS),
                     title="Monthly-charge bands", side="bottom", showgrid=False,
                     range=[-.5, len(BANDS)-.5], tickfont=dict(size=11), zeroline=False)
    fig.update_yaxes(tickvals=list(range(len(PLANS))), ticktext=list(PLANS),
                     title="Subscription plan", showgrid=False,
                     range=[len(PLANS)-.5, -.5], tickfont=dict(size=12), zeroline=False)
    return fig


def insight_box(kicker: str, headline: str, description: str, metric: str, css_class: str = "") -> None:
    st.markdown(
        f'<div class="insight-box {css_class}">'
        f'<div class="insight-kicker">{html.escape(kicker)}</div>'
        f'<div class="insight-headline">{html.escape(headline)}</div>'
        f'<p>{html.escape(description)}</p>'
        f'<div class="insight-foot">{html.escape(metric)}</div>'
        '</div>', unsafe_allow_html=True,
    )


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');
html, body, [data-testid="stApp"] {font-family:'DM Sans',sans-serif;}
[data-testid="stAppViewContainer"] {background:#F6F8FC;}
.block-container {max-width:1260px;padding-top:1.7rem;padding-bottom:3.6rem;}
h1,h2,h3 {font-family:'Manrope',sans-serif;letter-spacing:-.025em;}
.hero {background:linear-gradient(112deg,#192943,#2B4074 73%,#38568E);
       border-radius:22px;padding:30px 34px;color:white;box-shadow:0 16px 35px #14264b1c;}
.hero-eyebrow {font-size:11px;letter-spacing:.17em;text-transform:uppercase;
               color:#B9CBFF;font-weight:800;margin-bottom:16px;}
.hero-title {display:flex;align-items:center;gap:15px;margin-bottom:14px;}
.hero-logo {width:62px;height:62px;border-radius:16px;background:#ffffff1b;
            border:1px solid #ffffff38;display:flex;align-items:center;justify-content:center;
            transition:transform .22s ease,background .22s ease;flex-shrink:0;}
.hero-logo:hover {transform:translateY(-3px) rotate(-4deg);background:#ffffff2d;}
.hero h1 {color:white;font-size:34px;line-height:1.18;margin:0;font-weight:800;}
.hero p {color:#dbe5fc;font-size:15px;line-height:1.6;max-width:880px;margin:0;}
.hero-tags {display:flex;gap:9px;flex-wrap:wrap;margin-top:20px;}
.hero-tags span {border:1px solid #ffffff35;border-radius:30px;color:#f3f6ff;
                 background:#ffffff14;padding:7px 12px;font-size:11px;}
.hero-nav {display:flex;flex-wrap:wrap;gap:8px;margin-top:15px;}
.hero-nav a {font-size:12px;font-weight:700;border:1px solid #ffffff30;
            background:#a8bfff20;padding:8px 12px;border-radius:9px;color:white!important;
            text-decoration:none!important;transition:background .18s ease;}
.hero-nav a:hover {background:#b8c9ff48;}
.section-label {font-size:11px;letter-spacing:.14em;color:#6173BB;
                font-weight:800;text-transform:uppercase;margin-bottom:4px;}
.section-title {font-size:23px;color:#20304D;font-family:'Manrope',sans-serif;
                font-weight:800;margin-bottom:4px;}
.section-sub {font-size:13px;color:#677994;margin-bottom:13px;line-height:1.6;}
.metric-card {height:126px;background:white;border:1px solid #E5EBF5;border-radius:16px;
              box-shadow:0 4px 16px #1f346005;padding:18px 19px;}
.metric-label {font-size:12px;color:#6A7A92;font-weight:700;}
.metric-value {font-size:28px;color:#202E4B;font-family:'Manrope',sans-serif;
               font-weight:800;letter-spacing:-.045em;margin-top:9px;}
.metric-note {font-size:11px;color:#8290A3;margin-top:3px;}
.metric-highlight {background:#ECF1FF;border-color:#DDE5FF;}
.metric-highlight .metric-value {color:#4056B3;}
.insight-box {background:#F0F4FF;border:1px solid #DFE6FC;border-radius:16px;
              padding:17px 18px;margin:0 0 11px;transition:box-shadow .15s ease;}
.insight-box:hover {box-shadow:0 7px 17px #1c367013;}
.insight-kicker {font-size:10px;font-weight:800;color:#5165B4;
                 letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px;}
.insight-headline {font-family:'Manrope',sans-serif;font-size:16px;
                   font-weight:800;line-height:1.4;color:#25365B;}
.insight-box p {font-size:12px;line-height:1.6;color:#5E708A;margin:8px 0;}
.insight-foot {font-size:11px;font-weight:700;color:#4B5D84;
               border-top:1px solid #D6E0F6;padding-top:10px;margin-top:11px;}
.insight-accent {background:#EAF7F4;border-color:#D5EBE7;}
.insight-accent .insight-kicker {color:#167A76;}
.insight-accent .insight-foot {border-color:#C9E7E1;}
.controls {color:#2E4366;font-size:13px;}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-color:#E5EAF2!important;}
@media(max-width:720px) {.hero{padding:24px 22px}.hero h1{font-size:27px}
 .hero-logo{width:48px;height:48px}.metric-card{height:117px}.block-container{padding-top:1rem;}}
@media(prefers-reduced-motion:reduce) {.hero-logo,.hero-nav a,.insight-box{transition:none!important;}}
</style>
""", unsafe_allow_html=True)

try:
    counts = load_counts(str(DATA_PATH))
except (OSError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Could not load dashboard summary: {exc}")
    st.stop()

all_customers = int(counts["Customers"].sum())
all_cancelled = int(counts["Cancelled"].sum())
overall_pct = group_rate(counts)
plan_table = summarize(counts, ["SubscriptionType"]).set_index("SubscriptionType").reindex(PLANS)
highest_plan = plan_table["Rate"].idxmax()

st.markdown(f"""
<div class="hero">
  <div class="hero-eyebrow">Customer retention insights</div>
  <div class="hero-title">
    <div class="hero-logo" role="img" aria-label="Analytics chart logo">
      <svg width="39" height="39" viewBox="0 0 48 48" aria-hidden="true">
        <rect x="5" y="29" width="8" height="13" rx="2" fill="#B2D1FF"/>
        <rect x="19" y="23" width="8" height="19" rx="2" fill="#80DEC7"/>
        <rect x="33" y="15" width="8" height="27" rx="2" fill="#E0E9FF"/>
        <path d="M7 19L18 11L27 16L40 5M32 5H40V13" stroke="#fff"
              stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <h1>Customer churn &amp; subscriptions</h1>
  </div>
  <p>Explore subscription plans, monthly charges and cancellation patterns through
     three interactive visualisations and live, filter-driven key takeaways.</p>
  <div class="hero-tags"><span>{all_customers:,} customer records</span>
    <span>3 interactive charts</span><span>Live key takeaways</span>
    <span>Subscription and pricing analysis</span></div>
  <div class="hero-nav"><a href="#plan-comparison">Plan comparison ↓</a>
    <a href="#charge-trends">Charge trends ↓</a>
    <a href="#plan-pricing-heatmap">Plan × pricing heatmap ↓</a></div>
</div>
""", unsafe_allow_html=True)

st.write("")
st.markdown('<div class="section-label">At a glance</div>', unsafe_allow_html=True)
for col, title, val, note, highlight in zip(
    st.columns(4, gap="small"),
    ["Customers analysed", "Cancelled subscriptions", "Cancellation rate", "Highest-cancellation plan"],
    [f"{all_customers:,}", f"{all_cancelled:,}", f"{overall_pct:.2f}%", highest_plan],
    ["Unique customer records", "Churn = 1", "Overall population", f"{plan_table.loc[highest_plan, 'Rate']:.2f}% cancelled"],
    [False, False, True, False],
):
    with col:
        extra = " metric-highlight" if highlight else ""
        st.markdown(
            f'<div class="metric-card{extra}"><div class="metric-label">{html.escape(title)}</div>'
            f'<div class="metric-value">{html.escape(val)}</div>'
            f'<div class="metric-note">{html.escape(note)}</div></div>',
            unsafe_allow_html=True,
        )

st.write("")
st.markdown('<div class="section-label">Interactive exploration</div>', unsafe_allow_html=True)
f1, f2, f3 = st.columns([1.4, 1.6, 1.15], gap="medium")
with f1:
    selected_plan = st.selectbox("Subscription plan", [ALL, *PLANS], index=0,
                                 help="Controls highlighted bars, line chart and key takeaways.")
with f2:
    selected_band = st.selectbox("Monthly-charge band", [ALL_BANDS, *BANDS], index=0,
                                 help="Highlights heatmap cells and updates key takeaways.")
with f3:
    compare_lines = st.checkbox("Compare all plans on trend", value=False,
                                help="Shows separate lines for Basic, Standard and Premium.")

st.write("")
st.markdown('<div id="plan-comparison" class="section-label">01 / Subscription plans</div>'
            '<div class="section-title">Which plan has the highest cancellation rate?</div>'
            '<div class="section-sub">Percentages compare each plan using its own customer base. '
            'Select a plan above to highlight its bar.</div>', unsafe_allow_html=True)
c1, c2 = st.columns([2.9, 1.15], gap="large")
with c1:
    with st.container(border=True):
        st.plotly_chart(plan_chart(counts, selected_plan), width="stretch", theme=None,
                        config={"displaylogo": False})
with c2:
    insight_box("Plan insight · live", *plan_insight(counts, selected_plan), css_class="insight-accent")

st.write("")
st.markdown('<div id="charge-trends" class="section-label">02 / Monthly charges</div>'
            '<div class="section-title">How does cancellation change across charge bands?</div>'
            '<div class="section-sub">Five ordered price ranges, not dates. The selected plan changes the '
            'line and the insight; switch on comparison to see all three plans.</div>', unsafe_allow_html=True)
c3, c4 = st.columns([2.9, 1.15], gap="large")
with c3:
    with st.container(border=True):
        st.plotly_chart(trend_chart(counts, selected_plan, compare_lines, selected_band), width="stretch", theme=None,
                        config={"displaylogo": False})
with c4:
    insight_box("Price trend · live", *trend_insight(counts, selected_plan, selected_band))

st.write("")
st.markdown('<div id="plan-pricing-heatmap" class="section-label">03 / Plan × pricing</div>'
            '<div class="section-title">Where are cancellation rates highest?</div>'
            '<div class="section-sub">Each tile represents one subscription plan and charge band. '
            'Darker colours indicate higher cancellation rates; hover for counts. '
            'Orange borders highlight the current filter selection.</div>', unsafe_allow_html=True)
c5, c6 = st.columns([2.9, 1.25], gap="large")
with c5:
    with st.container(border=True):
        st.plotly_chart(heatmap_chart(counts, selected_plan, selected_band),
                        width="stretch", theme=None, config={"displaylogo": False})
with c6:
    st.markdown('<div class="section-label">Live key takeaways</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Updated whenever you change the filters above.</div>',
                unsafe_allow_html=True)
    insight_box("Plan comparison", *plan_insight(counts, selected_plan))
    insight_box("Selected pricing", *trend_insight(counts, selected_plan, selected_band))
    insight_box("Highest-rate segment in focus", *hotspot_insight(counts, selected_plan, selected_band),
                css_class="insight-accent")

# Share the exact aggregated records underlying the current filter selection.
export_rows = selected_rows(counts, selected_plan, selected_band).copy()
export_rows["Retained"] = export_rows["Customers"] - export_rows["Cancelled"]
export_rows["CancellationRatePct"] = (
    100 * export_rows["Cancelled"] / export_rows["Customers"].replace(0, float("nan"))
).round(4)
st.download_button(
    "↓ Download selected heatmap data (CSV)",
    data=export_rows.to_csv(index=False).encode("utf-8-sig"),
    file_name="subscription_pricing_selected_summary.csv",
    mime="text/csv",
    help="Download the anonymised plan-by-charge-group counts that match your current filters.",
)
