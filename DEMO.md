# Covered: 2-minute demo script

A home-care demo. Deterministic, no keys needed for this flow.

**Setup:** open the deployed URL (or `http://localhost:8000`). You land on the home-care journey.

## The script

**0:00 Frame it (say).**
"An older adult in Ontario needs help at home. The programs exist, but the paths are a maze. Covered gives one clear path and prepares the real application."

**0:15 Screen (do).** Fill the form:
- Age 68, lives in Ontario with OHIP: Yes
- Permanent physical disability: Yes
- Needs help with: Bathing and Dressing (hands-on care)
- Care needs steady for a year: Yes
- Can direct your own attendants: Yes
- Hours of help per week: 20

Click **Check my eligibility**.

**0:35 The fork (say + point).**
"Two ways to get home care. Because she can self-manage, Covered recommends Direct Funding, the self-managed route administered by CILT, and shows the other option too."

**0:45 The real budget (point).**
"This is not a placeholder. It is CILT's own formula: 86 attendant hours a month at $22, plus 21% employer costs, admin, and a 5% contingency. About $2,646 a month. And here are the real application sections, marked by who completes each."

**1:10 The honest ceiling (say).**
"Covered prepares and hands off. The person signs and sends it to CILT, and the interview panel decides. Nothing is filed automatically."

**1:20 The other side of the fork (do).**
Change "Can you direct your own attendants" to **Not sure**, check again.
"For someone who cannot self-manage, Covered leads with Ontario Health atHome, agency-arranged care, with the services and how to start."

**1:40 Why trust it (say).**
"Every rule is deterministic and auditable. A regression suite keeps it consistent and catches drift, and a policy drift checker verifies every dollar figure against its official government source, with a source link and a verified date on each program."

**1:55 Close (say).**
"One clear path, real numbers, real next steps, and we never pretend to submit what a human must. That is Covered."

## Optional add-ons (if time)
- **`/benefits`:** the broader screener for DTC, CDCP, Trillium and more, with source links.
- **Care team:** caregiver dashboard, clinician Part B coordination, agency console (behind auth).

## Fallback
The home-care flow is pure computation, so it works with no database, keys, or network beyond the page. If the deployed site is down, run `docker compose up` or `uvicorn app.main:app` locally and demo at `http://localhost:8000`.
