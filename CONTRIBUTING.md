# CONTRIBUTING

Contributions to Pandora are welcome! Since this is a privacy-focused project, all code changes must be reviewed carefully.

## Setup

1. Fork the repository
2. `python -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`

## Scrapers

To write a new scraper for automatic categorization, add a module to `pandora/backend/scrapers/`.

## Testing

Run tests using `pytest`:

```bash
pytest
```
