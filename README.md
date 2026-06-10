# webcrawlers

#indeed_scraper:
  Python tool that extracts job listings from Indeed Canada for any search query and location. The interesting part is that I didn't scrape HTML — I discovered that Indeed embeds all job card data as a structured JSON object inside the page source, the same data their React frontend uses to render the page. I extract that JSON directly using a regex, which gives me clean structured data including job title, company, location, salary, and posting date — all fields that wouldn't be available through HTML parsing alone. The tool filters results to only jobs where the title actually contains the search keyword, paginate through all results, and exports everything to a formatted Excel file.

#redfin_scraper:
  Python tool that extracts real estate listing data from Redfin for any US city. Instead of scraping HTML, I reverse-engineered Redfin's internal JSON API — the same one their own website uses — to get fully structured data directly. The tool paginates through all results, extracts 36 fields per listing including price, beds, baths, sqft, coordinates, agent info, and property description, and exports everything to a formatted Excel file. I also built a FastAPI service on top of it that accepts a city, state, and filters like min beds, max price, or year built, and returns matching listings as structured JSON. I ran this for Austin, TX and filtered to only properties built after 2020.

#fl_dental_scraper:
  Web scraping tool in Python that extracts all dental provider license data from Florida's Department of Health public database. The tool uses Playwright to automate a real browser, navigates through 1,400+ paginated result pages, collects 29,500+ provider records, and exports them to a formatted Excel file. I also built a FastAPI REST service on top of it that accepts a license number and returns structured provider data in JSON — useful when you need to verify a single provider on demand.

#books_scraper:
  Full-stack web scraper for books.toscrape.com — a sandbox site with ~1,000 books across 50 pages.
The scraper uses `requests` and `BeautifulSoup` to paginate through all pages, extracting title, price, star
rating, and availability from each book card. I wrapped it in a FastAPI service that accepts search filters —
title substring, minimum rating, max price, availability — and returns structured JSON. The CLI can also export
results directly to a styled Excel file. I wrote 41 tests covering the API layer, input validation, filter
passthrough, error handling, and direct unit tests for the HTML parser with all its edge cases.
