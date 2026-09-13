# Market Agent - development fixtures

**DEVELOPMENT DATA ONLY. Do not use this package as current market information or as evidence for a trade.**

## What is included

- `market_movers.json`: a partial September 11, 2026 snapshot reconstructed from the user's supplied console values and corresponding raw mover groups. It preserves the 17 candidates used by the recent script. This is not a recovered, complete Alpha Vantage response and was not independently verified.
- `FEIM_news.json`: four **synthetic** entries: an earnings scenario, an exact duplicate, a routine holdings story, and generic commentary.
- `TNON_news.json`: two **synthetic** reports of the same debt-repayment scenario, with deliberately missing financial context.
- `ACVA_news.json`, `SMR_news.json`, `MKDW_news.json`, and the other ticker files: intentionally empty **mock** responses. They exist so any supplied ticker has an explicit test file. An empty mock is not evidence of no real news.
- `manifest.json`: file mapping, replay time, fixed news window, provenance, and qualitative checks.
- `validate_fixtures.py`: a standard-library-only checker. It does not import the agent, load `.env`, or use either API.

The full original FEIM/TNON article payloads were not supplied in the conversation. The two mock event narratives echo selected figures seen in the console, but their wording and simulation timing are authored for this test. They must not be called original news articles, saved live API responses, or independently verified financial facts.

## Installation and safe first check

Copy the whole `test_data` folder into `C:\Users\Pavan\market-agent`.

```powershell
python test_data/validate_fixtures.py
```

This validation uses **zero Alpha Vantage calls and zero Claude calls**. No API key is required. It checks the JSON, file mapping, timestamps, duplicate/noise cases, and absence of credential fields.

## Important: data only, not yet connected to the agent

This package does not replace or modify `market_agent_test.py` or `alpha_vantage_cache.py`. Running the existing main script still uses its live Alpha Vantage path. The next coding step is an explicit development-data loader. Until that is added, use only the validator above to test this package.

The intended loader must:

1. Read the market and per-ticker news files from this directory rather than the API or live cache.
2. Display `DEVELOPMENT FIXTURE - NOT LIVE DATA` prominently and supply that status to Claude at each stage.
3. Use `manifest.json`'s fixed replay clock/news window for the scenario, while keeping any actual run time separate.
4. Stop clearly on a missing or malformed file. Never fall back to Alpha Vantage or turn a missing file into an empty feed.
5. Keep fixtures out of `.cache/` so they cannot be mistaken for successful live requests.
6. Load current rules/skills normally. Claude analysis, when connected, will still make paid API calls; this dataset does not include cached or mocked Claude responses.

## Deliberate expected behaviors

The current Python preparation should remove the FEIM holdings item and its duplicate earnings row, leaving two FEIM rows and two TNON rows for triage. The TNON reports have distinct titles/URLs: choosing one representative per event remains a triage task.

There is no required Claude shortlist or score. Check claims against the supplied mock evidence rather than forcing 7/10 or a particular number of displayed stories. Successful tests cannot establish that prompts eliminate hallucinations.

The scenario is fixed at replay time **2026-09-12T04:39:47+00:00**, using the logged market snapshot **2026-09-11 16:15:57 US/Eastern**. Do not rewrite the dates to make this look fresh.

## Security and provenance

This package contains no API keys and no `.env`. Mock URLs use `example.invalid` and are identifiers, not article sources to fetch. No provider sentiment or relevance scores are fabricated. Keep the `_fixture` metadata, title markers, source labels, and summary warnings when handling these files.
