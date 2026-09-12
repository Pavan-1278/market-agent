Skill: SEC Filing Analysis

Goal

Identify material investor-relevant information in supplied filing text or excerpts.

Focus

Financial results, outlook, agreements, acquisitions, securities issuance, insider transactions, executive changes, legal/regulatory developments, risks, and customer/supplier changes.

Evidence Checks

Use the supplied issuer, form, filing date, event/reporting period, and amendments. Do not infer a form from the topic or a linked URL's existence.

Say "the filing states" rather than treating filing as independent verification. A summary of a filing is not the full filing.

Call language new or changed only when a comparison or explicit supported change is supplied. Without a prior version, do not claim boilerplate is unchanged.

Distinguish a proposed transaction from a completed one, a registration authorization from an actual issuance, and registered capacity from proceeds raised.

Distinguish open-market insider purchases from grants, exercises, transfers, or other transactions using supplied descriptions/codes and explanations; do not guess missing codes.

For financing, retain instrument, amount, pricing, conversion/repayment terms, and stated use of funds when provided. Do not invent dilution, cash benefit, or a percentage calculation.

Do not infer missing exhibits, materiality thresholds, legal conclusions, or stock-price effects.

Output

Retain the requested fields: filing_type, importance (integer 1–10), affected, key_change, and why_read.

Score the specific disclosure, not the form's existence: 7+ needs concrete material content; routine/unclear content stays lower. key_change should identify a supported development and any essential limitation. why_read is at most one sentence. Use "unknown" for an unidentified filing type when a string is required; do not fabricate one.