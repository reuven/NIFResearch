# Grey-market sources — operator reference

> **⚠️ DO NOT ENABLE WITHOUT LEGAL SIGN-OFF.** These are commercial data-broker /
> enrichment APIs. They are classified `grey_market` and are **double-gated**:
> they run only under the **PERMISSIVE** compliance mode AND only when their API
> key environment variable is set. By default they are blocked. Confirm a lawful
> basis under Israel's Privacy Protection Law (incl. Amendment 13) before enabling
> any of them for real data.
>
> **Breach-sourced datasets (leaked population/voter registries) are excluded by
> policy and are never integrated.**
>
> **Privacy notice:** when enabled, subject PII (email, phone — and the phone
> number in Twilio's request URL path) travels in outbound HTTPS requests to
> these third-party providers. Confirm this is acceptable under your legal basis
> before enabling any provider.

| Source | id | Input(s) | Env key(s) | Returns |
|--------|----|----------|------------|---------|
| Pipl | grey_pipl | name/email/phone | NIFRESEARCH_PIPL_API_KEY | address, employer, contact |
| Lusha | grey_lusha | name/email | NIFRESEARCH_LUSHA_API_KEY | role, employer, contact |
| Hunter.io | grey_hunter | email | NIFRESEARCH_HUNTER_API_KEY | email verification |
| NumVerify | grey_numverify | phone | NIFRESEARCH_NUMVERIFY_KEY | carrier/line, location |
| Twilio Lookup | grey_twilio | phone | NIFRESEARCH_TWILIO_SID + NIFRESEARCH_TWILIO_TOKEN | caller name |
| Apollo.io | grey_apollo | name/email | NIFRESEARCH_APOLLO_API_KEY | role, employer, contact |
| RocketReach | grey_rocketreach | name/email | NIFRESEARCH_ROCKETREACH_API_KEY | contact, employer, role |
| ContactOut | grey_contactout | email | NIFRESEARCH_CONTACTOUT_API_KEY | contact, employer |
| Clearbit/Breeze | grey_clearbit | email | NIFRESEARCH_CLEARBIT_API_KEY | employer, contact |
| People Data Labs | grey_pdl | name/email/phone | NIFRESEARCH_PDL_API_KEY | employer, address, contact |

Each grey fact is tagged `confidence=0.25`, carries the provider URL, and includes
`detail["caveat"] = "grey-market source — verify legal basis before use"`. The
report shows a warning banner whenever any grey source actually ran.

Exact endpoints/fields are representative and must be confirmed against current
provider documentation before relying on results.
