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
    
    def search_linkedin_profile(self, first_name: str, last_name: str, company: str = "", location: str = "") -> Optional[str]:
        """
        Search for LinkedIn profile using Google search
        Returns LinkedIn profile URL if found
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
            
            # Try multiple selectors for search results
            selectors_to_try = [
                "div.g",
                "div[data-ved]",
                "div.yuRUbf",
                "a[href*='linkedin.com/in/']"
            ]
            
            links = []
            for selector in selectors_to_try:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        logger.info(f"Found elements with selector: {selector}")
                        break
                except:
                    continue
            
            # Look specifically for LinkedIn links
            linkedin_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='linkedin.com/in/']")
            
            if linkedin_links:
                linkedin_url = linkedin_links[0].get_attribute('href')
                # Clean up the URL (remove Google redirect)
                if 'url?q=' in linkedin_url:
                    linkedin_url = linkedin_url.split('url?q=')[1].split('&')[0]
                
                logger.info(f"Found LinkedIn profile: {linkedin_url}")
                
                # Click on the LinkedIn profile
                try:
                    linkedin_links[0].click()
                    logger.info(f"Clicked on LinkedIn profile: {linkedin_url}")
                    time.sleep(3)  # Wait for page to load
                    return linkedin_url
                except Exception as e:
                    logger.warning(f"Could not click LinkedIn link: {e}")
                    return linkedin_url
            else:
                logger.info(f"No LinkedIn links found in search results for {first_name} {last_name}")
                
        except Exception as e:
            logger.error(f"Error searching for {first_name} {last_name}: {e}")
            
        return None
    
    def extract_profile_data(self, linkedin_url: str) -> Dict[str, str]:
        """
        Extract data from LinkedIn public profile
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(linkedin_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract data from various sources
            profile_data = {
                'linkedin_url': linkedin_url,
                'headline': '',
                'current_title': '',
                'current_company': '',
                'location_linkedin': '',
                'industry_linkedin': '',
                'education': '',
                'last_enriched_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Try to extract headline from title tag
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text()
                if '|' in title_text:
                    profile_data['headline'] = title_text.split('|')[0].strip()
            
            # Try to extract from meta tags
            meta_description = soup.find('meta', {'name': 'description'})
            if meta_description:
                description = meta_description.get('content', '')
                profile_data['headline'] = description[:200]  # Limit length
            
            # Try to extract from JSON-LD structured data
            json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})
            for script in json_ld_scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if 'jobTitle' in data:
                            profile_data['current_title'] = data['jobTitle']
                        if 'worksFor' in data:
                            profile_data['current_company'] = data['worksFor']
                        if 'address' in data:
                            profile_data['location_linkedin'] = data['address']
                except:
                    continue
            
            logger.info(f"Extracted profile data for {linkedin_url}")
            return profile_data
            
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
                'last_enriched_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
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
                'location_linkedin', 'industry_linkedin', 'education', 'last_enriched_at'
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
                    
                    # Search for LinkedIn profile
                    linkedin_url = self.search_linkedin_profile(first_name, last_name, company, location)
                    
                    if linkedin_url:
                        # Extract profile data
                        profile_data = self.extract_profile_data(linkedin_url)
                        
                        # Update dataframe
                        for key, value in profile_data.items():
                            if key in df.columns:
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
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        enricher.close()

if __name__ == "__main__":
    main()