# Development replay update

## Install

Copy these TWO files into `C:\Users\Pavan\market-agent`:

- `market_agent_test.py`: replace the existing script.
- `dev_data_source.py`: add the new local-fixture reader beside it.

Keep `alpha_vantage_cache.py`, `.env`, `.gitignore`, `AGENT_RULES.md`, all skill files,
and the previously installed `test_data/` folder unchanged. No new packages or API
keys are needed. The optional `tests/test_dev_mode.py` may be added to `tests/`.
The ZIP does not contain replacement prompts, secrets, cached responses, or data.

## Run this command for development

```powershell
python market_agent_test.py --dev
```

In this mode:

- Alpha Vantage is not instantiated or contacted. No Alpha Vantage key is required.
- The existing Anthropic key is still used. Claude requests consume tokens.
- Data comes only from the files mapped in `test_data/manifest.json`.
- The news window and replay clock come from the manifest, not the current date.
- The actual execution time is displayed separately from the fixed replay time.
- All mapped fixture files are validated before making any paid Claude calls.
- Missing, corrupt, mislabeled, or inconsistent fixtures cause an explicit error.
- There is no fallback to live data and no live-cache read or write.
- Mock data labels remain in the evidence and displayed output. No article URL is
  fetched; the fixture URLs are non-live placeholders.
- Ticker discovery, catalyst triage, and news analysis use your existing skill
  files and output schemas. Numeric scores and ticker choices are NOT hard-coded.
- The existing display threshold stays at 6/10.

This is a simulation of the research workflow, not live financial research.
The market snapshot was reconstructed from prior console output, and the article
summaries are synthetic. Neither is independently verified here. A successful
replay does not prove factual accuracy or eliminate hallucinations.

The mock feeds contain articles for FEIM and TNON only. Selection and scores can
vary. Choosing other supplied tickers may correctly lead to empty fixture feeds.
Do not treat an empty feed as proof there was no real-world news.

## Live mode is preserved

Running the script without `--dev` retains the normal Alpha Vantage/cache path.
`--refresh-data` still forces that live path to bypass cached responses. Do not
use it to troubleshoot a provider quota. Combining `--dev` and `--refresh-data`
is rejected before running the pipeline.

No Git commit or push is performed by these files. After reviewing and testing
locally, you can commit the update through your existing Git workflow.

## Optional offline code tests

Copy `tests/test_dev_mode.py` into the existing `tests/` directory, then run:

```powershell
python -m unittest discover -s tests -p "test_dev_mode.py" -v
```

These tests require your existing installed dependencies, fixtures, and prompts.
They replace the API client with canned responses, block requests from the main
HTTP client paths, and do not load your `.env`. No API allowance is consumed.
They do not evaluate the model's judgment or verify the news in the fixtures.

### Checks performed for this update

36 offline tests passed: fixture parsing/provenance/time windows, file errors,
query validation, no-Alpha-key replay, mocked full-pipeline execution, invented
ID rejection, response validation failures, zero-shortlist cases, live-provider
routing, and command-line flag handling. Python syntax checks also passed.

The test environment did not have the Anthropic SDK installed, so a minimal
import-only SDK stand-in was used alongside mocked Claude responses. The
stand-in is NOT included in this update. SDK/network integration, actual Claude
analysis, your account, and execution on Windows have not been tested here.
The Anthropic calls themselves use the same SDK interface as your existing
working script.
