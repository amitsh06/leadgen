import re
import logging
import requests
from typing import Dict, List, Optional, Union
from bs4 import BeautifulSoup
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailFinder:
    """Utility class to find business owner email addresses."""
    
    def __init__(self):
        """Initialize the email finder."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Email regex pattern
        self.email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # Common email prefixes for business owners
        self.common_prefixes = [
            'contact', 'info', 'hello', 'support', 'admin', 'sales',
            'help', 'office', 'mail', 'team', 'business', 'inquiries',
            'feedback', 'customer', 'service', 'general', 'manager'
        ]
    
    def extract_domain_from_url(self, url: str) -> Optional[str]:
        """
        Extract domain name from URL.
        
        Args:
            url (str): Website URL.
            
        Returns:
            Optional[str]: Domain name or None if extraction fails.
        """
        if not url:
            return None
            
        try:
            # Remove protocol (http/https)
            domain = url.strip().lower()
            domain = re.sub(r'^https?://', '', domain)
            
            # Remove www
            domain = re.sub(r'^www\.', '', domain)
            
            # Remove path and query parameters
            domain = domain.split('/')[0]
            
            return domain
        except Exception as e:
            logger.error(f"Error extracting domain from URL {url}: {str(e)}")
            return None
    
    def find_emails_on_page(self, html_content: str) -> List[str]:
        """
        Find email addresses on a web page.
        
        Args:
            html_content (str): HTML content of the page.
            
        Returns:
            List[str]: List of email addresses found.
        """
        emails = set()
        
        try:
            # Find all email addresses using regex
            found_emails = re.findall(self.email_pattern, html_content)
            
            for email in found_emails:
                # Filter out emails that are likely not business emails
                if not any(
                    email.lower().endswith(domain) 
                    for domain in [
                        '.jpg', '.png', '.gif', '.jpeg', '.pdf', 
                        '.doc', '.docx', '.xls', '.xlsx', '.js', '.css'
                    ]
                ):
                    emails.add(email.lower())
                    
        except Exception as e:
            logger.error(f"Error finding emails on page: {str(e)}")
            
        return list(emails)
    
    def scrape_website_for_emails(self, url: str, max_pages: int = 3) -> List[str]:
        """
        Scrape a website for email addresses.
        
        Args:
            url (str): Website URL to scrape.
            max_pages (int): Maximum number of pages to scrape.
            
        Returns:
            List[str]: List of email addresses found.
        """
        all_emails = set()
        visited_urls = set()
        urls_to_visit = [url]
        
        # Clean up the URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Extract domain for internal link checking
        domain = self.extract_domain_from_url(url)
        
        try:
            # Scrape pages
            page_count = 0
            
            while urls_to_visit and page_count < max_pages:
                current_url = urls_to_visit.pop(0)
                
                if current_url in visited_urls:
                    continue
                    
                visited_urls.add(current_url)
                page_count += 1
                
                logger.info(f"Scraping page {page_count}/{max_pages}: {current_url}")
                
                try:
                    response = requests.get(
                        current_url, 
                        headers=self.headers, 
                        timeout=10
                    )
                    response.raise_for_status()
                    
                    # Find emails on the current page
                    page_emails = self.find_emails_on_page(response.text)
                    all_emails.update(page_emails)
                    
                    # If this is not the contact page, try to find a link to it
                    if page_count == 1:  # Only on the first page
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Look for contact page links
                        for link in soup.find_all('a', href=True):
                            href = link.get('href')
                            link_text = link.text.lower()
                            
                            if href and (
                                'contact' in link_text or 
                                'about' in link_text or
                                'contact' in href.lower() or
                                'about' in href.lower()
                            ):
                                # Handle relative URLs
                                if href.startswith('/'):
                                    contact_url = f"https://{domain}{href}"
                                elif href.startswith(('http://', 'https://')):
                                    # Only include if it's on the same domain
                                    if domain in self.extract_domain_from_url(href):
                                        contact_url = href
                                else:
                                    contact_url = f"https://{domain}/{href}"
                                
                                if contact_url not in visited_urls and contact_url not in urls_to_visit:
                                    urls_to_visit.append(contact_url)
                    
                except requests.RequestException as e:
                    logger.error(f"Error scraping {current_url}: {str(e)}")
                    continue
                
                # Add a random delay between requests
                time.sleep(1 + random.uniform(0, 2))
                
        except Exception as e:
            logger.error(f"Error scraping website for emails: {str(e)}")
            
        return list(all_emails)
    
    def generate_common_emails(self, domain: str, business_name: str = None, owner_name: str = None) -> List[str]:
        """
        Generate common email formats for a business.
        
        Args:
            domain (str): Business domain.
            business_name (str, optional): Name of the business.
            owner_name (str, optional): Name of the business owner.
            
        Returns:
            List[str]: List of generated email addresses.
        """
        if not domain:
            return []
            
        generated_emails = []
        
        # Add common prefix emails
        for prefix in self.common_prefixes:
            generated_emails.append(f"{prefix}@{domain}")
        
        # Add business name-based emails if provided
        if business_name:
            # Clean up business name
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', business_name.lower())
            
            if clean_name:
                generated_emails.append(f"{clean_name}@{domain}")
                generated_emails.append(f"info@{clean_name}.{domain.split('.')[-1]}")
        
        # Add owner name-based emails if provided
        if owner_name:
            # Split name into parts
            name_parts = owner_name.lower().split()
            
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                # Remove non-alphabetic characters
                first_name = re.sub(r'[^a-z]', '', first_name)
                last_name = re.sub(r'[^a-z]', '', last_name)
                
                if first_name and last_name:
                    # Generate common name formats
                    generated_emails.extend([
                        f"{first_name}@{domain}",
                        f"{last_name}@{domain}",
                        f"{first_name}.{last_name}@{domain}",
                        f"{first_name[0]}{last_name}@{domain}",
                        f"{first_name}{last_name[0]}@{domain}"
                    ])
        
        return generated_emails
    
    def find_business_emails(self, business_data: Dict) -> List[str]:
        """
        Find email addresses for a business.
        
        Args:
            business_data (Dict): Dictionary containing business details.
            
        Returns:
            List[str]: List of found email addresses.
        """
        found_emails = []
        
        # Get the website URL
        website_url = business_data.get('website', '')
        
        if not website_url:
            logger.warning(f"No website URL found for business: {business_data.get('name', 'Unknown')}")
            return found_emails
        
        try:
            # Extract domain
            domain = self.extract_domain_from_url(website_url)
            
            if not domain:
                logger.warning(f"Could not extract domain from URL: {website_url}")
                return found_emails
            
            # Step 1: Scrape the website for emails
            website_emails = self.scrape_website_for_emails(website_url)
            found_emails.extend(website_emails)
            
            # Step 2: Generate common email formats as a fallback
            if not found_emails:
                logger.info(f"No emails found on website. Generating common formats for domain: {domain}")
                generated_emails = self.generate_common_emails(
                    domain=domain,
                    business_name=business_data.get('name', ''),
                    owner_name=None  # We don't have owner name in our scraped data
                )
                
                # Mark these as generated (unverified)
                found_emails.extend([f"{email} (generated)" for email in generated_emails])
            
        except Exception as e:
            logger.error(f"Error finding business emails: {str(e)}")
            
        return found_emails
    
    def enrich_business_data_with_emails(self, business_data: Dict) -> Dict:
        """
        Find emails for a business and add them to the business data.
        
        Args:
            business_data (Dict): Business data dictionary.
            
        Returns:
            Dict: Enriched business data dictionary with emails.
        """
        try:
            website = business_data.get('website')
            business_name = business_data.get('name', '')
            
            emails = []
            
            if website:
                # Log that we're processing this business
                logger.info(f"Finding emails for: {business_name} - {website}")
                
                # Try to scrape actual emails from website
                scraped_emails = self.scrape_website_for_emails(website)
                if scraped_emails:
                    logger.info(f"Found {len(scraped_emails)} scraped emails for {business_name}")
                    emails.extend(scraped_emails)
                
                # Try to generate common email formats
                domain = self.extract_domain_from_url(website)
                if domain:
                    generated_emails = self.generate_common_emails(domain, business_name)
                    
                    # Only add generated emails if we didn't find any scraped ones
                    if not emails and generated_emails:
                        logger.info(f"Generated {len(generated_emails)} potential emails for {business_name}")
                        emails.extend(generated_emails)
            
            # Add emails to business data
            if emails:
                # Sort by likelihood of being a real business email (prioritize contact/info prefixes)
                priority_prefixes = ['contact', 'info', 'hello', 'support', 'admin', 'sales', 'hello']
                
                # Sort emails with priority prefixes to the top
                def email_sort_key(email):
                    email_prefix = email.split('@')[0].lower()
                    # Return 0 for priority prefixes (to sort them first), else return 1
                    return (0 if any(prefix == email_prefix for prefix in priority_prefixes) else 1, email)
                
                sorted_emails = sorted(emails, key=email_sort_key)
                business_data['emails'] = sorted_emails
                business_data['primary_email'] = sorted_emails[0] if sorted_emails else None
            else:
                business_data['emails'] = []
                business_data['primary_email'] = None
                logger.warning(f"No emails found for {business_name}")
            
            return business_data
            
        except Exception as e:
            logger.error(f"Error enriching business data with emails: {str(e)}")
            # Make sure we return the original data even if there's an error
            business_data['emails'] = []
            business_data['primary_email'] = None
            return business_data


if __name__ == "__main__":
    # Example usage
    finder = EmailFinder()
    
    # Test with a sample business
    sample_business = {
        "name": "Example Business",
        "website": "https://www.example.com"
    }
    
    enriched_data = finder.enrich_business_data_with_emails(sample_business)
    print(f"Found emails: {enriched_data['emails']}") 