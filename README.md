# ASX Stock Radar Pro — GitHub Pages edition

A free mobile-first ASX market screening website plus a scheduled Python scanner. **Not real-time, not an accurate-prediction guarantee, not connected to Plus500.**

## Publish from Android (GitHub website in Chrome)

1. Create a **public** GitHub repository named `asx-stock-radar` (GitHub Pages on free accounts requires public repos).
2. Upload **all files and folders** from this ZIP to the repository, preserving `.github/workflows/update.yml` and `data/` structure. On Android Chrome, enable **Desktop site** if GitHub's upload UI is difficult. ZIP files cannot be uploaded as-is and run automatically; extract them first.
3. Go to **Settings → Actions → General → Workflow permissions** and choose **Read and write permissions**, if the option is available. Save.
4. Go to **Actions → Update ASX market scan → Run workflow**. Allow several minutes. Confirm it finishes successfully and commits `data/stocks.json`.
5. Go to **Settings → Pages → Build and deployment**. Choose **Deploy from a branch**, branch `main`, folder `/ (root)`; Save.
6. After deployment, open `https://YOUR-USERNAME.github.io/asx-stock-radar/` on Android Chrome. Tap **⋮ → Add to Home screen** (or Install app if offered).

The schedule runs at **07:15 UTC Monday–Friday** (approximately 6:15 pm Sydney AEDT / 5:15 pm AEST). GitHub scheduled jobs may run late or be disabled after inactivity; free data can be delayed or rate-limited. Run the workflow manually if needed. It may take a few days to get a reliable ticker universe. The app explicitly shows the last update time and number scanned.

## Tickers and limits

The scanner tries to obtain ASX listed companies from a public ASX directory. If the source is blocked or unavailable it uses a fallback list of ~75 tickers. To control the universe, create `tickers.txt` with one ASX code per line (without `.AX`), commit it, and rerun the workflow. **500+ successful scans are not guaranteed**; delisted or illiquid shares may not have sufficient history, and free providers may throttle requests.

The long-term score is **technical momentum**, not business fundamentals. The short-term score uses end-of-day prices, so it **cannot reliably catch intraday spikes**. Scores are heuristics, not probabilities; they have not been backtested and are not personalized investment recommendations. No paid API keys or hosting are required for this starter.

## Run locally (optional)

```bash
pip install -r requirements.txt
python scanner.py
python -m http.server 8000
```

Open http://localhost:8000. Data will only appear after scanner succeeds. The site is static; the GitHub Actions workflow supplies refreshed JSON. Never put brokerage passwords or API secrets in public repositories.
