# PostPulse

Free GitHub Pages dashboard for measuring public social-posting volume against a historical baseline.

## Current source

Donald Trump's Truth Social account is collected through the public RSS feed maintained by Trump's Truth. The feed supports date filters and up to 500 items per request.

## Setup

1. Create a **public** GitHub repository.
2. Upload all files from this folder.
3. Go to Settings → Pages → Source: **GitHub Actions**.
4. Run Actions → Update PostPulse data → Run workflow.
5. Open the Pages URL GitHub gives you.

The workflow also runs automatically every 30 minutes.

## Important limitation

The public feed returns a finite recent window, so the repository builds its own history over time. It cannot magically recover older history that the feed no longer returns. Run the collector regularly to build a durable local dataset.

## Account expansion

Edit `data/accounts.json` to add accounts. The current collector is intentionally focused on Trump's Truth Social feed; additional source adapters can be added later for other public X/Truth sources.

## Cost

The site is static and hosted by GitHub Pages. The scheduled collector runs on GitHub Actions. GitHub documents Pages availability on GitHub Free for public repositories and free standard runners for public repositories.
