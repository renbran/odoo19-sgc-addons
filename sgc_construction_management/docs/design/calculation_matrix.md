# Financial & Progress Calculation Matrix

## 1. Work In Progress (WIP) - Contractor Method
**Formula:**
1. **Completion %** = `Total Cost (Invoices + Expenses) / Estimated Total Cost (BOQ Cost)`
2. **Earned Revenue** = `Completion % * Contract Value`
3. **Over/Under Billing** = `Earned Revenue - Total Billed (Posted Invoices)`
4. **WIP Asset** = `Max(0, Over/Under Billing)` if positive.

## 2. Cost-to-Complete (CTC)
**Formula:**
1. **Current Cost** = `Actual Expenses + Labor + Equipment`
2. **Forecasted Total Cost** = `Current Cost / Current Progress %` (Linear) OR `Manual Estimate`
3. **Cost to Complete** = `Forecasted Total Cost - Current Cost`

## 3. Cash Flow Forecast (S-Curve)
**Method:**
* Cumulative planned progress mapped over time.
* **Forecasted Monthly Cash In** = `(Planned Progress % This Month - Last Month) * Contract Value`
* Lag of 30-60 days applied for "Cash Collection" forecast.

## 4. Labor Productivity
**Formula:**
* **Unit Productivity** = `Actual Progress (Quantity) / Total Man-hours spent`
* **Efficiency Index** = `Actual Productivity / Standard Productivity`
