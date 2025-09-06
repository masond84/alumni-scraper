import pandas as pd
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, Optional, List
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInProfileScraper:
    def __init__(self, driver):
        """
        Initialize the scraper with an existing WebDriver instance
        """
        self.driver = driver
        
    def extract_profile_info(self, linkedin_url: str) -> Dict[str, str]:
        """
        Extract company, job_title, and description from a LinkedIn profile page
        """
        try:
            logger.info(f"Extracting profile info from: {linkedin_url}")
            
            # Navigate to the LinkedIn profile
            self.driver.get(linkedin_url)
            time.sleep(3)
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                logger.warning("Page load timeout, continuing anyway")
            
            profile_data = {
                'linkedin_url': linkedin_url,
                'company': '',
                'job_title': '',
                'description': '',
                'scraped_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Extract company and job title from the main profile section
            company, job_title = self._extract_company_and_title()
            profile_data['company'] = company
            profile_data['job_title'] = job_title
            
            # Extract description (About section or fallback)
            description = self._extract_description()
            profile_data['description'] = description
            
            logger.info(f"Successfully extracted profile info for {linkedin_url}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Error extracting profile info from {linkedin_url}: {e}")
            return {
                'linkedin_url': linkedin_url,
                'company': '',
                'job_title': '',
                'description': '',
                'scraped_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def _extract_description(self) -> str:
        """
        Extract description from the main profile title section (fallback only)
        """
        try:
            # Use the specific XPath you provided to get the main title section
            xpath_selectors = [
                "//*[@id='profile-content']/div/div[2]/div/div/main/section[1]/div[2]/div[2]/div[1]/div[2]",
                "//div[@class='text-body-medium break-words']",
                "//div[contains(@class, 'text-body-medium') and contains(@class, 'break-words')]"
            ]
            
            for xpath in xpath_selectors:
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    if element:
                        text = element.text.strip()
                        if text:
                            logger.info(f"Found main profile title: {text}")
                            return text
                except:
                    continue
            
            # Fallback: try CSS selectors
            fallback_selectors = [
                "div.text-body-medium.break-words[data-generated-suggestion-target*='profileActionDelegate']",
                "div.text-body-medium.break-words",
                ".pv-text-details__left-panel .text-body-medium",
                ".pv-top-card--list-bullet .text-body-medium"
            ]
            
            for selector in fallback_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 10:
                            logger.info(f"Found fallback profile title: {text}")
                            return text
                except:
                    continue
            
            logger.warning("No main profile title found")
            return ''
            
        except Exception as e:
            logger.error(f"Error extracting main profile title: {e}")
            return ''

    def _extract_about_section(self) -> str:
        """
        About section extraction removed - we only use main profile title now
        """
        return ''

    def _extract_current_job_from_experience(self) -> tuple:
        """
        Extract current company and job title from the Experience section
        Returns tuple: (company, job_title)
        """
        try:
            # Wait for page to load completely
            time.sleep(2)
            
            # Try to find the Experience section
            experience_selectors = [
                "#experience",
                "[data-test-id='experience-section']",
                ".pv-profile-section.experience",
                "section[aria-labelledby*='experience']"
            ]
            
            experience_section = None
            for selector in experience_selectors:
                try:
                    experience_section = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if experience_section:
                        logger.info(f"Found Experience section with selector: {selector}")
                        break
                except:
                    continue
            
            if not experience_section:
                logger.warning("Experience section not found")
                return '', ''
            
            # Look for individual experience entries
            experience_entries = experience_section.find_elements(By.CSS_SELECTOR, "li.artdeco-list__item")
            
            if not experience_entries:
                # Try alternative selectors for experience entries
                experience_entries = experience_section.find_elements(By.CSS_SELECTOR, ".pv-entity__position-group-pager")
                if not experience_entries:
                    experience_entries = experience_section.find_elements(By.CSS_SELECTOR, ".pv-entity__summary-info")
            
            logger.info(f"Found {len(experience_entries)} experience entries")
            
            # Process each experience entry to find the most recent one
            for i, entry in enumerate(experience_entries):
                try:
                    # Extract job title
                    job_title_selectors = [
                        ".pv-entity__summary-info h3",
                        ".pv-entity__summary-info .t-16.t-black.t-bold",
                        ".pv-entity__summary-info .t-14.t-black.t-bold",
                        ".pv-entity__summary-info-v2 h3",
                        ".pv-entity__summary-info-v2 .t-16.t-black.t-bold"
                    ]
                    
                    job_title = ''
                    for selector in job_title_selectors:
                        try:
                            title_element = entry.find_element(By.CSS_SELECTOR, selector)
                            job_title = title_element.text.strip()
                            if job_title:
                                break
                        except:
                            continue
                    
                    # Extract company name
                    company_selectors = [
                        ".pv-entity__secondary-title",
                        ".pv-entity__summary-info h4",
                        ".pv-entity__summary-info .t-14.t-black--light.t-normal",
                        ".pv-entity__summary-info-v2 h4",
                        ".pv-entity__summary-info-v2 .t-14.t-black--light.t-normal"
                    ]
                    
                    company = ''
                    for selector in company_selectors:
                        try:
                            company_element = entry.find_element(By.CSS_SELECTOR, selector)
                            company = company_element.text.strip()
                            if company:
                                break
                        except:
                            continue
                    
                    # Extract date information to check if it's current/most recent
                    date_selectors = [
                        ".pv-entity__dates .t-14.t-black--light.t-normal",
                        ".pv-entity__summary-info .t-14.t-black--light.t-normal",
                        ".pv-entity__summary-info-v2 .t-14.t-black--light.t-normal",
                        ".pvs-entity__caption-wrapper"
                    ]
                    
                    date_text = ''
                    is_current = False
                    for selector in date_selectors:
                        try:
                            date_element = entry.find_element(By.CSS_SELECTOR, selector)
                            date_text = date_element.text.strip()
                            if date_text:
                                # Check if it contains "Present" or "Current"
                                if 'Present' in date_text or 'Current' in date_text:
                                    is_current = True
                                break
                        except:
                            continue
                    
                    logger.info(f"Entry {i+1}: Job='{job_title}', Company='{company}', Date='{date_text}', Current={is_current}")
                    
                    # Return the first entry (most recent) or the current one
                    if job_title and company:
                        if is_current or i == 0:  # First entry is usually most recent
                            logger.info(f"Selected most recent job: {job_title} at {company}")
                            return company, job_title
                
                except Exception as e:
                    logger.warning(f"Error processing experience entry {i+1}: {e}")
                    continue
            
            logger.warning("No valid experience entries found")
            return '', ''
            
        except Exception as e:
            logger.error(f"Error extracting current job from experience: {e}")
            return '', ''

    def _extract_company_and_title(self) -> tuple:
        """
        Extract company and job title - try Experience section first, then fallback to main profile
        """
        try:
            # First, try to get current job from Experience section
            company, job_title = self._extract_current_job_from_experience()
            if company and job_title:
                return company, job_title
            
            # Fallback: try the main profile section
            logger.info("Experience section failed, trying main profile section")
            
            # Try multiple selectors for the main profile info
            selectors_to_try = [
                "div.text-body-medium.break-words",
                "div[data-generated-suggestion-target*='profileActionDelegate']",
                ".pv-text-details__left-panel .text-body-medium",
                ".pv-text-details__left-panel .break-words",
                ".pv-top-card--list-bullet .text-body-medium",
                ".pv-top-card--list-bullet .break-words"
            ]
            
            for selector in selectors_to_try:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 10:  # Filter out short/empty text
                            logger.info(f"Found profile text: {text}")
                            
                            # Try to parse company and job title
                            company, job_title = self._parse_company_and_title(text)
                            if company or job_title:
                                return company, job_title
                except:
                    continue
            
            logger.warning("Could not extract company and job title")
            return '', ''
            
        except Exception as e:
            logger.error(f"Error extracting company and title: {e}")
            return '', ''
    
    def _parse_company_and_title(self, text: str) -> tuple:
        """
        Parse company and job title from profile text
        """
        try:
            # Handle "Job Title at Company" format (most common)
            if ' at ' in text:
                parts = text.split(' at ')
                if len(parts) == 2:
                    job_title = parts[0].strip()
                    company = parts[1].strip()
                    
                    # Clean up job title (remove common prefixes)
                    job_title = job_title.replace('former ', '').replace('current ', '').strip()
                    
                    return company, job_title
            
            # Handle comma-separated format: "Company, Department, Job Title"
            if ',' in text:
                parts = [part.strip() for part in text.split(',')]
                if len(parts) >= 2:
                    company = parts[0]
                    job_title = parts[-1]  # Last part is usually the job title
                    
                    # Clean up the job title
                    job_title = job_title.replace('Department Chair', '').replace('Manager', '').strip()
                    if job_title.endswith(','):
                        job_title = job_title[:-1].strip()
                    
                    return company, job_title
            
            # Single part - treat as job title, no company
            return '', text.strip()
                    
        except Exception as e:
            logger.error(f"Error parsing company and title from '{text}': {e}")
            return '', text.strip()

def test_single_url():
    """
    Simple test function with hardcoded URL
    Comment/uncomment this section to test
    """
    from linkedin_enricher import LinkedInEnricher
    
    # Initialize the enricher to get the driver
    enricher = LinkedInEnricher()
    
    try:
        # Initialize the scraper
        scraper = LinkedInProfileScraper(enricher.driver)
        
        # HARDCODED TEST URL - Change this to test different profiles
        test_url = "https://www.linkedin.com/in/matt-amann-b2062211"
        
        print("="*60)
        print("🔍 TESTING LINKEDIN PROFILE SCRAPER")
        print("="*60)
        print(f"Testing URL: {test_url}")
        print("="*60)
        
        # Extract profile info
        profile_data = scraper.extract_profile_info(test_url)
        
        # Display results
        print("\n=== EXTRACTION RESULTS ===")
        print(f"LinkedIn URL: {profile_data['linkedin_url']}")
        print(f"Company: '{profile_data['company']}'")
        print(f"Job Title: '{profile_data['job_title']}'")
        print(f"Description: '{profile_data['description'][:200]}...' (first 200 chars)")
        print(f"Scraped At: {profile_data['scraped_at']}")
        
        # Test individual methods for debugging
        print("\n=== DEBUGGING INDIVIDUAL METHODS ===")
        
        # Test description extraction
        print("\n--- Description Extraction ---")
        description = scraper._extract_description()
        print(f"Description: '{description[:100]}...' (first 100 chars)")
        
        # Test About section extraction
        print("\n--- About Section Extraction ---")
        about_text = scraper._extract_about_section()
        print(f"About section found: {bool(about_text)}")
        if about_text:
            print(f"About text: '{about_text[:100]}...' (first 100 chars)")
        else:
            print("No About section found, testing fallback...")
            
        # Test fallback description
        print("\n--- Fallback Description ---")
        fallback_text = scraper._extract_fallback_description()
        print(f"Fallback text: '{fallback_text}'")
        
        # Test company and title extraction
        print("\n--- Company and Title Extraction ---")
        company, job_title = scraper._extract_company_and_title()
        print(f"Company: '{company}'")
        print(f"Job Title: '{job_title}'")
        
        print("\n=== TEST COMPLETED ===")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
    finally:
        enricher.close()

if __name__ == "__main__":
    # COMMENT/UNCOMMENT THESE LINES TO SWITCH BETWEEN TEST AND MAIN MODE
    
    # TEST MODE - Test single hardcoded URL
    test_single_url()
    
    # MAIN MODE - Process CSV file (commented out for now)
    # main()
