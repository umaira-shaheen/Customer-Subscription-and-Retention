# Customer Churn & Subscriptions — Streamlit Dashboard

A GitHub-ready Streamlit dashboard for **subscription plans and pricing**. Includes:

- **Plan comparison** bar chart (Basic, Standard, Premium)
- **Monthly-charge trend** line chart with plan comparison toggle
- **NEW: Plan × pricing heatmap** displaying 15 plan/charge-band cancellation rates; hover for counts
- **NEW: Live key takeaways** that update for the selected plan and charge band
- Four KPI cards, modern branded header and Streamlit Cloud-ready configuration

The presentation-only explanation, detailed tables and notes accordion requested removed earlier **are not included**.

## GitHub upload

Upload the **contents** of this folder to your repository, including `data/plan_charge_summary.csv` and `.streamlit/config.toml`.

```
app.py
requirements.txt
README.md
data/plan_charge_summary.csv
.streamlit/config.toml
```

The app includes a built-in fallback copy of the exact aggregated counts. If GitHub misses the `data/` folder, the dashboard still opens with the identical figures rather than crashing.

## Local run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Deploy

1. Commit files to GitHub.
2. On https://share.streamlit.io, select your repository and deployment branch.
3. Main file path: `app.py`.
4. Deploy or reboot the existing app.

## Updated data

`data/plan_charge_summary.csv` is the **15-row privacy-safe aggregated data**, calculated from the original customer-level CSV provided for this project: 3 plans × 5 ordered charge bands. It contains `SubscriptionType`, `ChargeBand`, `Customers`, `Cancelled`, `Retained`, and `CancellationRatePct`. The app recalculates percentages from the counts, so the CSV's descriptive rate column is not trusted as the denominator.

**Overall:** 243,787 unique customers, 44,182 cancelled (18.12%). `Churn = 1` is cancellation.

**Rate:** Cancelled ÷ Customers in the selected plan-and-band group × 100.

**Charge bands:** [4.99,8), [8,11), [11,14), [14,17), [17,20). Monthly charge currency is not identified in the supplied data, so the charts do not assume £ or $.

These results are **descriptive associations**, not evidence that pricing or plan choice causes cancellations.
