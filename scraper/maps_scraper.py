import time
import json
import logging
import random
import os
import sys
import subprocess
from typing import Dict, List, Optional, Union
from urllib.parse import quote
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('server.log')  # Log to file
    ]
)
logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    """
    A class to scrape business data from Google Maps.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the Google Maps scraper.
        
        Args:
            headless (bool): Whether to run Chrome in headless mode.
        """
        self.headless = headless
        self.driver = None
        self.setup_driver()
        
    def setup_driver(self):
        """Set up the Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--lang=en-US")
        
        # Add user agent to appear more like a regular browser
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # For Windows, check Chrome installation and version
        chrome_path = None
        if os.name == 'nt':
            try:
                for path in [
                    os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe'),
                    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                ]:
                    if os.path.exists(path):
                        chrome_path = path
                        break
                        
                if chrome_path:
                    logger.info(f"Found Chrome at: {chrome_path}")
                    # Get Chrome version
                    try:
                        result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
                        chrome_version = result.stdout.strip()
                        logger.info(f"Chrome version: {chrome_version}")
                    except Exception as e:
                        logger.warning(f"Failed to get Chrome version: {str(e)}")
                else:
                    logger.warning("Chrome not found in expected locations.")
            except Exception as e:
                logger.warning(f"Error checking Chrome installation: {str(e)}")
        
        attempts = 0
        max_attempts = 3
        last_error = None
        
        while attempts < max_attempts:
            try:
                attempts += 1
                logger.info(f"ChromeDriver setup attempt {attempts}/{max_attempts}")
                
                if attempts == 1:
                    # First attempt: Use webdriver_manager to get the ChromeDriver
                    try:
                        # Try to get a specific version that matches the Chrome version
                        if chrome_path and os.name == 'nt':
                            try:
                                result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
                                version_text = result.stdout.strip()
                                if version_text:
                                    # Extract version number (e.g., "Google Chrome 120.0.6099.130" -> "120.0.6099.130")
                                    version_parts = version_text.split(' ')
                                    if len(version_parts) >= 3:
                                        chrome_version = version_parts[-1]
                                        # Get major version (e.g., "120.0.6099.130" -> "120")
                                        major_version = chrome_version.split('.')[0]
                                        logger.info(f"Using Chrome major version: {major_version}")
                                        
                                        # Use version-specific ChromeDriver
                                        service = Service(ChromeDriverManager(version=f"{major_version}.0.0.0").install())
                                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                                        return
                            except Exception as e:
                                logger.warning(f"Failed to get Chrome version-specific driver: {str(e)}")
                        
                        # Default case - let webdriver_manager find the appropriate driver
                        service = Service(ChromeDriverManager().install())
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    except Exception as e:
                        logger.error(f"Error with webdriver_manager: {str(e)}")
                        raise
                elif attempts == 2:
                    # Second attempt: Try with built-in ChromeDriver
                    self.driver = webdriver.Chrome(options=chrome_options)
                else:
                    # Third attempt: Try with explicit Chrome path if available
                    if chrome_path and os.name == 'nt':
                        chrome_options.binary_location = chrome_path
                        self.driver = webdriver.Chrome(options=chrome_options)
                    else:
                        # Last resort
                        raise last_error or Exception("Failed to initialize ChromeDriver after multiple attempts")
                
                # If we get here, driver initialized successfully
                logger.info("ChromeDriver initialized successfully")
                break
                
            except Exception as e:
                last_error = e
                logger.error(f"Error initializing ChromeDriver (attempt {attempts}/{max_attempts}): {str(e)}")
                time.sleep(1)  # Wait before retry
        
        if self.driver is None:
            error_msg = f"Failed to initialize ChromeDriver: {str(last_error)}"
            logger.error(error_msg)
            if "not a valid Win32 application" in str(last_error):
                error_msg = ("ChromeDriver compatibility issue. Please ensure you have the latest Google Chrome "
                            "installed and try again. This error typically occurs when there's a mismatch between "
                            "ChromeDriver and Chrome versions.")
            raise Exception(error_msg)
                
        self.wait = WebDriverWait(self.driver, 10)
        logger.info("WebDriver setup completed")
        
    def handle_consent_dialog(self):
        """Handle Google's consent dialog if it appears."""
        try:
            # Look for different types of consent dialogs and accept buttons
            consent_button_selectors = [
                "button#L2AGLb",  # Standard Google consent
                "button[aria-label='Accept all']",
                "button[aria-label='I agree']",
                "button[jsname='higCR']",
                "form[action*='consent'] button",
                "button[jsaction*='consent']",
                ".consent-bump-dialog button"
            ]
            
            for selector in consent_button_selectors:
                try:
                    consent_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if consent_buttons:
                        for button in consent_buttons:
                            if button.is_displayed():
                                logger.info(f"Found consent dialog, clicking accept button: {selector}")
                                button.click()
                                time.sleep(1)  # Wait for dialog to close
                                return True
                except Exception as e:
                    logger.debug(f"No consent button found with selector {selector}: {str(e)}")
                    continue
            
            logger.debug("No consent dialog found or needed")
            return False
        except Exception as e:
            logger.warning(f"Error handling consent dialog: {str(e)}")
            return False
    
    def handle_captcha(self):
        """
        Check for and handle Google captcha if present.
        Returns True if captcha was found (handled or not), False otherwise.
        """
        try:
            # Take a screenshot to see if there's a captcha
            self.driver.save_screenshot("captcha_check.png")
            
            # Check for various captcha indicators
            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "div.recaptcha-checkbox-border",
                "div[data-callback='onRecaptchaSuccess']",
                "#captcha-form",
                "form[action*='challenge']"
            ]
            
            for selector in captcha_selectors:
                try:
                    captcha_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if captcha_elements and any(elem.is_displayed() for elem in captcha_elements):
                        logger.warning(f"CAPTCHA detected! Using selector: {selector}")
                        self.driver.save_screenshot("captcha_found.png")
                        
                        # Since we're in non-headless mode, we'll pause to let the user solve it manually
                        logger.critical("CAPTCHA requires human intervention. Please solve the CAPTCHA in the browser window.")
                        logger.critical("The program will wait 30 seconds for you to complete the CAPTCHA...")
                        
                        # Pause to give the user time to solve the captcha manually
                        time.sleep(30)
                        
                        # Check if we're still on a captcha page
                        if any(self.driver.find_elements(By.CSS_SELECTOR, selector)):
                            logger.warning("Still on CAPTCHA page after waiting. Continuing anyway...")
                        else:
                            logger.info("CAPTCHA appears to be solved! Continuing...")
                        
                        return True
                except Exception as e:
                    logger.debug(f"Error checking captcha with selector {selector}: {str(e)}")
            
            return False
        except Exception as e:
            logger.warning(f"Error in captcha handling: {str(e)}")
            return False
    
    def scroll_results(self, max_results: int = 100):
        """
        Scroll through the search results to load more businesses.
        
        Args:
            max_results (int): Maximum number of results to load.
        """
        logger.debug(f"Attempting to scroll and load up to {max_results} results")
        try:
            # First try the standard feed container
            feed_selectors = [
                "div[role='feed']",
                "div.section-result-content",
                "div.section-scrollbox",
                ".section-result",
                "div[aria-label='Results for " + self.driver.title + "']"
            ]
            
            results_div = None
            for selector in feed_selectors:
                try:
                    logger.debug(f"Trying to find results container with selector: {selector}")
                    results_div = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if results_div:
                        logger.debug(f"Found results container with selector: {selector}")
                        break
                except NoSuchElementException:
                    continue
            
            if not results_div:
                logger.debug("Could not find results container with predefined selectors, trying to scroll the whole page")
                results_div = self.driver.find_element(By.TAG_NAME, "body")
            
            # Take a screenshot before scrolling
            self.driver.save_screenshot("before_scrolling.png")
            
            # Get initial set of results
            prev_results_count = 0
            
            # Try different selectors for business results
            business_selectors = [
                "div[role='article']",
                ".section-result",
                ".place-result",
                "a[href*='maps/place']"
            ]
            
            # Find all business elements with different selectors
            business_elements = []
            for selector in business_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    business_elements = elements
                    logger.debug(f"Found {len(elements)} business elements with selector: {selector}")
                    break
            
            current_results_count = len(business_elements)
            logger.debug(f"Initial business count: {current_results_count}")
            
            with tqdm(total=max_results, desc="Loading results") as pbar:
                pbar.update(current_results_count)
                
                scroll_attempts = 0
                max_scroll_attempts = 10  # Limit scrolling attempts
                
                # Continue scrolling until we reach max_results or results stop loading
                while current_results_count < max_results and current_results_count > prev_results_count and scroll_attempts < max_scroll_attempts:
                    scroll_attempts += 1
                    
                    # Scroll to the bottom of the results
                    try:
                        # Try element scrolling first
                        self.driver.execute_script(
                            "arguments[0].scrollTop = arguments[0].scrollHeight", 
                            results_div
                        )
                        logger.debug(f"Scrolled results container (attempt {scroll_attempts})")
                    except Exception as e:
                        logger.warning(f"Error scrolling container: {str(e)}, trying window scroll")
                        # Fall back to window scrolling
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        logger.debug("Scrolled window instead")
                    
                    # Wait for new results to load
                    time.sleep(3 + random.uniform(0, 1))
                    
                    # Update results count using the successful selector
                    prev_results_count = current_results_count
                    
                    # Try to find business elements again
                    for selector in business_selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            business_elements = elements
                            break
                    
                    current_results_count = len(business_elements)
                    
                    # Update progress bar
                    pbar.update(current_results_count - prev_results_count)
                    logger.debug(f"After scroll {scroll_attempts}: {current_results_count} results")
                
                # Take a screenshot after scrolling
                self.driver.save_screenshot("after_scrolling.png")
                
            logger.info(f"Loaded {current_results_count} results after {scroll_attempts} scroll attempts")
            return current_results_count
            
        except NoSuchElementException as e:
            logger.error(f"Could not find results container: {str(e)}")
            # Take a screenshot for debugging
            self.driver.save_screenshot("error_no_results_container.png")
            return 0
        except Exception as e:
            logger.error(f"Error during scrolling: {str(e)}")
            # Take a screenshot for debugging
            self.driver.save_screenshot("error_during_scrolling.png")
            return 0
    
    def extract_business_links(self) -> List[str]:
        """
        Extract links to business details from search results.
        
        Returns:
            List[str]: List of URLs to business detail pages.
        """
        business_links = []
        
        try:
            # Save screenshot before extracting links
            self.driver.save_screenshot("before_extracting_links.png")
            logger.debug("Taking screenshot before extracting business links")
            
            # Check for new Google Maps UI
            new_ui = self.check_for_new_ui()
            
            # Try different selectors for business results
            business_selectors = [
                "div[role='article']", 
                ".section-result", 
                ".place-result",
                "a[href*='maps/place']",
                "div.Nv2PK",
                "a.hfpxzc"  # New Google Maps UI
            ]
            
            # If we detected the new UI, prioritize its selectors
            if new_ui:
                business_selectors.insert(0, "a.hfpxzc")
                business_selectors.insert(0, "a[jsaction*='mouseup:placeCard']")
            
            # Find all business result elements with different selectors
            business_elements = []
            used_selector = ""
            
            for selector in business_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                logger.debug(f"Trying selector {selector}: found {len(elements)} elements")
                
                if elements:
                    business_elements = elements
                    used_selector = selector
                    logger.info(f"Found {len(elements)} business elements with selector: {selector}")
                    break
                    
            if not business_elements:
                logger.warning("No business elements found with any selector")
                return business_links
                
            logger.info(f"Processing {len(business_elements)} business elements")
            
            # Different extraction strategy based on the selector that worked
            if "maps/place" in used_selector or "href" in used_selector or new_ui:
                # These are direct links
                for element in business_elements:
                    try:
                        business_url = element.get_attribute("href")
                        if business_url and ("maps/place" in business_url or "maps/search" in business_url):
                            business_links.append(business_url)
                            logger.debug(f"Added direct link: {business_url}")
                    except Exception as e:
                        logger.error(f"Error extracting direct link: {str(e)}")
            else:
                # Need to click each element
                for i, element in enumerate(business_elements):
                    try:
                        logger.debug(f"Processing business element {i+1}/{len(business_elements)}")
                        
                        # Try to scroll element into view
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.5)
                        
                        # Try to click the element
                        try:
                            element.click()
                            logger.debug(f"Clicked on business element {i+1}")
                        except Exception as click_error:
                            logger.warning(f"Could not click normally: {str(click_error)}")
                            # Try JavaScript click as fallback
                            try:
                                self.driver.execute_script("arguments[0].click();", element)
                                logger.debug(f"Clicked with JavaScript on business element {i+1}")
                            except Exception as js_click_error:
                                logger.error(f"JavaScript click also failed: {str(js_click_error)}")
                                continue
                                
                        # Wait for details to load
                        time.sleep(1.5 + random.uniform(0, 1))
                        
                        # Get the current URL (business details page)
                        business_url = self.driver.current_url
                        
                        if "maps/place" in business_url or "maps/search" in business_url:
                            business_links.append(business_url)
                            logger.debug(f"Added business URL: {business_url}")
                        else:
                            logger.warning(f"URL doesn't look like a business page: {business_url}")
                        
                        # Go back to results
                        self.driver.back()
                        time.sleep(1.5 + random.uniform(0, 1))
                        
                        # Wait for results to load again
                        try:
                            # Wait for search results to appear again
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, used_selector))
                            )
                            logger.debug("Successfully returned to results page")
                        except TimeoutException:
                            logger.warning("Timeout waiting for results page after going back")
                            # Try to navigate to original search again if we got lost
                            if i < len(business_elements) - 1:  # Don't bother if this is the last element
                                try:
                                    current_url = self.driver.current_url
                                    if "maps/search" not in current_url:
                                        logger.warning("Lost results page, trying to navigate back")
                                        # Get elements again as they might be stale
                                        business_elements = self.driver.find_elements(By.CSS_SELECTOR, used_selector)
                                except Exception as nav_error:
                                    logger.error(f"Error during navigation recovery: {str(nav_error)}")
                        
                    except (StaleElementReferenceException, Exception) as e:
                        logger.error(f"Error processing business element {i+1}: {str(e)}")
                        continue
            
            # Take screenshot after extracting links
            self.driver.save_screenshot("after_extracting_links.png")
            logger.debug(f"Extracted {len(business_links)} business links in total")
                    
        except Exception as e:
            logger.error(f"Error extracting business links: {str(e)}")
            # Take screenshot on error
            self.driver.save_screenshot("error_extracting_links.png")
            
        return business_links
    
    def check_for_new_ui(self):
        """Check if we're dealing with the new Google Maps UI."""
        try:
            # Modern UI elements to check for
            new_ui_indicators = [
                "a.hfpxzc",  # Modern place cards
                "div[jsaction*='mouseover:pane.placeCard']",  # Modern place card interactions
                "div.lI9IFe",  # New sidebar
                "div.bJzME"   # New header structure
            ]
            
            for indicator in new_ui_indicators:
                elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements and any(e.is_displayed() for e in elements):
                    logger.info(f"Detected new Google Maps UI via selector: {indicator}")
                    return True
            
            logger.debug("Using classic Google Maps UI")
            return False
        except Exception as e:
            logger.debug(f"Error checking for new UI: {str(e)}")
            return False
    
    def extract_business_data(self, url: str) -> Dict:
        """
        Extract detailed information about a business from its Google Maps page.
        
        Args:
            url (str): URL of the business details page.
            
        Returns:
            Dict: Dictionary containing business details.
        """
        try:
            logger.debug(f"Extracting business data from: {url}")
            self.driver.get(url)
            time.sleep(2 + random.uniform(0, 1))  # Wait longer for page to fully load
            
            # Save screenshot for debugging
            self.driver.save_screenshot(f"business_page_{url.split('/')[-1][:20]}.png")
            
            # Wait for business details to load
            try:
                # Try multiple possible selectors for the business name
                name_selectors = [
                    "h1.fontHeadlineLarge", 
                    "h1.section-hero-header-title", 
                    "h1[class*='headline']",
                    "div[class*='fontHeadline']",
                    "div[class*='header']"
                ]
                
                element_found = False
                for selector in name_selectors:
                    try:
                        self.wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        element_found = True
                        logger.debug(f"Found business name with selector: {selector}")
                        break
                    except TimeoutException:
                        continue
                
                if not element_found:
                    logger.warning("Timeout waiting for business details, proceeding anyway")
            except Exception as e:
                logger.warning(f"Error waiting for business details: {str(e)}")
            
            # Initialize business data dictionary
            business_data = {
                "url": url,
                "name": "",
                "address": "",
                "phone": "",
                "website": "",
                "category": "",
                "rating": "",
                "reviews_count": "",
                "hours": {},
                "coordinates": {}
            }
            
            # Extract business name
            for selector in ["h1.fontHeadlineLarge", "h1.section-hero-header-title", "h1", "div.fontHeadlineLarge"]:
                try:
                    business_data["name"] = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    ).text
                    if business_data["name"]:
                        logger.debug(f"Extracted business name: {business_data['name']}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract address
            address_selectors = [
                "button[data-item-id='address']",
                "button[data-tooltip='Copy address']",
                "button[aria-label*='address']",
                "div[data-attrid='kc:/location/location:address']"
            ]
            
            for selector in address_selectors:
                try:
                    address_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    business_data["address"] = address_element.text
                    if business_data["address"]:
                        logger.debug(f"Extracted address: {business_data['address']}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract phone number
            phone_selectors = [
                "button[data-item-id='phone:tel:']",
                "button[data-tooltip='Copy phone number']",
                "button[aria-label*='phone']",
                "a[href^='tel:']",
                "div[data-attrid='kc:/collection/knowledge_panels/has_phone:phone']"
            ]
            
            for selector in phone_selectors:
                try:
                    phone_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    
                    if selector.startswith("a[href"):
                        # If it's a tel link, get the href and clean it
                        href = phone_element.get_attribute("href")
                        if href:
                            business_data["phone"] = href.replace("tel:", "")
                    else:
                        business_data["phone"] = phone_element.text
                        
                    if business_data["phone"]:
                        logger.debug(f"Extracted phone: {business_data['phone']}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract website
            website_selectors = [
                "a[data-item-id='authority']",
                "a[aria-label*='website']",
                "a[data-tooltip='Open website']",
                "a[href*='http']:not([href*='google'])"
            ]
            
            for selector in website_selectors:
                try:
                    website_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    business_data["website"] = website_element.get_attribute("href")
                    if business_data["website"]:
                        logger.debug(f"Extracted website: {business_data['website']}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract category
            category_selectors = [
                "button[jsaction*='pane.rating.category']",
                "span[jstcache*='category']",
                "div[jsaction*='category']",
                "button[jsaction*='category']"
            ]
            
            for selector in category_selectors:
                try:
                    category_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    business_data["category"] = category_element.text
                    if business_data["category"]:
                        logger.debug(f"Extracted category: {business_data['category']}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extract rating and reviews
            rating_selectors = [
                "div.fontDisplayLarge",
                "span.section-star-display",
                "span[aria-label*='stars']",
                "span[aria-label*='rating']"
            ]
            
            for selector in rating_selectors:
                try:
                    rating_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    
                    rating_text = rating_element.text or rating_element.get_attribute("aria-label")
                    
                    if rating_text:
                        # Try to extract just the number
                        import re
                        rating_match = re.search(r'(\d+\.\d+)', rating_text)
                        if rating_match:
                            business_data["rating"] = rating_match.group(1)
                            logger.debug(f"Extracted rating: {business_data['rating']}")
                            break
                        else:
                            business_data["rating"] = rating_text
                            break
                except NoSuchElementException:
                    continue
            
            # Extract review count
            reviews_selectors = [
                "span[jsaction*='reviews']",
                "span[aria-label*='reviews']",
                "div[class*='review']",
                "button[jsaction*='reviews']"
            ]
            
            for selector in reviews_selectors:
                try:
                    reviews_element = self.driver.find_element(
                        By.CSS_SELECTOR, selector
                    )
                    
                    reviews_text = reviews_element.text or reviews_element.get_attribute("aria-label")
                    
                    if reviews_text:
                        # Try to extract just the number
                        import re
                        reviews_match = re.search(r'(\d+)', reviews_text)
                        if reviews_match:
                            business_data["reviews_count"] = reviews_match.group(1)
                            logger.debug(f"Extracted reviews count: {business_data['reviews_count']}")
                            break
                except NoSuchElementException:
                    continue
            
            # Extract hours
            try:
                hours_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR, "button[aria-label*='hour' i], button[aria-label*='open' i], button[data-item-id*='hour' i]"
                )
                
                if hours_buttons:
                    logger.debug(f"Found {len(hours_buttons)} possible hours buttons")
                    for button in hours_buttons:
                        try:
                            # Try to click the hours button
                            button.click()
                            logger.debug("Clicked on hours button")
                            time.sleep(1)  # Wait for hours to expand
                            
                            # Try to find hours elements
                            hours_elements = self.driver.find_elements(
                                By.CSS_SELECTOR, "div[role='gridcell'], td[style*='hours'], tr[jsaction*='hours']"
                            )
                            
                            if hours_elements:
                                logger.debug(f"Found {len(hours_elements)} hours elements")
                                # Only process elements that look like they contain day information
                                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                                
                                for element in hours_elements:
                                    text = element.text.lower()
                                    
                                    if any(day in text for day in days):
                                        for day in days:
                                            if day in text:
                                                # Extract hours for this day
                                                day_hours = text.replace(day, "").strip()
                                                business_data["hours"][day] = day_hours
                                                logger.debug(f"Found hours for {day}: {day_hours}")
                            
                            # Click somewhere else to close the hours
                            webdriver.ActionChains(self.driver).move_by_offset(0, 0).click().perform()
                            
                            # If we found at least some hours, break
                            if business_data["hours"]:
                                break
                                
                        except Exception as e:
                            logger.warning(f"Error extracting hours from button: {str(e)}")
                            continue
            except Exception as e:
                logger.warning(f"Error extracting hours: {str(e)}")
            
            # Extract coordinates from URL
            try:
                url_parts = url.split('!3d')
                if len(url_parts) > 1:
                    lat_lng = url_parts[1].split('!4d')
                    if len(lat_lng) > 1:
                        latitude = lat_lng[0]
                        longitude = lat_lng[1].split('!')[0]
                        business_data["coordinates"] = {
                            "latitude": latitude,
                            "longitude": longitude
                        }
                        logger.debug(f"Extracted coordinates: {latitude}, {longitude}")
            except Exception as e:
                logger.warning(f"Error extracting coordinates: {str(e)}")
                
            # Clean up empty values
            non_empty_data = {k: v for k, v in business_data.items() if v or isinstance(v, dict)}
            
            return non_empty_data
            
        except Exception as e:
            logger.error(f"Error extracting business data from {url}: {str(e)}")
            return {"url": url, "error": str(e)}
    
    def search(self, query: str, location: str) -> str:
        """
        Search for businesses on Google Maps.
        
        Args:
            query (str): The type of business to search for (e.g., "restaurants", "dentists").
            location (str): The location to search in (e.g., "New York, NY").
            
        Returns:
            str: The URL of the search results page.
        """
        search_query = f"{query} in {location}"
        encoded_query = quote(search_query)
        url = f"https://www.google.com/maps/search/{encoded_query}"
        
        logger.info(f"Searching for: {search_query}")
        self.driver.get(url)
        
        # Handle consent dialogs if they appear
        self.handle_consent_dialog()
        
        # Handle captcha if present
        if self.handle_captcha():
            logger.info("Proceeding after captcha check")
            
        # Wait for search results to load
        try:
            logger.debug("Waiting for search results to load...")
            # Save screenshot for debugging
            self.driver.save_screenshot("search_results_page.png")
            logger.debug(f"Screenshot saved to search_results_page.png")
            
            # First try with a feed element
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
                )
                logger.debug("Found results feed element")
            except TimeoutException:
                logger.warning("Could not find feed element, trying alternative selectors")
                
                # Try alternative selectors
                try:
                    # Look for any search results container
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".section-result, .place-result, div[role='article']"))
                    )
                    logger.debug("Found results using alternative selector")
                except TimeoutException:
                    logger.warning("Still couldn't find results, trying last resort selector")
                    # Last resort - just wait for the page to load something
                    time.sleep(5)
        except Exception as e:
            logger.error(f"Error waiting for search results: {str(e)}")
            
        # Log page source for debugging
        logger.debug(f"Current URL: {self.driver.current_url}")
        logger.debug("Page title: " + self.driver.title)
        
        return self.driver.current_url
    
    def scrape_businesses(self, query: str, location: str, max_results: int = 20) -> List[Dict]:
        """
        Search for and scrape business data from Google Maps.
        
        Args:
            query (str): The type of business to search for.
            location (str): The location to search in.
            max_results (int): Maximum number of businesses to scrape.
            
        Returns:
            List[Dict]: List of dictionaries containing business details.
        """
        results = []
        
        try:
            # Search for businesses
            logger.info(f"Searching for {query} in {location}")
            self.search(query, location)
            
            # Scroll to load more results
            loaded_count = self.scroll_results(max_results)
            logger.info(f"Loaded {loaded_count} business listings")
            
            if loaded_count == 0:
                logger.warning("No businesses found to scrape")
                # Try direct search as fallback
                try:
                    logger.info("Trying direct Google Maps search as fallback")
                    direct_url = f"https://www.google.com/maps/search/{query}+{location}".replace(' ', '+')
                    self.driver.get(direct_url)
                    time.sleep(3)  # Wait for page to load
                    logger.debug(f"Direct search URL: {direct_url}")
                    
                    # Take screenshot to see what we got
                    self.driver.save_screenshot("direct_search_fallback.png")
                    
                    # Try scrolling again
                    loaded_count = self.scroll_results(max_results)
                    logger.info(f"Fallback search loaded {loaded_count} business listings")
                except Exception as e:
                    logger.error(f"Error in fallback search: {str(e)}")
            
            # Extract business links
            business_links = self.extract_business_links()
            logger.info(f"Found {len(business_links)} business links")
            
            # Save links for debugging
            if business_links:
                with open("business_links.txt", "w") as f:
                    for link in business_links:
                        f.write(f"{link}\n")
                logger.debug("Saved business links to business_links.txt")
            
            # Limit to max_results
            business_links = business_links[:max_results]
            
            # Extract data for each business
            for i, url in enumerate(business_links):
                try:
                    logger.info(f"Scraping business {i+1}/{len(business_links)}: {url}")
                    business_data = self.extract_business_data(url)
                    
                    # Make sure we have at least some basic data
                    if business_data and (business_data.get("name") or business_data.get("address")):
                        results.append(business_data)
                        logger.info(f"Successfully scraped business data: {business_data.get('name', 'Unknown')}")
                    else:
                        logger.warning(f"Skipping business with insufficient data: {url}")
                    
                    # Add a random delay between requests to avoid getting blocked
                    delay = 2 + random.uniform(0, 2)
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Error scraping business at {url}: {str(e)}")
                    continue
            
            # Check if we got any results
            if not results:
                logger.error("No business data was successfully scraped")
                # Create a dummy result for debugging purposes
                results.append({
                    "error": "No businesses found",
                    "query": query,
                    "location": location,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.info(f"Successfully scraped {len(results)} businesses")
                    
        except Exception as e:
            logger.error(f"Error in scrape_businesses: {str(e)}")
            # Create a dummy result for the error
            results.append({
                "error": str(e),
                "query": query,
                "location": location,
                "timestamp": datetime.now().isoformat()
            })
            
        return results
    
    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def save_results_to_file(results: List[Dict], filename: str, file_format: str = "json"):
    """
    Save scraped results to a file.
    
    Args:
        results (List[Dict]): List of business data dictionaries.
        filename (str): Filename to save to (without extension).
        file_format (str): File format, either "json" or "csv".
    """
    try:
        if file_format.lower() == "json":
            with open(f"{filename}.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {filename}.json")
            
        elif file_format.lower() == "csv":
            import pandas as pd
            
            # Flatten nested dictionaries (hours, coordinates)
            flattened_results = []
            for business in results:
                flat_business = business.copy()
                
                # Handle coordinates
                if "coordinates" in flat_business and isinstance(flat_business["coordinates"], dict):
                    for key, value in flat_business["coordinates"].items():
                        flat_business[f"coordinates_{key}"] = value
                    del flat_business["coordinates"]
                
                # Handle hours
                if "hours" in flat_business and isinstance(flat_business["hours"], dict):
                    for day, hours in flat_business["hours"].items():
                        flat_business[f"hours_{day}"] = hours
                    del flat_business["hours"]
                
                flattened_results.append(flat_business)
            
            df = pd.DataFrame(flattened_results)
            df.to_csv(f"{filename}.csv", index=False, encoding="utf-8")
            logger.info(f"Results saved to {filename}.csv")
            
        else:
            logger.error(f"Unsupported file format: {file_format}")
            
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}")


if __name__ == "__main__":
    # Example usage
    query = "restaurants"
    location = "New York, NY"
    max_results = 10
    
    with GoogleMapsScraper(headless=True) as scraper:
        results = scraper.scrape_businesses(query, location, max_results)
        
        if results:
            print(f"Scraped {len(results)} businesses")
            # Save results to files
            save_results_to_file(results, f"{query}_{location}_results", "json")
            save_results_to_file(results, f"{query}_{location}_results", "csv")
        else:
            print("No results found") 