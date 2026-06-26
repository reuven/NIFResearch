# Israeli Prospect-Research Source Catalog

**Date:** 2026-06-26
**Status:** Research deliverable (the "explore what's possible" core of the project)
**Companion doc:** `../specs/2026-06-26-nifresearch-prospect-research-design.md`

This catalog maps the Israeli data-source landscape for donor/prospect research.
For each source: what it contains, which input identifier queries it, how it's
accessed, its legal classification, cost, and reliability notes. Classifications:
`official_public` / `licensed` / `grey_market`.

---

## Executive summary — what's actually possible in Israel

Six findings reshape the project, and one of them changes our live-slice choice:

1. **The core gap is reverse lookup: there is no official "person → affiliations"
   index in Israel.** Every official registry (companies, amutot, land, trusts) is
   keyed by *entity* number/name or *parcel*, **never by a person**. You cannot ask
   "which boards does this person sit on." To answer that, you must build your own
   reverse index by ingesting entity records and extracting the people — or buy a
   commercial aggregator. This is the central engineering reality.

2. **Of the four inputs, only `name` is broadly useful — and it's ambiguous.**
   - `email` keys almost nothing Israeli (only Gravatar + breach-validation via HIBP).
   - `phone` keys only grey-market caller-ID apps.
   - `id_number (ת"ז)` is the golden key for official records **but there is no
     legal public service that maps a name/ID to an address**, and holding ת"ז
     triggers the strictest privacy provisions.
   - `name` works against most sources but collides badly (common Hebrew names).
   **Entity resolution / disambiguation is therefore THE hard problem**, not an edge case.

3. **Israeli individual *giving history* is essentially not public.** Transparency
   law targets the *recipient organization*, not the donor. What's public is board/
   officer membership and org financials — not who donated. Quantified named giving
   comes mainly from **US IRS 990-PF** (private foundations, donor names visible) for
   Israeli-American donors, and from **manual OSINT** (donor walls, gala journals).

4. **The strongest *legal* wins are clean and free:**
   - **Professional licensing registries** — doctors, lawyers, CPAs, engineers,
     etc. — are **name-searchable, official, free**, and instantly yield profession +
     seniority. This is the single best thing you can do from just a name.
   - **`data.gov.il` CKAN APIs** — companies & amutot master data via a clean,
     free, no-auth JSON API (entity-level).
   - **Address → affluence** via **nadlan.gov.il** (sale prices) + **CBS
     socioeconomic index** (1–10 decile per statistical area) — robust, official,
     free, and directly answers "where they live / roughly what they earn."
   - **Insolvency registry** (name-searchable financial-distress flag) and **Dun's
     100** (free, name-searchable executive/wealth rankings).

5. **Grey-market data exists and is legally radioactive.** Reverse-phone apps,
   people-search brokers, and — critically — freely-circulating **breach dumps of the
   entire population/voter registry** (Agron 2006; Elector 2020). **Amendment 13**
   (in force 14 Aug 2025) sharply raised exposure: multi-million-NIS sanctions and
   the right for individuals to **sue without proving harm**. Catalog-only; hard-block
   breach data.

6. **Revised live-slice recommendation (see §8).** Our spec guessed GuideStar +
   Companies Registrar. The research says: lead with **`data.gov.il` CKAN (companies
   + amutot)** and a **professional-licensing registry** — both are clean **free
   APIs/datasets** keyed on name, no fragile scraping. GuideStar (board members)
   stays valuable but needs headless-browser scraping → phase 2.

---

## Cross-cutting: which identifier unlocks what

| Input | Unlocks (legal) | Notes |
|---|---|---|
| **Name** | Professional registries, company/amuta fuzzy match, Dun's 100, courts/insolvency, news, GuideStar (via org), social | Universal key; **disambiguation is the bottleneck**. Search Hebrew + transliteration. |
| **Email** | Gravatar (weak), HIBP (validation only), B2B enrichment brokers (grey) | Treat as a *contactability* field, not an enrichment key, for Israeli sources. |
| **Phone** | Grey-market caller-ID only; thin B144 | No clean legal reverse-phone path. |
| **ID (ת"ז)** | Disambiguation inside official lookups; licensed KYC vendors | No legal name/ID→address service. Most privacy-sensitive to store. |
| **Address** (derived) | nadlan.gov.il valuation; CBS affluence decile; Tabu ownership | The richest *legal* wealth signal — but you must obtain the address lawfully first. |

---

## 1. Official government registries

**Most promising for live integration:** `data.gov.il` CKAN — free, no-auth JSON API
exposing the Companies, Amutot/PBC, Partnerships, and Hekdeshot registries as
queryable datastores. Critical limit: these are **entity-level only** (no directors/
officers/board members). People come from GuideStar (§2), paid per-company extracts,
or public-company filings (MAYA/MAGNA).

### 1.1 Companies Registrar — open dataset (`ica_companies`)
- **Contents:** ~727k companies: number, He/En name, type, status, purpose, incorporation date, "violating company" flag, last annual-report year, address. **No directors/shareholders.**
- **Key:** company number or name (free-text `q`). **Not person-searchable.**
- **Access:** CKAN API, no auth. `GET https://data.gov.il/api/3/action/datastore_search?resource_id=f004176c-b85f-4542-8901-7b3176f9a054&q=<term>`; SQL via `datastore_search_sql`; bulk CSV.
- **Class:** official_public · **Cost:** free · **URL:** https://data.gov.il/dataset/ica_companies
- **Notes:** Authoritative; Hebrew/RTL field names + values. Good for enriching a known company; useless alone for person→company.

### 1.2 Companies Registrar — per-company extract (נסח חברה)
- **Contents:** The data the open dataset omits — **directors & shareholders** (names, addresses, %), liens, violating-company flag. (Company-held register is the legal source of truth.)
- **Key:** company number/name (per-entity). Not person-searchable.
- **Access:** Public web lookup + paid extract; **no API** (JS portal, anti-bot). `https://ica.justice.gov.il/Request/OpenRequest?rt=CompanyExtract`
- **Class:** official_public · **Cost:** ~₪11/extract (free tier = company basics only, no officers) · **URL:** https://ica.justice.gov.il/
- **Notes:** The realistic path to private-company officers — but one company at a time, paid, scrape-hostile.

### 1.3 Partnerships Registrar — open dataset (`ica_partnerships`)
- ~28.7k partnerships; entity-level only (no partner names in open data; names via paid extract). CKAN `resource_id=139aa193-fabb-4f6b-a71b-0bb40fd73eb2`. official_public, free. https://data.gov.il/dataset/ica_partnerships

### 1.4 Amutot & Public-Benefit Companies — open dataset (`moj-amutot`)
- **Contents:** ~75k amutot: number, dates, He/En name, status, activity, last report year, **revenue, expenses, # volunteers/employees/members**, purposes, address. Separate resource: **ניהול תקין (proper-management) certificate** status (~328k records) — key for donor due diligence. Plus PBC (חל"צ) and foreign-political-entity donations resources. **No board members in open data.**
- **Key:** amuta number or name. Not person-searchable.
- **Access:** CKAN API, no auth. Amutot `resource_id=be5b7935-3922-45d4-9638-08871b17ec95`; nihul-takin `cb12ac14-7429-4268-bc03-460f48157858`; foreign-state donations `35cb40b5-3f13-4bca-9ce2-488085913107`.
- **Class:** official_public · **Cost:** free · **URL:** https://data.gov.il/dataset/moj-amutot
- **Notes:** Excellent org financials + good-standing. Board names require GuideStar (§2.x).

### 1.5 Charitable Trusts Registrar — open dataset (`hekdeshot`)
- ~3.3k trusts: file number, dates, name, purposes, funding method, status; plus real-estate-holdings and asset-balance resources (high wealth signal). Trustees not in open data. CKAN `resource_id=f70898aa-9d47-47b2-b1bc-ec736b76bfe2`. official_public, free. https://data.gov.il/dataset/hekdeshot

### 1.6 ISA/TASE public-company filings — MAYA & MAGNA
- **Contents:** The **only** official source explicitly tying *named individuals* to roles + holdings: directors, senior officers (נושאי משרה), interested parties (בעלי עניין), and **Regulation-21 tables naming the 5 highest-paid officers with compensation**. Public companies only (~a small slice).
- **Key:** company/security; person names appear *inside* filing text (Google site-search can surface a name).
- **Access:** MAYA web + scrapable PDF/HTML (`mayafiles.tase.co.il`); **TASE Data Hub** is the sanctioned *paid* API. MAGNA = regulator's citation-grade root (free, web/XBRL).
- **Class:** official_public (data); licensed (Data Hub API) · **Cost:** web free; Data Hub paid (unverified) · **URLs:** https://maya.tase.co.il/en · https://www.magna.isa.gov.il/
- **Notes:** Best for public-company exec pay; parsing Hebrew/RTL holdings tables is non-trivial. Prefer licensing the Data Hub feed over scraping for a real product.

---

## 2. Non-profit, charity & giving-history data

**Bottom line:** Public & structured in Israel = board/officer membership + org
financials + ניהול תקין status. Public donor *names* = only large/foreign-government
donors in mandated filings (rare). Quantified individual giving = mainly **US 990-PF**
+ manual OSINT.

### 2.1 GuideStar Israel (גיידסטאר)
- **Contents:** Official MoJ window into every amuta/PBC: objectives, number, address, **named office-holders / board / audit committee**, financial + narrative reports, ניהול תקין status. **Best free source for board/officer affiliation.** No per-donor ledger.
- **Key:** organization name/number (person names appear only inside an opened profile — **no board-member-name search**).
- **Access:** Free public web; **no official API** (the US Candid "GuideStar API" is unrelated). Programmatic use = **headless-browser scrape** (JS-rendered). Check ToS/robots.
- **Class:** official_public · **Cost:** free · **URL:** https://www.guidestar.org.il/ (note `.org.il`)
- **Notes:** Authoritative for ~75k orgs; the realistic at-scale source for board names. Pair with §1.4 for financials.

### 2.2 US IRS Form 990 / 990-PF (ProPublica Nonprofit Explorer)
- **Contents:** **The best giving-history source for Israeli-American / cross-border donors.** **990-PF (private foundations):** named grantees + amounts, and **substantial-contributor names are PUBLIC** — a family foundation's 990-PF reveals the family's giving. **990 (public charities):** named officers/directors, but **Schedule B donor names are redacted**.
- **Key:** person name (foundations/boards bearing it) or org/EIN.
- **Access:** Free web + bulk + **public API**; machine-readable XML back to ~2001. https://projects.propublica.org/nonprofits/
- **Class:** official_public · **Cost:** free
- **Notes:** The single best place to find *quantified named giving* relevant to Israeli causes. Remember the asymmetry (990-PF visible; 990 Schedule B hidden).

### 2.3 Supporting / context sources
- **data.gov.il `moj-amutot`** (§1.4) — bulk amuta index to drive GuideStar resolution. official_public, free.
- **Registrar annual reports** (דוח כספי + דוח מילולי): named board/officers, top-5 salaries; **large-donor disclosure** only above high thresholds (~₪100k single donor; foreign-political-entity donations >~₪20k must name the donor). Free PDFs; OCR often needed.
- **Midot** (midot.org.il) — org effectiveness ratings; no donor data; selective coverage.
- **NGO Monitor funding DB** — org-level funder mapping from filings; has an editorial viewpoint (figures solid, framing advocacy).
- **Candid / Foundation Directory** (licensed, paid) — better search over US 990 data; US-only coverage.
- **Honor rolls / gala journals / donor walls** (manual OSINT) — where Israeli *individual* giving actually becomes visible (tiers/ranges, not exact amounts). Highest-signal substitute for the structured donor DB that doesn't exist.

---

## 3. Real-estate, address & wealth-signal data

**Key answers:** **Name/ID → address: NOT legally possible** via official channels
(population & voter registries are closed; Land Registry is parcel-indexed). **Address
→ affluence: YES, robustly, cheaply, officially.** So acquire the address lawfully
(from the donor, public company ownership, or news), then run address→wealth.

### 3.1 nadlan.gov.il — Real-Estate Transactions DB (Tax Authority)
- **Contents:** Historical **sale prices** nationwide by address/street/neighborhood/parcel: date, declared price, m², rooms, floor, year built. **Anonymized — no buyer/seller names.**
- **Key:** address / street / neighborhood / city / parcel.
- **Access:** Free public web + map; **no official API** but a JSON endpoint backs it (`nadlan.gov.il` / `nadlan.taxes.gov.il/svinfonadlan2010`) — de-facto scrape. Also on GovMap.
- **Class:** official_public · **Cost:** free · **URL:** https://www.nadlan.gov.il/
- **Notes:** Strongest *legal* affluence input — values a known address. Hebrew street-name spelling variants complicate matching.

### 3.2 CBS Socioeconomic Index (מדד חברתי-כלכלי)
- **Contents:** Affluence **decile 1–10** (and 1–20 cluster) **per statistical area inside cities** — turns an address into an income-proxy percentile. Built from ~14 variables (income, education, vehicles, pensions…).
- **Key:** locality + statistical area (derive from address via GovMap).
- **Access:** Free CBS Excel/CSV + GovMap GIS boundaries. Latest: 2021 data, published 2024.
- **Class:** official_public · **Cost:** free · **URL:** https://www.cbs.gov.il/ (→ "מדד חברתי-כלכלי")
- **Notes:** Best legal affluence proxy. Caveat: area average (ecological fallacy) — combine with the specific property's nadlan value. Municipality-only is too coarse for big cities.

### 3.3 Land Registry — Tabu extract (נסח טאבו)
- **Contents:** Per-parcel "ID card": **registered owners (name + ת"ז)**, shares, mortgages, liens, warnings.
- **Key:** **גוש/חלקה (block/parcel)** or address (portal resolves address→parcel). **NOT searchable by owner name/ID** — confirms ownership of a *known* property only.
- **Access:** Official web portal, ~₪18 digitally-signed PDF; **no API**. https://www.gov.il/he/service/land_registration_extract
- **Class:** official_public · **Cost:** ~₪18 (resellers overcharge — use gov.il)
- **Notes:** Properties held via company/trust hide the individual. "טאבו לפי ת"ז" commercial services only catch *mortgaged/liened* parcels — a null result ≠ owns nothing (grey/partial).

### 3.4 Municipal data (arnona zones, permits, GIS)
- Address/parcel-keyed; per-city portals (no unified API). Tariff zones + building permits = supplementary wealth signals (e.g., permitted pool/extension). Free; labor-intensive; not name-searchable.

### 3.5 Voter Registry (פנקס הבוחרים) — **closed / off-limits**
- Contains name + parent + ת"ז + DOB + **address** for ~6.5M voters. By law released **only to political parties for elections** under signed-use restriction. **grey_market / unlawful** for prospect research. Notorious leaks (2020 Elector breach) circulate — **do not ingest** (see §6).

---

## 4. Professional, employment & business-credit data

Three tiers: **(1)** statutory licensing registries (free, official, name-searchable —
the best name→profession win); **(2)** employer discovery (LinkedIn/brokers/directories);
**(3)** business/wealth standing (Dun's 100 + rich lists).

### 4.1 Professional licensing registries (free, official_public, name-searchable)
Minimum return: **name + license number + profession/specialty + status**; often
**city + seniority signal** (grant date or license-number sequence).

- **Medical & health practitioners (MoH):** ~56k physicians (72 specialties), dentists, pharmacists, psychologists, physios, dietitians, etc. Name or license #. Web UI is bot-blocked → **use the open dataset** `https://data.gov.il/dataset/database-of-doctors-licenses-moh`. UI: https://practitioners.health.gov.il/ . Gives profession + seniority, **not employer** (pair with §4.2 hospital/HMO directories).
- **Lawyers — Israel Bar (ספר עורכי הדין):** name, license #, city, fields; admission year derivable from license-number sequence. CC-BY dataset: https://www.odata.org.il/dataset/israelbarmembers (live portal WAF-blocked). "Private use" labeled — fine for one-off, riskier for bulk.
- **CPAs (Council of CPAs):** name, license #, city, **status** (active/suspended/revoked). Dataset: https://data.gov.il/dataset/cpalist
- **Engineers & architects:** verification-oriented (wants ID + name) — weak for discovery. https://data.labor.gov.il/EngineersAndArchitects.aspx
- **Social workers:** needs ID *or* first+last together. Dataset: https://data.gov.il/dataset/social-workers-registration
- **Others (all free/official, name-searchable):** real-estate appraisers (`data.gov.il/dataset/shamaim`), land surveyors, notaries (`data.gov.il/dataset/notary` — notary ⇒ senior lawyer, 10+ yrs), insurance/pension agents (Capital Market Authority), patent attorneys, tax advisors.
- **Automation tip:** prefer the `data.gov.il`/`odata.org.il` open datasets over scraping the bot-blocked search UIs.

### 4.2 Employer discovery
- **LinkedIn:** richest for title/employer/seniority, **but no compliant people-search/scrape API**; scraping breaches ToS (hiQ won on CFAA, but LinkedIn enforces via contract; Proxycurl was sued & shut down early 2025). Manual `"Name" site:linkedin.com/in` is the safe path. Treat as analyst-assist, not pipeline.
- **B2B enrichment brokers** (the realistic automated path, **grey/licensed**): **Lusha** and **Bright Data** (both Israeli, more defensible — claim no LinkedIn scraping / won *Meta v. Bright Data* 2024), Apollo, RocketReach, ContactOut (most LinkedIn-derived → highest risk). Avoid PhantomBuster/logged-in-session tools. Confirm the license permits *prospect/donor research* (most license for B2B *sales*); treat output as personal data under Privacy Law + GDPR.
- **University faculty directories / CRIS-Pure portals** (free, official, name-searchable): name, title, dept, email. HUJI, TAU, Technion, BGU, Bar-Ilan, Haifa, Open U.
- **Hospital & HMO "find a doctor" directories** (free, official, by name → **workplace** + specialty — the piece the MoH registry lacks): Ichilov (clean `/dr/<slug>/` URLs), Rambam, Maccabi, Sheba, Hadassah, Clalit.
- **ORCID** (academics): free public API, much data CC0 — `/<iD>/employments` gives current employer. Most automation-friendly.

### 4.3 Business-credit & wealth standing
- **Dun's 100 (duns100.co.il) — GOLD, mostly FREE.** One of the few resources where a **name** directly yields seniority + standing: leading-executives lists, **annual richest-Israelis ranking**, top law/accounting firm rankings. Inclusion is partly opt-in (absence ≠ insignificance). official_public-style, free to read.
- **Dun & Bradstreet Israel / CofaceBdi** (licensed, paid): deepest commercial DB (~500k companies) — credit/risk reports + **officer/director/shareholder identification** + ownership %. Company-keyed (reach person via company report). Strong owner-operator income proxy. Quote-based pricing.
- **Journalistic rich lists** (free, person-keyed wealth proxies): **Forbes Israel** (2026: 52 Israeli billionaires), **TheMarker 500** (reaches below billionaire tier), Globes/Calcalist (exit/liquidity events = donor-timing signal).
- **Government salary transparency:** Commissioner of Wages (position-keyed, usually *not* named); Government Companies Authority (named top-earners, but stale ~2018).

### 4.4 Hard legal limit — individual consumer credit is OFF-LIMITS
The **Credit Data Law 2016** places individual consumer-credit data in the Bank of
Israel register; bureaus may pull it **only with the person's authorization**. **No
lawful unconsented access** to a prospect's credit score/history. Stay on the
business/company + public-rich-list side.

---

## 5. Social media, open web, news, court/legal & academic (OSINT)

**Reality:** rich for *prominent* prospects (business press, Wikipedia, courts,
insolvency), **sparse** for typical donors (maybe a Facebook/LinkedIn profile).
**Disambiguation** is the core obstacle; **none of these free sources accept email or
ת"ז** as a query key. Social-media scraping is grey/ToS-violating at scale.

### 5.1 High-value, defensible (official_public / licensed)
- **Israeli business press — Globes / Calcalist / TheMarker** (official_public): best open net-worth signal for prominent businesspeople; TheMarker's 500-richest list. Free headlines; ~₪20–50/mo archives. Wealth-/prominence-gated.
- **Insolvency Authority registry (חדלות פירעון)** (official_public, free, **name-searchable**): cleanest financial-distress signal; threshold ~₪176,923 (2026). A positive hit is a strong negative signal. https://insolvency.justice.gov.il
- **Nevo / Psakdin** (licensed, paid): the practical **party-name-searchable** way to find litigation involvement (Nevo authoritative/pricier; Psakdin cheaper free tier). Court records are public but only practically searchable by name in these commercial DBs.
- **Net HaMishpat / Supreme Court search** (official_public, free): mostly per-case-number; Supreme Court has free full-text search. No free cross-court name search — that's what Nevo/Psakdin sell.
- **Commercial KYC vendors (e.g., KYC Israel)** (licensed): bundle litigation + bankruptcy + enforcement into one disambiguated report (name + ת"ז/DOB). Per-report fee; suits high-value prospects. Verify lawful basis before integrating.
- **Enforcement Authority (הוצאה לפועל)** (official_public records, access-gated): no open third-party name search — only via licensed vendors.
- **Hebrew Wikipedia** (official_public, CC, **MediaWiki API, ToS-friendly**): only notable people, but excellent for them; references are a springboard.
- **Google Scholar / university faculty pages** (official_public): academic niche — publications, grants, affiliations, often direct email/CV.

### 5.2 Social platforms (grey_market for automation; manual viewing softer)
- **Facebook:** dominant in Israel (~7.6M users); name-keyed; **email/phone lookup removed** post-2018. No compliant people-search API; severe disambiguation. Manual analyst only.
- **LinkedIn:** strong professional/capacity signal; no compliant people-search API; scraping = ban + ToS risk. Manual or licensed provider.
- **X / Instagram:** color/affinity for vocal/prominent people; handles rarely map to legal names; paid APIs.

### 5.3 Email-keyed (the only email-keyed sources)
- **Gravatar** (official_public): email-hash → public avatar/profile *if* one exists. Low hit-rate for Israelis. Free.
- **Have I Been Pwned** (official_public): **email validation/aging only** — confirms the email is real and roughly how long it's existed; **does not identify the owner**. Must not be presented as enrichment. Paid API (~$4/mo).

---

## 6. Grey-market / commercial data brokers — **catalog-only, disabled-by-default**

Documented to define what we deliberately **do not** integrate, and to hard-block the
breach material. Legal anchor: **Privacy Protection Law (1981) + Amendment 13** (in
force **14 Aug 2025**) — broadened "sensitive data," mandatory DPOs, data-broker
duties, PPA criminal-investigation powers, multi-million-NIS sanctions, and individuals
can **sue without proving harm** (statutory/exemplary damages). PI activity is governed
separately by the **Private Investigators and Security Services Law (1972)**.

### 6.1 Crowd-sourced caller-ID / reverse-phone apps (grey_market)
- **CallApp, Sync.me** (Israeli), **Truecaller** (foreign, ubiquitous): build name↔number maps from *other users'* uploaded address books → the data subject never consented. Truecaller is under a Swedish IMY investigation (Feb 2025) and skips phonebook upload for EU users — illustrating the exact consent gap Amendment 13 polices. Generic foreign reverse-lookup sites (WhoseNo, Free-Lookup, Scannero, etc.): opaque sourcing, lead-gen funnels, may recycle leaked data. **Avoid.**

### 6.2 Commercial list brokers (borderline)
- **D&B Israel marketing lists / dun'sguide:** the legitimate option — but **B2B/organizational** only, with direct-marketing duties (registration, opt-out, source disclosure). Not for enriching private individuals. Disabled by default pending legal review.

### 6.3 International people-search brokers (grey_market for Israeli subjects)
- **Spokeo / BeenVerified / Whitepages:** US-records-based; thin, error-prone Israeli coverage; may incorporate recycled leaks. **Pipl:** large identity graph, positioned for fraud/identity-verification — *not* unconsented donor profiling. No lawful basis for this use case. **Avoid.**

### 6.4 Licensed private investigators (חוקר פרטי) — separate legal track
- Skip-tracing/background via **MoJ-licensed PIs** under the 1972 Law (only licensed PIs may lawfully surveil). The PI shield covers the *investigative act*, not *your* downstream database — you remain controller with full Amendment-13 duties. Out of scope for an automated tool; if ever needed, case-by-case via a vetted PI, never an API feed.

### 6.5 B2B enrichment APIs (Clearbit-class)
- **Lusha** (Israeli), HubSpot Breeze (ex-Clearbit), Hunter, ZoomInfo, Apollo, Cognism, PDL. Strong B2B coverage; returning a person's **mobile/personal email** from a name is exactly what Amendment 13 scrutinizes. Even "B2B" enrichment of named individuals lacks a clean basis for a nonprofit donor tool. Disabled by default; if ever allowed, organizational data only, with DPO sign-off + opt-out.

### 6.6 Breached government databases — **NEVER source, store, or query**
- **"Agron 2006"** — stolen Population Registry (~9M records: ת"ז, names, addresses, DOB, family links), circulated via torrents.
- **Elector / Likud leak (Feb 2020)** — entire voter registry (~6.5M adults: name, address, often cellphone) exposed via the Elector app.
- **Recurring re-leaks** (e.g., Shas breach) — recycled Agron/Elector data.
- **Free availability creates no lawful basis.** Implement hard-block denylists; never ingest.

**Why all of §6 stays disabled-by-default:** no clean lawful basis for unconsented
donor enrichment; Amendment 13 made the downside asymmetric (uncapped class exposure
vs. marginal benefit); breach data is unavoidable in this market and indistinguishable
from lawful data inside broker feeds; the only arguably-lawful lanes (B2B D&B, licensed
PI) leave *you* as controller with full duties and don't belong in an always-on pipeline.

---

## 7. Implications for the architecture

- **Plugins must declare `required_inputs` precisely** — most useful sources need
  `name` (and benefit from a disambiguator), a derived `address`, or a company number;
  `email`/`phone` satisfy almost nothing legal. The orchestrator's input-gating and
  the report's "sources skipped" section are doing real work here.
- **Entity resolution is a first-class component, not a nicety.** Plan for
  candidate-set output with confidence + provenance, Hebrew/transliteration-tolerant
  matching, and human-in-the-loop confirmation — never assert a single identity.
- **An address-enrichment sub-pipeline is high value and clean:** address → CBS
  decile + nadlan valuation directly answers the donor-relations head's "where they
  live / roughly what they earn," using only free official data.
- **`classification` gating is the compliance lever:** ship `official_public` on,
  `licensed` behind config, `grey_market` off + denylisted, breach-data hard-blocked.

## 8. Recommended live slice (revises spec §8)

Pick sources that are **clean free APIs/datasets, official_public, and keyed on the
identifiers we actually have** — minimizing fragile scraping for the prototype:

1. **`data.gov.il` CKAN — Amutot dataset (`moj-amutot`)** *(and Companies as a near-twin)*.
   Free no-auth JSON API, name/number searchable, rich org financials + ניהול תקין.
   Cleanest possible plugin; proves the pattern with zero scraping.
2. **A professional-licensing registry** — e.g., **lawyers** (CC-BY `odata.org.il`
   dataset) or **doctors** (`data.gov.il`). The one thing that genuinely works from a
   bare **name**, free and official, returning profession + seniority.
3. **(Stretch) Address → affluence**: CBS socioeconomic-index lookup + nadlan
   valuation, demoed with a manually-entered address — directly showcases the
   headline "where they live / how much they earn" use case.
4. **1–2 mock plugins** to exercise the orchestrator/merge/report safely; develop and
   demo against **public figures** (e.g. philanthropists on nonprofit boards).

**Deferred to phase 2 (scraping/paid, higher value):** GuideStar board members
(headless browser), Companies extract officers (₪11/extract), MAYA exec-pay,
ProPublica 990-PF for Israeli-American donors, insolvency registry.

---

## Appendix — honest uncertainties / to re-verify before launch
- Exact current fees: company extract / נסח, Tabu (~₪17–18), TASE Data Hub pricing.
- Whether MAGNA XBRL exposes a documented machine API vs web-only.
- GuideStar ToS/robots stance on automated access; Bar dataset opt-outs & freshness.
- JS-rendered gov portals (ICA, GuideStar, TASE, MoH practitioners) return empty to
  plain fetch — confirm via headless browser before committing to those integrations.
- Several figures were verified via search snippets / secondary summaries (gov.il
  blocks automated fetching) — re-confirm on live pages.
