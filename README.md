# Career Crawler Framework

This project provides a framework for scraping job postings from company career pages,
filtering them based on user preferences, and delivering alerts via Discord and a
local web dashboard.

## Features

-   Configurable list of companies and career page URLs.
-   Customizable job filtering based on titles, seniority, department, location, and exclusions.
-   Choice between SQLite (recommended) or TXT file for data storage.
-   Discord bot for real-time notifications.
-   Local web dashboard (Flask-based) to view and manage jobs.
-   Scheduled daily scraping.
-   Basic error handling and logging.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AnonArchitect/JobScraperAgent.git
    cd JobScraperAgent
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the scraper:**
    -   Rename `config.yaml.template` to `config.yaml`.
    -   Edit `config.yaml` with your specific details (Discord token, companies, preferences, etc.). See the comments within the file for guidance.

## Usage

1.  **Run the scraper and send notifications:**
    ```bash
    python src/main.py scrape
    ```
    If new matching jobs are found and Discord is enabled in `config.yaml`,
    notifications will be sent to the specified channel after scraping finishes.
    *(Note: Scheduler setup will be added later)*

2.  **Run the web dashboard:**
    ```bash
    python src/main.py dashboard
    ```
    Access the dashboard at `http://localhost:5000` (or the configured port).

3.  **Run the scraper automatically on schedule:**
    ```bash
    python src/main.py schedule
    ```
    This command will keep running in the foreground. It will execute the scrape
    and notification process daily at the time specified in `config.yaml`.
    Press Ctrl+C to stop the scheduler.

## Configuration (`config.yaml`)

See `config.yaml.template` for all available options and descriptions. Key sections include:

-   `scraping`: Schedule, companies, user agent, request delays.
-   `preferences`: Job titles, seniority, department, location, exclusions, time frame.
-   `storage`: Database type (sqlite/txt) and file path.
-   `discord`: Bot token and channel ID.
-   `dashboard`: Host and port.
-   `logging`: Log file path and level.

## Contributing

Contributions are welcome! Please follow standard Fork and Pull Request workflows.

## License

[MIT] 
