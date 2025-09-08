# LinkedIn Alumni Scraper
A Python-based web scraping tool designed to enrich alumni data by finding and extracting LinkedIn profile information. Automates the process of searching for LinkedIn profiles using Google search and extracting professional information from those profiles.

## Features
- **Automated LinkedIn Profile Discovery**: Uses Google search to find LinkedIn profiles for alumni
- **Profile Data Extraction**: Extracts company, job title, and professional descriptions
- **Batch Processing**: Processes Excel files containing alumni data
- **Incremental Saving**: Saves results progressively to prevent data loss
- **Future Multiprocessing Support**: Parallel processing for faster execution
- **Flexible Input**: Supports Excel files with various column structures

## Prerequisites
- Python 3.7 or higher
- Google Chrome browser
- LinkedIn account (for authentication)
- Excel file with alumni data containing at least:
  - `first_name`
  - `last_name`
  - `Email` (optional)
  - `company` (optional)
  - `location` (optional)

## Installation
1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd alumni_scraper
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Project Structure
```
alumni_scraper/
├── data/                                    # Input data directory
│   ├── Test-Upload-9-3.xlsx                # Sample input file
│   └── TRALIBLAIZE Sigma Chi MS Alumni Directory, 12-7-23.xlsx      # Full alumni directory (Sigma XI)
├── linkedin_profile_scraper.py              # Core profile scraping logic
├── linkedin_enricher.py                     # Single-process enrichment tool
├── linkedin_enricher_multiprocess.py        # Multi-process enrichment tool
├── linkedin_profiles_incremental_*.csv      # Output files
├── requirements.txt                         # Python dependencies
└── README.md                               # This file
```

## Quick Start
### Option 1: Single Process (Recommended for beginners)
1. **Prepare your data file**
   - Place your Excel file in the `data/` directory
   - Ensure it has columns: `first_name`, `last_name`, `Email`, `company`, `location`

2. **Update the file path**
   - Edit `linkedin_enricher.py` line 449:
   ```python
   input_file = r"path\to\your\alumni_data.xlsx"
   ```

3. **Run the scraper**
   ```bash
   python linkedin_enricher.py
   ```

4. **Follow the prompts**
   - The script will open a Chrome browser
   - Login to LinkedIn when prompted
   - Press Enter to continue after login

### Option 2: Multi-Process (For large datasets)
1. **Prepare your data file** (same as above)

2. **Update the file path**
   - Edit `linkedin_enricher_multiprocess.py` line 326:
   ```python
   input_file = r"path\to\your\alumni_data.xlsx"
   ```

3. **Run the multiprocess scraper**
   ```bash
   python linkedin_enricher_multiprocess.py
   ```

## Output
The tool generates CSV files with the following columns:

| Column | Description |
|--------|-------------|
| `Email` | Original email from input |
| `first_name` | First name |
| `last_name` | Last name |
| `company` | Original company from input |
| `location` | Original location from input |
| `linkedin_url` | Found LinkedIn profile URL |
| `additional_linkedin_urls` | Additional LinkedIn URLs found |
| `current_title` | Current job title from LinkedIn |
| `current_company` | Current company from LinkedIn |
| `description` | Professional description/headline |
| `last_enriched_at` | Timestamp of data extraction |

## Performance
### Typical Performance
- **Single Process**: ~2-3 profiles per minute
- **Multi-Process**: ~8-12 profiles per minute (4 workers)
- **Success Rate**: 60-80% (depends on data quality)

### Optimization Tips
- Use multiprocess for datasets >100 records
- Ensure good internet connection
- Close other browser tabs to free memory
- Use SSD storage for better I/O performance

## Security Considerations
- Uses stealth mode to avoid detection
- Implements proper error handling
- No sensitive data logging
- Respects robots.txt and rate limits
- Uses secure browser configurations

## Testing
### Test Single Profile
To test the scraper on a single LinkedIn profile:

1. Edit `linkedin_profile_scraper.py` line 348:
   ```python
   test_url = "https://www.linkedin.com/in/your-test-profile"
   ```

2. Run the test:
   ```bash
   python linkedin_profile_scraper.py
   ```

## Important Notes
### LinkedIn Authentication
- You must be logged into LinkedIn in the browser window
- The tool will prompt you to login if not authenticated
- Use your personal LinkedIn account (avoid business accounts with restrictions)

### Rate Limiting & Ethics
- The tool includes delays to respect LinkedIn's servers
- Don't run multiple instances simultaneously
- Use responsibly and in compliance with LinkedIn's Terms of Service
- Consider LinkedIn's rate limits for large datasets

### Data Privacy
- Only extracts publicly available information
- Respects LinkedIn's privacy settings
- No personal data is stored beyond what's publicly visible

## Troubleshooting

### Common Issues
1. **Chrome Driver Issues**
   ```bash
   # Update Chrome browser
   # The tool auto-downloads compatible ChromeDriver
   ```

2. **LinkedIn Login Issues**
   - Clear browser cache
   - Try incognito mode
   - Check if LinkedIn account has restrictions

3. **No Profiles Found**
   - Verify input data quality
   - Check if names are spelled correctly
   - Try with more specific search terms

4. **Memory Issues (Large Files)**
   - Use multiprocess version
   - Process in smaller batches
   - Increase system RAM

### Error Logs

The tool provides detailed logging:
- Check console output for error messages
- Logs include timestamps and detailed error information
- Failed records are skipped and processing continues

## Dependencies

- `pandas`: Data manipulation and Excel/CSV handling
- `selenium`: Web browser automation
- `beautifulsoup4`: HTML parsing
- `requests`: HTTP requests
- `webdriver-manager`: Automatic ChromeDriver management
- `openpyxl`: Excel file reading
- `python-dotenv`: Environment variable management
