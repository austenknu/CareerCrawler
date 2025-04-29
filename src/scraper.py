import logging
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from .config_loader import get_config
from .database import add_job, get_all_job_urls

log = logging.getLogger(__name__)

# --- Helper Functions ---

def fetch_page(url: str, user_agent: str, max_retries: int, delay: float) -> Optional[str]:
    """Fetches HTML content for a given URL with retries and delay."""
    headers = {'User-Agent': user_agent}
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=30) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            log.debug(f"Successfully fetched {url} (Status: {response.status_code})")
            time.sleep(delay) # Respect delay even on success
            return response.text
        except requests.exceptions.HTTPError as e:
            log.warning(f"HTTP Error fetching {url}: {e} (Attempt {retries + 1}/{max_retries})")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"Connection Error fetching {url}: {e} (Attempt {retries + 1}/{max_retries})")
        except requests.exceptions.Timeout as e:
            log.warning(f"Timeout Error fetching {url}: {e} (Attempt {retries + 1}/{max_retries})")
        except requests.exceptions.RequestException as e:
            log.warning(f"Error fetching {url}: {e} (Attempt {retries + 1}/{max_retries})")

        retries += 1
        if retries < max_retries:
            log.info(f"Retrying in {delay * (retries + 1)} seconds...")
            time.sleep(delay * (retries + 1)) # Exponential backoff (simple)

    log.error(f"Failed to fetch {url} after {max_retries} retries.")
    return None

def parse_jobs(html_content: str, base_url: str) -> List[Dict[str, Any]]:
    """Parses the HTML to find job listings.

    !! VERY BASIC PLACEHOLDER !!
    This function needs to be adapted for each specific website's structure.
    It currently tries to find all links and assumes they *might* be jobs.
    Real implementation requires inspecting each site and using specific selectors.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    potential_jobs = []

    # --- !!! --- Placeholder Logic --- !!! ---
    # Find all links. A real implementation would use more specific selectors
    # based on the target website's structure (e.g., find divs with class 'job-listing').
    links = soup.find_all('a', href=True)

    log.warning(f"Using basic link extraction for {base_url}. Found {len(links)} links. Site-specific parsing implementation is highly recommended.")

    for link in links:
        job = {
            "title": link.get_text(strip=True) or "(No Title Text)",
            "url": urljoin(base_url, link['href']), # Make URL absolute
            "location": "(Location Unknown)", # Placeholder
            "description": "(Description Unavailable)", # Placeholder
            "posted_date": None # Placeholder
        }
        # Basic check: avoid simple '#' links or javascript calls
        if job['url'] and not job['url'].startswith('#') and not job['url'].startswith('javascript:'):
             # Very basic filter: crude check if title or url contains common job keywords
            if any(kw in job['title'].lower() for kw in ['job', 'career', 'openings', 'position']) or \
               any(kw in job['url'].lower() for kw in ['job', 'career', 'posting', 'requisition']):
                potential_jobs.append(job)
                log.debug(f"Potential job found (basic check): {job['title']} - {job['url']}")
            else:
                 log.debug(f"Skipping link (basic check): {job['title']} - {job['url']}")
    # --- !!! --- End Placeholder Logic --- !!! ---

    if not potential_jobs and links:
        log.warning(f"No potential jobs identified using basic filters on {base_url}. Review parsing logic or site structure.")
    elif not links:
        log.warning(f"No links found at all on {base_url}. Page might be empty, require JS, or structure is unexpected.")


    return potential_jobs

def filter_job(job: Dict[str, Any], preferences: Dict[str, Any]) -> bool:
    """Checks if a job matches user preferences.

    Handles titles, exclusions. Basic location/seniority/dept requires better parsing.
    Time frame filtering relies on database check (new URL) for now.
    """
    title = job.get('title', '').lower()
    description = job.get('description', '').lower()
    location = job.get('location', '').lower()
    full_text = title + " " + description # Combine for exclusion check

    # 1. Exclusions (Keywords)
    exclusions = [e.lower() for e in preferences.get('exclusions', [])]
    if any(excl in full_text for excl in exclusions):
        log.debug(f"Filtering out job by exclusion keyword: {job['title']}")
        return False

    # 2. Titles (Keywords)
    pref_titles = [t.lower() for t in preferences.get('titles', [])]
    if not pref_titles:
        log.warning("No preferred titles specified in config. Cannot filter by title.")
        # Maybe allow all if no titles specified? Or block all? Let's allow.
    elif not any(pt in title for pt in pref_titles):
        log.debug(f"Filtering out job by title keyword: {job['title']}")
        return False

    # 3. Location (Basic - requires better parsing)
    pref_location = preferences.get('location', ["any"])
    if pref_location != ["any"]:
        include_locations = [loc.lower() for loc in pref_location if not loc.startswith('exclude:')]
        exclude_locations = [loc.lower().replace('exclude:', '').strip() for loc in pref_location if loc.startswith('exclude:')]

        # Exclusion check
        if any(excl_loc in location for excl_loc in exclude_locations):
             log.debug(f"Filtering out job by excluded location '{location}': {job['title']}")
             return False
        # Inclusion check (if includes are specified)
        if include_locations and not any(inc_loc in location for inc_loc in include_locations):
             log.debug(f"Filtering out job - location '{location}' not in preferred list: {job['title']}")
             return False
        log.debug(f"Job location '{location}' passed filters: {job['title']}")

    # --- Placeholder Filters (Require better parsing) ---
    # 4. Seniority
    pref_seniority = [s.lower() for s in preferences.get('seniority', ["any"])]
    if pref_seniority != ["any"] and not any(s in title for s in pref_seniority):
        # This is a very weak check, relying on seniority in the title
        log.debug(f"Filtering out job by seniority (basic title check): {job['title']}")
        return False

    # 5. Department
    pref_department = [d.lower() for d in preferences.get('department', ["any"])]
    if pref_department != ["any"]:
        # Requires dedicated parsing or smarter text analysis
        log.debug(f"Department filtering not implemented reliably yet. Skipping check for: {job['title']}")
        pass # Cannot reliably filter yet

    # 6. Time Frame (Handled by checking if URL is new in the DB)
    # More complex date parsing/filtering could be added here if dates are scraped.

    log.debug(f"Job passed filters: {job['title']}")
    return True


# --- Main Scraper Function ---

def run_scraper():
    """Main function to run the scraping process for all configured companies."""
    log.info("Starting scraper run...")
    config = get_config()
    if not config:
        log.error("Configuration not loaded. Aborting scrape.")
        return

    scrape_config = config.get('scraping', {})
    companies = scrape_config.get('companies', [])
    user_agent = scrape_config.get('user_agent', 'Mozilla/5.0 (compatible; CareerCrawler/1.0; +https://github.com/AnonArchitect/JobScraperAgent)')
    delay = float(scrape_config.get('request_delay_seconds', 3))
    max_retries = int(scrape_config.get('max_retries', 3))

    preferences = config.get('preferences', {})

    if not companies:
        log.warning("No companies configured in config.yaml. Nothing to scrape.")
        return

    log.info(f"Found {len(companies)} companies to scrape.")
    existing_urls = set(get_all_job_urls()) # Load existing URLs once
    log.info(f"Loaded {len(existing_urls)} existing job URLs from database.")
    total_new_jobs_added = 0

    for company in companies:
        company_name = company.get('name')
        company_url = company.get('url')

        if not company_name or not company_url:
            log.warning(f"Skipping invalid company entry in config: {company}")
            continue

        log.info(f"--- Scraping company: {company_name} ({company_url}) ---")

        html_content = fetch_page(company_url, user_agent, max_retries, delay)

        if not html_content:
            log.error(f"Could not fetch page for {company_name}. Skipping.")
            continue

        try:
            potential_jobs = parse_jobs(html_content, company_url)
        except Exception as e:
            log.error(f"Error parsing jobs for {company_name}: {e}", exc_info=True)
            continue # Skip company on parsing error

        log.info(f"Parsed {len(potential_jobs)} potential jobs from {company_name} (using basic parser). Filtering...")
        new_jobs_for_company = 0
        for job_data in potential_jobs:
            # Add company name to the job data
            job_data['company'] = company_name

            # Check if URL already exists before deeper filtering
            if job_data['url'] in existing_urls:
                log.debug(f"Skipping already existing job URL: {job_data['url']}")
                continue

            if filter_job(job_data, preferences):
                log.info(f"Found matching job: {job_data['title']} at {company_name}")
                # Prepare data for DB (ensure keys match model)
                db_data = {
                    'company': job_data['company'],
                    'title': job_data['title'],
                    'url': job_data['url'],
                    'location': job_data.get('location'),
                    'description': job_data.get('description'),
                    'posted_date': job_data.get('posted_date'), # Will be None for now
                }
                added_job = add_job(db_data)
                if added_job:
                    new_jobs_for_company += 1
                    existing_urls.add(added_job.url) # Add to known URLs immediately
            # else: Job was filtered out, debug log is inside filter_job

        log.info(f"Added {new_jobs_for_company} new jobs for {company_name}.")
        total_new_jobs_added += new_jobs_for_company

    log.info(f"--- Scraper run finished. Added {total_new_jobs_added} total new jobs. ---") 