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
from typing import Dict, Optional, List
import os
import multiprocessing as mp
from multiprocessing import Pool, Manager
import queue
from linkedin_profile_scraper import LinkedInProfileScraper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInEnricherMultiprocess:
    def __init__(self, worker_id: int = 0):
        self.worker_id = worker_id
        self.driver = None
        
    def _setup_driver(self):
        """Setup Chrome driver with stealth options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Add unique user data directory for each worker
        chrome_options.add_argument(f"--user-data-dir=C:/temp/chrome_worker_{self.worker_id}")
        
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
            time.sleep(5)
            
            # Multiple ways to check if we're logged in
            login_indicators = [
                "[data-test-id='main-feed']",
                "[data-test-id='global-nav']",
                "input[placeholder*='Search']",
                "[data-test-id='profile-nav-item']",
                "[data-test-id='messaging-nav-item']"
            ]
            
            for indicator in login_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements:
                        logger.info(f"Worker {self.worker_id}: Successfully logged into LinkedIn!")
                        return True
                except:
                    continue
            
            # Check if we're on login page or authwall
            current_url = self.driver.current_url.lower()
            if ("login" in current_url or 
                "signin" in current_url or
                "authwall" in current_url):
                
                print(f"\n{'='*60}")
                print(f"🔐 LINKEDIN LOGIN REQUIRED - Worker {self.worker_id}")
                print(f"{'='*60}")
                print(f"Please login to LinkedIn in the browser window that opened.")
                print(f"After logging in, press ENTER to continue...")
                print(f"{'='*60}")
                
                input(f"Worker {self.worker_id} - Press ENTER when you've completed the login...")
                
                # Refresh and check again
                self.driver.refresh()
                time.sleep(5)
                
                # Re-check login status
                for indicator in login_indicators:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                        if elements:
                            logger.info(f"Worker {self.worker_id}: LinkedIn login successful!")
                            return True
                    except:
                        continue
                
                logger.warning(f"Worker {self.worker_id}: Login verification failed")
                return False
            else:
                logger.info(f"Worker {self.worker_id}: LinkedIn login status unclear, continuing...")
                return True
                
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error checking LinkedIn login: {e}")
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
            
            logger.info(f"Worker {self.worker_id}: Searching for: {first_name} {last_name}")
            
            self.driver.get(search_url)
            time.sleep(5)
            
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
                
                logger.info(f"Worker {self.worker_id}: Found LinkedIn profile: {primary_url}")
                if additional_urls:
                    logger.info(f"Worker {self.worker_id}: Found {len(additional_urls)} additional LinkedIn URLs")
                
                # Click on the first LinkedIn profile
                try:
                    linkedin_links[0].click()
                    logger.info(f"Worker {self.worker_id}: Clicked on LinkedIn profile: {primary_url}")
                    time.sleep(3)
                    
                    return primary_url, additional_urls
                except Exception as e:
                    logger.warning(f"Worker {self.worker_id}: Could not click LinkedIn link: {e}")
                    return primary_url, additional_urls
            else:
                logger.info(f"Worker {self.worker_id}: No LinkedIn links found for {first_name} {last_name}")
                
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error searching for {first_name} {last_name}: {e}")
            
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
                'headline': profile_data['description'][:200] if profile_data['description'] else '',
                'current_title': profile_data['job_title'],
                'current_company': profile_data['company'],
                'location_linkedin': '',
                'industry_linkedin': '',
                'education': '',
                'last_enriched_at': profile_data['scraped_at'],
                'description': profile_data['description']
            }
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error extracting profile data from {linkedin_url}: {e}")
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
    
    def process_batch(self, batch_data: List[Dict]) -> List[Dict]:
        """
        Process a batch of records
        """
        try:
            # Initialize driver
            self.driver = self._setup_driver()
            
            # Ensure LinkedIn login
            if not self.ensure_linkedin_login():
                logger.error(f"Worker {self.worker_id}: Failed to login to LinkedIn")
                return []
            
            results = []
            
            for i, record in enumerate(batch_data):
                try:
                    first_name = str(record.get('first_name', '')).strip()
                    last_name = str(record.get('last_name', '')).strip()
                    company = str(record.get('company', '')).strip()
                    location = str(record.get('location', '')).strip()
                    email = str(record.get('Email', '')).strip()
                    
                    if not first_name or not last_name or first_name == 'nan' or last_name == 'nan':
                        logger.warning(f"Worker {self.worker_id}: Skipping record {i}: missing name data")
                        continue
                    
                    logger.info(f"Worker {self.worker_id}: Processing {i+1}/{len(batch_data)}: {first_name} {last_name}")
                    
                    # Search for LinkedIn profile
                    primary_url, additional_urls = self.search_linkedin_profile(first_name, last_name, company, location)
                    
                    result = {
                        'Email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'company': company,
                        'location': location,
                        'linkedin_url': '',
                        'additional_linkedin_urls': '',
                        'current_title': '',
                        'current_company': '',
                        'description': '',
                        'last_enriched_at': ''
                    }
                    
                    if primary_url:
                        # Extract profile data
                        profile_data = self.extract_profile_data(primary_url)
                        
                        # Update result
                        result.update({
                            'linkedin_url': profile_data['linkedin_url'],
                            'additional_linkedin_urls': '; '.join(additional_urls) if additional_urls else '',
                            'current_title': profile_data['current_title'],
                            'current_company': profile_data['current_company'],
                            'description': profile_data['description'],
                            'last_enriched_at': profile_data['last_enriched_at']
                        })
                        
                        logger.info(f"Worker {self.worker_id}: Successfully enriched {first_name} {last_name}")
                    else:
                        logger.info(f"Worker {self.worker_id}: No LinkedIn profile found for {first_name} {last_name}")
                    
                    results.append(result)
                    
                    # Be respectful with delays
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Worker {self.worker_id}: Error processing record {i}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error processing batch: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

def worker_process(worker_id: int, batch_data: List[Dict]) -> List[Dict]:
    """
    Worker process function for multiprocessing
    """
    enricher = LinkedInEnricherMultiprocess(worker_id)
    return enricher.process_batch(batch_data)

def split_into_batches(data: List[Dict], batch_size: int = 100) -> List[List[Dict]]:
    """
    Split data into batches
    """
    batches = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        batches.append(batch)
    return batches

def main():
    """
    Main function to run the multiprocess enricher
    """
    try:
        # Use the full file path
        input_file = r"C:\Users\dmaso\OneDrive\Documents\002 Projects\003 Web Development Agency\01_Clients\01_Greekrow_Trailblaze\03_Development\alumni_scraper\data\Test-Upload-9-3.xlsx"
        
        logger.info("Starting LinkedIn enrichment process with multiprocessing...")
        
        # Read Excel file
        df = pd.read_excel(input_file)
        logger.info(f"Loaded {len(df)} records from {input_file}")
        
        # Convert to list of dictionaries
        data = df.to_dict('records')
        
        # Split into batches of 100
        batches = split_into_batches(data, batch_size=100)
        logger.info(f"Split into {len(batches)} batches of ~100 records each")
        
        # Process batches with 4 workers
        num_workers = 4
        all_results = []
        
        with Pool(processes=num_workers) as pool:
            # Create worker tasks
            worker_tasks = []
            for i, batch in enumerate(batches):
                worker_id = i % num_workers  # Distribute batches across workers
                worker_tasks.append((worker_id, batch))
            
            # Process batches in parallel
            logger.info(f"Starting {num_workers} workers to process {len(batches)} batches...")
            results = pool.starmap(worker_process, worker_tasks)
            
            # Flatten results
            for batch_results in results:
                all_results.extend(batch_results)
        
        # Create final dataframe
        final_df = pd.DataFrame(all_results)
        
        # Save results
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"linkedin_profiles_multiprocess_{timestamp}.csv"
        final_df.to_csv(output_file, index=False)
        
        logger.info("LinkedIn enrichment completed successfully!")
        
        # Show summary
        linkedin_found = final_df['linkedin_url'].notna().sum()
        print(f"\n=== ENRICHMENT SUMMARY ===")
        print(f"Total records processed: {len(final_df)}")
        print(f"LinkedIn profiles found: {linkedin_found}")
        print(f"Success rate: {(linkedin_found/len(final_df)*100):.1f}%")
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")

if __name__ == "__main__":
    main()
