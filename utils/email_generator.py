import os
import logging
import json
from typing import Dict, List, Optional, Union
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailTemplateGenerator:
    """Generate personalized cold email templates using AI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the email template generator.
        
        Args:
            api_key (str, optional): OpenAI API key. If not provided, will try to get from environment.
        """
        # Get API key from constructor or environment
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            # Log only once to avoid repeated warnings
            if not hasattr(EmailTemplateGenerator, '_warning_logged'):
                logger.warning(
                    "No OpenAI API key provided. Email generation will use pre-written templates. "
                    "Set OPENAI_API_KEY in your .env file to enable AI-powered templates."
                )
                EmailTemplateGenerator._warning_logged = True
        else:
            openai.api_key = self.api_key
            logger.info("OpenAI API key configured successfully")
        
        # Enhanced fallback templates with more dynamic fields
        self.fallback_templates = [
            "Subject: Partnering with {business_name} to Boost Your Growth\n\n"
            "Hi there,\n\n"
            "I noticed {business_name} is doing great work in the {category} industry in {location}. "
            "I wanted to reach out because we've helped similar businesses increase their customer base by 30% on average.\n\n"
            "Your {rating}-star rating shows you're already delivering quality service. I'd love to discuss how we can "
            "help you reach even more customers who are searching for {category} services.\n\n"
            "Would you be open to a quick 15-minute call this week?\n\n"
            "Best regards,\n"
            "[Your Name]",
            
            "Subject: Quick question about {business_name}\n\n"
            "Hello,\n\n"
            "I recently came across {business_name} and was impressed by your reputation in the {category} industry. "
            "Our company specializes in helping businesses like yours expand their reach "
            "through targeted digital marketing.\n\n"
            "I'd love to learn more about your business goals and share a few ideas that have worked "
            "well for other {category} businesses in {location}.\n\n"
            "Are you available for a brief conversation this week?\n\n"
            "Thanks,\n"
            "[Your Name]",
            
            "Subject: Help {business_name} attract more customers\n\n"
            "Hello there,\n\n"
            "I hope this email finds you well. I was researching top {category} businesses in {location} "
            "and {business_name} caught my attention with its {rating}-star rating.\n\n"
            "We've developed a solution specifically for {category} businesses that helps them "
            "attract more qualified leads and convert them into customers.\n\n"
            "I'd be happy to share some insights on what's working for other businesses in your industry. "
            "Would you be interested in a quick call on Tuesday or Thursday?\n\n"
            "Regards,\n"
            "[Your Name]",
            
            "Subject: Opportunity for {business_name}\n\n"
            "Hi,\n\n"
            "I'm reaching out because I've been working with several {category} businesses in {location} and thought "
            "{business_name} might benefit from our services as well.\n\n"
            "We specialize in helping businesses like yours increase online visibility and generate more leads. "
            "Given your excellent reputation, I think we could help you capitalize on that even further.\n\n"
            "I have a few specific ideas I'd like to share. Would you be available for a quick chat?\n\n"
            "Thanks for your time,\n"
            "[Your Name]",
            
            "Subject: Potential collaboration with {business_name}\n\n"
            "Hello,\n\n"
            "I hope your week is going well. I'm reaching out because I believe there might be a good opportunity "
            "for collaboration between our companies.\n\n"
            "We've been working with several {category} businesses in {location} to help them grow their customer base "
            "and streamline their operations. Given {business_name}'s established presence, I think we might be able to "
            "offer some valuable services.\n\n"
            "Would you be open to a brief conversation to explore potential synergies?\n\n"
            "Best regards,\n"
            "[Your Name]"
        ]
    
    def _get_ai_generated_template(self, business_data: Dict) -> str:
        """
        Generate a personalized email template using OpenAI.
        
        Args:
            business_data (Dict): Business data to personalize the email.
            
        Returns:
            str: AI-generated email template.
        """
        try:
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            
            # Format basic information about the business for the prompt
            business_name = business_data.get('name', 'the business')
            category = business_data.get('category', 'local')
            location = business_data.get('address', '').split(',')[-1].strip() if business_data.get('address') else 'your area'
            
            # Build a rating description if available
            rating_info = ""
            if business_data.get('rating') and business_data.get('reviews_count'):
                rating_info = f" with a {business_data.get('rating')} rating from {business_data.get('reviews_count')} reviews"
            
            # Construct the prompt
            prompt = f"""
            Write a short, professional, and personalized cold email for a business outreach.
            
            Business information:
            - Name: {business_name}
            - Type: {category} business{rating_info}
            - Location: {location}
            
            The email should:
            1. Be concise (3-4 short paragraphs max)
            2. Sound natural and conversational, not salesy
            3. Include a subject line
            4. Demonstrate understanding of their business type
            5. Include a clear but gentle call to action
            6. Use [Your Name] as the signature
            
            Format as plain text with "Subject:" at the beginning.
            """
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a skilled business development expert who writes effective, personalized outreach emails."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            template = response.choices[0].message.content.strip()
            return template
            
        except Exception as e:
            logger.error(f"Error generating AI email template: {str(e)}")
            return None
    
    def generate_email_template(self, business_data: Dict) -> str:
        """
        Generate a personalized email template for a business.
        
        Args:
            business_data (Dict): Business data to personalize the email.
            
        Returns:
            str: Personalized email template.
        """
        # Try to generate template with AI first
        ai_template = None
        if self.api_key:
            ai_template = self._get_ai_generated_template(business_data)
        
        # Fall back to template-based approach if AI fails
        if not ai_template:
            import random
            
            # Select a random template
            template = random.choice(self.fallback_templates)
            
            # Get business data with fallbacks for missing fields
            business_name = business_data.get('name', 'your business')
            category = business_data.get('category', 'local')
            
            # Extract city from address or use fallback
            address = business_data.get('address', '')
            location = "your area"
            if address:
                # Try to extract city or region
                parts = address.split(',')
                if len(parts) >= 2:
                    location = parts[-2].strip()  # Usually the city is second-to-last part
                else:
                    location = parts[-1].strip()  # Use whatever we have
            
            rating = business_data.get('rating', '5')
            
            # Fill in the template with business data
            filled_template = template.format(
                business_name=business_name,
                category=category,
                location=location,
                rating=rating
            )
            
            return filled_template
        
        return ai_template
    
    def enrich_business_data_with_email_template(self, business_data: Dict) -> Dict:
        """
        Enrich business data with a personalized email template.
        
        Args:
            business_data (Dict): Business data dictionary.
            
        Returns:
            Dict: Enriched business data dictionary with email template.
        """
        # Generate email template
        email_template = self.generate_email_template(business_data)
        
        # Add template to business data
        business_data['email_template'] = email_template
        
        return business_data


if __name__ == "__main__":
    # Example usage
    generator = EmailTemplateGenerator()
    
    # Test with a sample business
    sample_business = {
        "name": "Sunset Cafe",
        "category": "Coffee Shop",
        "address": "123 Main St, New York, NY",
        "rating": "4.7",
        "reviews_count": "142"
    }
    
    enriched_data = generator.enrich_business_data_with_email_template(sample_business)
    print(f"Generated email template:\n\n{enriched_data['email_template']}") 