import pandas as pd
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote_plus
import logging
from typing import Dict, Optional
import os
from linkedin_profile_scraper import LinkedInProfileScraper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInEnricher:
    def __init__(self):
        # Setup Chrome driver with stealth options
        self.driver = self._setup_driver()
        
        # Ensure LinkedIn login
        self.ensure_linkedin_login()
    
    def _setup_driver(self):
        """Setup Chrome driver with stealth options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def ensure_linkedin_login(self) -> bool:
        """
        Ensure user is logged into LinkedIn, prompt if needed
        Returns True if logged in
        """
        try:
            # Go to LinkedIn to check login status
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)  # Increased wait time
            
            # Multiple ways to check if we're logged in
            login_indicators = [
                # Check for feed elements
                "[data-test-id='main-feed']",
                # Check for navigation elements
                "[data-test-id='global-nav']",
                # Check for search bar (indicates logged in)
                "input[placeholder*='Search']",
                # Check for profile elements
                "[data-test-id='profile-nav-item']",
                # Check for messaging elements
                "[data-test-id='messaging-nav-item']"
            ]
            
            for indicator in login_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements:
                        logger.info("Successfully logged into LinkedIn!")
                        return True
                except:
                    continue
            
            # Check if we're on login page or authwall
            current_url = self.driver.current_url.lower()
            if ("login" in current_url or 
                "signin" in current_url or
                "authwall" in current_url):
                
                print("\n" + "="*60)
                print("🔐 LINKEDIN LOGIN REQUIRED")
                print("="*60)
                print("Please login to LinkedIn in the browser window that opened.")
                print("After logging in, press ENTER to continue...")
                print("="*60)
                
                input("Press ENTER when you've completed the login...")
                
                # Refresh and check again
                self.driver.refresh()
                time.sleep(5)
                
                # Re-check login status
                for indicator in login_indicators:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                        if elements:
                            logger.info("LinkedIn login successful!")
                            return True
                    except:
                        continue
                
                logger.warning("Login verification failed")
                return False
            else:
                logger.info("LinkedIn login status unclear, continuing...")
                return True
                
        except Exception as e:
            logger.error(f"Error checking LinkedIn login: {e}")
            return False
    
    def search_linkedin_profile(self, first_name: str, last_name: str, company: str = "", location: str = "") -> tuple:
        """
        Search for LinkedIn profile using Google search
        Returns tuple: (primary_url, additional_urls_list)
        """
        try:
            # Construct search query
            search_terms = [first_name, last_name]
            if company and company != "Not Specified" and company and company != "nan":
                search_terms.append(company)
            if location and location != "Not Specified" and location and location != "nan":
                search_terms.append(location)
            
            query = f'site:linkedin.com/in {" ".join(search_terms)}'
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            
            logger.info(f"Searching for: {first_name} {last_name}")
            logger.info(f"Search URL: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(5)  # Increased wait time
            
            # Look specifically for LinkedIn links
            linkedin_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='linkedin.com/in/']")
            
            if linkedin_links:
                # Clean up URLs (remove Google redirect)
                clean_urls = []
                for link in linkedin_links:
                    url = link.get_attribute('href')
                    if 'url?q=' in url:
                        url = url.split('url?q=')[1].split('&')[0]
                    clean_urls.append(url)
                
                # Remove duplicates while preserving order
                unique_urls = []
                seen = set()
                for url in clean_urls:
                    if url not in seen:
                        unique_urls.append(url)
                        seen.add(url)
                
                primary_url = unique_urls[0]
                additional_urls = unique_urls[1:5]  # Get next 3-4 URLs (max 4 additional)
                
                logger.info(f"Found LinkedIn profile: {primary_url}")
                if additional_urls:
                    logger.info(f"Found {len(additional_urls)} additional LinkedIn URLs")
                
                # Click on the first LinkedIn profile
                try:
                    linkedin_links[0].click()
                    logger.info(f"Clicked on LinkedIn profile: {primary_url}")
                    time.sleep(3)  # Wait for page to load
                    
                    # Check if we're on LinkedIn login page
                    current_url = self.driver.current_url
                    if "linkedin.com/authwall" in current_url or "linkedin.com/login" in current_url:
                        logger.info("Not on LinkedIn login page. Current URL: " + current_url)
                    else:
                        logger.info("Successfully navigated to LinkedIn profile")
                    
                    return primary_url, additional_urls
                except Exception as e:
                    logger.warning(f"Could not click LinkedIn link: {e}")
                    return primary_url, additional_urls
            else:
                logger.info(f"No LinkedIn links found in search results for {first_name} {last_name}")
                
        except Exception as e:
            logger.error(f"Error searching for {first_name} {last_name}: {e}")
            
        return None, []
    
    def extract_profile_data(self, linkedin_url: str) -> Dict[str, str]:
        """
        Extract data from LinkedIn public profile using the new scraper
        """
        try:
            # Initialize the scraper with our driver
            scraper = LinkedInProfileScraper(self.driver)
            
            # Extract profile info
            profile_data = scraper.extract_profile_info(linkedin_url)
            
            # Map to the expected format
            return {
                'linkedin_url': profile_data['linkedin_url'],
                'headline': profile_data['description'][:200] if profile_data['description'] else '',  # Truncate for headline
                'current_title': profile_data['job_title'],
                'current_company': profile_data['company'],
                'location_linkedin': '',  # We can add this later
                'industry_linkedin': '',   # We can add this later
                'education': '',          # We can add this later
                'last_enriched_at': profile_data['scraped_at'],
                'description': profile_data['description']  # Add the full description
            }
            
        except Exception as e:
            logger.error(f"Error extracting profile data from {linkedin_url}: {e}")
            return {
                'linkedin_url': linkedin_url,
                'headline': '',
                'current_title': '',
                'current_company': '',
                'location_linkedin': '',
                'industry_linkedin': '',
                'education': '',
                'last_enriched_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                'description': ''
            }
    
    def process_excel_file(self, file_path: str, max_records: int = None) -> pd.DataFrame:
        """
        Process Excel file and search for LinkedIn profiles
        Returns dataframe with search results (no file saving)
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Excel file not found: {file_path}")
            
            # Read Excel file
            df = pd.read_excel(file_path)
            logger.info(f"Loaded {len(df)} records from {file_path}")
            
            # Show column structure
            logger.info(f"Columns found: {list(df.columns)}")
            
            # Limit records for testing if specified
            if max_records:
                df = df.head(max_records)
                logger.info(f"Limited to first {max_records} records for testing")
            
            # Initialize enrichment columns
            enrichment_columns = [
                'linkedin_url', 'headline', 'current_title', 'current_company',
                'location_linkedin', 'industry_linkedin', 'education', 'last_enriched_at',
                'additional_linkedin_urls', 'description'  # Add description column
            ]
            
            for col in enrichment_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Process each record
            for index, row in df.iterrows():
                try:
                    first_name = str(row.get('first_name', '')).strip()
                    last_name = str(row.get('last_name', '')).strip()
                    company = str(row.get('company', '')).strip()
                    location = str(row.get('location', '')).strip()
                    
                    if not first_name or not last_name or first_name == 'nan' or last_name == 'nan':
                        logger.warning(f"Skipping row {index}: missing name data")
                        continue
                    
                    logger.info(f"Processing {index + 1}/{len(df)}: {first_name} {last_name}")
                    
                    # Search for LinkedIn profile (now returns tuple)
                    primary_url, additional_urls = self.search_linkedin_profile(first_name, last_name, company, location)
                    
                    if primary_url:
                        # Extract profile data from primary URL
                        profile_data = self.extract_profile_data(primary_url)
                        
                        # Update dataframe with primary URL and additional URLs
                        df.at[index, 'linkedin_url'] = primary_url
                        df.at[index, 'additional_linkedin_urls'] = '; '.join(additional_urls) if additional_urls else ''
                        
                        # Update other profile data
                        for key, value in profile_data.items():
                            if key in df.columns and key != 'linkedin_url':
                                df.at[index, key] = value
                        
                        logger.info(f"Successfully enriched {first_name} {last_name}")
                    else:
                        logger.info(f"No LinkedIn profile found for {first_name} {last_name}")
                    
                    # Be respectful with delays
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing row {index}: {e}")
                    continue
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            raise
    
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()

    def save_linkedin_urls_to_csv(self, df: pd.DataFrame, output_file: str = None) -> str:
        """
        Save LinkedIn URLs to a CSV file with email, linkedin_url, additional_urls, company, job_title, and description columns
        """
        try:
            # Create a dataframe with all the relevant columns
            csv_data = []
            
            for index, row in df.iterrows():
                email = str(row.get('Email', '')).strip()
                linkedin_url = str(row.get('linkedin_url', '')).strip()
                additional_urls = str(row.get('additional_linkedin_urls', '')).strip()
                company = str(row.get('current_company', '')).strip()
                job_title = str(row.get('current_title', '')).strip()
                description = str(row.get('description', '')).strip()
                
                # Only include rows where we found a LinkedIn URL
                if linkedin_url and linkedin_url != 'nan' and linkedin_url != '':
                    csv_data.append({
                        'email': email if email != 'nan' else '',
                        'linkedin_url': linkedin_url,
                        'additional_linkedin_urls': additional_urls if additional_urls != 'nan' else '',
                        'company': company if company != 'nan' else '',
                        'job_title': job_title if job_title != 'nan' else '',
                        'description': description if description != 'nan' else ''
                    })
            
            if not csv_data:
                logger.warning("No LinkedIn URLs found to save")
                return None
            
            # Create dataframe and save to CSV
            csv_df = pd.DataFrame(csv_data)
            
            # Generate output filename if not provided (save to current directory)
            if not output_file:
                timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
                output_file = f"linkedin_profiles_complete_{timestamp}.csv"
            
            # Save to CSV in current directory
            csv_df.to_csv(output_file, index=False)
            
            logger.info(f"Saved {len(csv_data)} complete LinkedIn profiles to {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error saving LinkedIn profiles to CSV: {e}")
            return None

def main():
    """Main function to run the enricher"""
    enricher = LinkedInEnricher()
    
    try:
        # Use the full file path
        input_file = r"C:\Users\dmaso\OneDrive\Documents\002 Projects\003 Web Development Agency\01_Clients\01_Greekrow_Trailblaze\03_Development\alumni_scraper\data\Test-Upload-9-3.xlsx"
        
        logger.info("Starting LinkedIn enrichment process...")
        
        # Process the file (limit to 5 records for initial testing)
        enriched_df = enricher.process_excel_file(input_file, max_records=5)
        
        logger.info("LinkedIn enrichment completed successfully!")
        
        # Show summary
        linkedin_found = enriched_df['linkedin_url'].notna().sum()
        print(f"\n=== ENRICHMENT SUMMARY ===")
        print(f"Total records processed: {len(enriched_df)}")
        print(f"LinkedIn profiles found: {linkedin_found}")
        print(f"Success rate: {(linkedin_found/len(enriched_df)*100):.1f}%")
        
        # Show results
        print(f"\n=== RESULTS ===")
        for index, row in enriched_df.iterrows():
            if row['linkedin_url']:
                print(f"{row['first_name']} {row['last_name']}: {row['linkedin_url']}")
        
        # Save LinkedIn URLs to CSV
        csv_file = enricher.save_linkedin_urls_to_csv(enriched_df)
        if csv_file:
            print(f"\n=== CSV FILE CREATED ===")
            print(f"LinkedIn URLs saved to: {csv_file}")
            print(f"File contains: email, linkedin_url, additional_linkedin_urls columns")
        else:
            print(f"\n=== NO CSV FILE CREATED ===")
            print("No LinkedIn URLs were found to save")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        enricher.close()

if __name__ == "__main__":
    main()