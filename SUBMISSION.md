# LeadHarvest - Project Submission

## Project Overview
LeadHarvest is a comprehensive web-based tool that streamlines lead generation by automating the process of finding and connecting with potential clients. The application scrapes business information from Google Maps, finds email addresses from business websites, and generates personalized cold email templates - all through an intuitive user interface.

## Key Features
- **Intelligent Google Maps Scraping**: Automatically extracts detailed business information including name, address, phone number, website URL, ratings, and reviews
- **Smart Email Discovery**: Uses advanced techniques to find business email addresses from their websites
- **AI-Powered Email Templates**: Creates personalized cold email templates tailored to each business's specific characteristics
- **Multi-Format Data Export**: Download leads in JSON, CSV, and Excel formats with detailed business information
- **Real-Time Progress Updates**: Provides detailed progress information during the scraping process
- **Error Handling**: Robust error management for common issues like CAPTCHAs and connection problems
- **User-Friendly Interface**: Simple, responsive web interface accessible from any device

## Technologies Used
- **Frontend**: HTML, CSS, JavaScript (vanilla JS for lightweight performance)
- **Backend**: Python, FastAPI (for high-performance API development)
- **Scraping**: Selenium, BeautifulSoup4, ChromeDriver
- **Data Processing**: Pandas, XlsxWriter
- **API Integration**: OpenAI API (optional for enhanced email templates)

## Installation & Usage
Please refer to the README.md file for detailed installation and usage instructions. The application is designed to work on both Windows and macOS/Linux environments with minimal setup.

## Project Structure
```
lead_harvest/
│
├── api/ - FastAPI server and endpoints
│   ├── main.py - Main API entry point
│
├── frontend/ - Frontend files
│   ├── index.html - Main HTML file
│   ├── app.js - JavaScript for the frontend
│   ├── style.css - CSS styles
│
├── scraper/ - Web scraping modules
│   ├── maps_scraper.py - Google Maps scraping 
│   ├── email_finder.py - Email finding
│
├── utils/ - Utility functions
│   ├── email_generator.py - Email template generation
│
├── docs/ - Documentation
│   ├── images/ - Screenshots
│
├── requirements.txt - Project dependencies
├── requirements-full.txt - Complete environment dependencies
├── README.md - Documentation
└── LICENSE - MIT License
```

## Learning Outcomes
This project demonstrated practical application of:
- Web scraping with Selenium and BeautifulSoup in a real-world scenario
- API development with FastAPI for high-performance backend services
- Asynchronous programming in Python for efficient web scraping
- Frontend-backend integration for seamless user experience
- Data processing and export in multiple business-friendly formats
- Error handling and recovery in web automation systems

## Future Improvements
- Add user authentication system for multi-user support
- Implement database storage for lead history and campaign tracking
- Create email campaign management features with tracking capabilities
- Add advanced data visualization options for lead insights
- Improve email finding accuracy with additional data sources
- Implement rate limiting and proxy rotation for larger scale scraping

## Contact
For any questions or feedback about this submission, please contact amits.work369@gmail.com 