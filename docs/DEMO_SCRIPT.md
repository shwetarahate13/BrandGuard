# BrandGuard: 3-Minute Judge Demo Walkthrough

Welcome, Judges! Follow this step-by-step walkthrough to test the live **BrandGuard** build in under 3 minutes using the pre-seeded demo accounts.

---

## ⏱️ Minute 1: Log In & Experience the Hero Review Screen

1. **Sign In as Creator**:
   - On the login screen, click the **Creator (Janvi Thakre)** quick-fill button.
   - Click **Sign In to BrandGuard**.
2. **Open a Sample Submission**:
   - On the dashboard, click on the top submission: **"Fall Season Golden Oat Elixir Campaign"**.
3. **Explore the Hero Review Screen**:
   - **Left Column**: Notice the text has highlighted spans marking compliance issues. Click on the highlighted text `"clinically proven"` or `"world's best"`.
   - **Right Column**: Notice how the matching finding is highlighted.
   - **Grounded Citation**: Click the **Cited Source** accordion to reveal the exact quote from brand guideline clause `CLAIM-1`:
     > *"All nutritional, health, and sourcing claims must be backed by approved clinical testing..."*
   - **Word-Level Diff Fix (Improvement 1)**: Scroll to finding for `"revolutionary"`. Inspect the diff viewer showing:
     - <span style="color:red; text-decoration:line-through;">revolutionary</span>
     - <span style="color:green; font-weight:bold;">premium</span>
   - **Accept the Fix**: Click the black **Accept Fix** button.
     - *Notice*: The document text immediately updates to Version 2 with the fix cleanly applied!
4. **Submit for Approval**:
   - Click the black **Request Manager Review** button in the top right.
   - The status updates to `in_review`.

---

## ⏱️ Minute 2: Sign-Off Dossier (Manager & Reviewer Perspective)

1. **Switch to Brand Manager**:
   - Click the Log Out icon in the top right navbar.
   - Click the **Brand Manager (Shweta Rahate)** quick-fill button, then click **Sign In**.
2. **Review Pending Submissions**:
   - On the dashboard, click the **In Review** tab.
   - Select **"Fall Season Golden Oat Elixir Campaign"**.
   - Click the **Approval Sign-Off View** button in the header.
3. **Inspect Version Comparison**:
   - Observe the side-by-side comparison between **Original Draft (v1)** and the **Current Revision (v2)** with creator accepted fixes.
   - Notice the audit trail timeline at the bottom showing every edit, timestamp, and author.
4. **Approve Copy**:
   - Click the green **Approve Copy** button.
   - Enter note: *"Compliance verified against approved claims policy. Approved for regional launch."*
   - Click **Confirm Decision**.
   - The submission status updates to `approved`.

---

## ⏱️ Minute 3: Insights & Source Management

1. **Governance Insights Dashboard**:
   - Click **Insights** in the top navigation bar.
   - Review the metrics:
     - **88% Fix Acceptance Rate**
     - Breakdown by Category (`unsupported_claim`, `tone`, `terminology`, `accessibility`)
     - Severity Distribution (`major`, `minor`, `critical`)
     - **Top Recurring Brand Violations** table showing where creators frequently encounter guideline friction.
2. **Approved Brand Sources**:
   - Click **Approved Sources** in the navbar.
   - Explore the **Approved Facts** tab: notice active certified facts alongside red **Expired Fact** badges (e.g. 2022 pricing of $28) used to detect outdated claims.
   - Click the **Re-index Chroma Vector Store** button to verify instant vector synchronization.
3. **Transparency Notice**:
   - Click the **mock/offline** (or **Claude**) pill in the top navbar.
   - Read the transparency modal explaining excerpt privacy, prompt injection defense, and the non-negotiable citation validator.

---

*Thank you for evaluating BrandGuard!*
