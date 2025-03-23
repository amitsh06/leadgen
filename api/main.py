import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, validator

# Import scraper and utilities
import sys
from pathlib import Path
# Add the parent directory to sys.path to import modules
sys.path.append(str(Path(__file__).parent.parent))

from scraper.maps_scraper import GoogleMapsScraper, save_results_to_file
from utils.email_finder import EmailFinder
from utils.email_generator import EmailTemplateGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create app
app = FastAPI(
    title="LeadHarvest API",
    description="API for the LeadHarvest lead generation tool",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create data directory if it doesn't exist
data_dir = Path(__file__).parent.parent / "data"
data_dir.mkdir(exist_ok=True)

# Initialize utilities
email_finder = EmailFinder()
email_generator = EmailTemplateGenerator()

# Define models
class ScraperRequest(BaseModel):
    query: str = Field(..., description="Type of business to search for")
    location: str = Field(..., description="Location to search in")
    max_results: int = Field(20, description="Maximum number of results to return", ge=1, le=100)
    include_emails: bool = Field(True, description="Whether to find email addresses")
    include_email_templates: bool = Field(True, description="Whether to generate email templates")
    
    # Updated for Pydantic V2 compatibility
    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "restaurants",
                "location": "New York, NY",
                "max_results": 20,
                "include_emails": True,
                "include_email_templates": True
            }
        }
    }

class ScraperResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    message: str
    completed_at: Optional[str] = None
    results_file: Optional[str] = None

# Store for background jobs
jobs_store = {}

# Background task for scraping
def scrape_task(
    job_id: str, 
    query: str, 
    location: str, 
    max_results: int,
    include_emails: bool,
    include_email_templates: bool
):
    """
    Background task to scrape Google Maps data.
    
    Args:
        job_id (str): Unique job identifier.
        query (str): Type of business to search for.
        location (str): Location to search in.
        max_results (int): Maximum number of results to return.
        include_emails (bool): Whether to find email addresses.
        include_email_templates (bool): Whether to generate email templates.
    """
    try:
        # Update job status
        jobs_store[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0.0,
            "message": "Starting scraper...",
            "completed_at": None,
            "results_file": None
        }
        
        try:
            # Check if Chrome is installed
            import subprocess
            try:
                # On Windows, check for Chrome installation
                if os.name == 'nt':
                    chrome_path = None
                    for path in [
                        os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe'),
                        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                    ]:
                        if os.path.exists(path):
                            chrome_path = path
                            break
                    
                    if not chrome_path:
                        raise Exception("Chrome browser not found. Please install Google Chrome to use this application.")
                    
                    logger.info(f"Found Chrome at: {chrome_path}")
            except Exception as e:
                logger.error(f"Error checking Chrome installation: {str(e)}")
                raise Exception("Failed to detect Chrome browser. Please ensure Google Chrome is properly installed.")
                
            # Initialize scraper with headless=False to see what's happening
            with GoogleMapsScraper(headless=False) as scraper:
                # Scrape businesses
                jobs_store[job_id]["message"] = "Scraping business data..."
                jobs_store[job_id]["progress"] = 0.1
                
                results = scraper.scrape_businesses(query, location, max_results)
                
                # Update progress
                jobs_store[job_id]["progress"] = 0.4
                jobs_store[job_id]["message"] = f"Found {len(results)} businesses."
                
                # Find emails if requested
                if include_emails and results:
                    jobs_store[job_id]["message"] = "Finding email addresses..."
                    jobs_store[job_id]["progress"] = 0.5
                    
                    for i, business_data in enumerate(results):
                        # Update progress
                        progress = 0.5 + (0.3 * (i / len(results)))
                        jobs_store[job_id]["progress"] = progress
                        jobs_store[job_id]["message"] = f"Finding emails for business {i+1}/{len(results)}: {business_data.get('name', 'Unknown')}"
                        
                        # Find emails
                        if business_data.get('website'):
                            results[i] = email_finder.enrich_business_data_with_emails(business_data)
                            # Update status with whether emails were found
                            if results[i].get('emails'):
                                jobs_store[job_id]["message"] = f"Found {len(results[i].get('emails', []))} emails for {business_data.get('name', 'Unknown')}"
                            else:
                                jobs_store[job_id]["message"] = f"No emails found for {business_data.get('name', 'Unknown')}"
                        else:
                            jobs_store[job_id]["message"] = f"No website found for {business_data.get('name', 'Unknown')}"
                
                # Generate email templates if requested
                if include_email_templates and results:
                    jobs_store[job_id]["message"] = "Generating email templates..."
                    jobs_store[job_id]["progress"] = 0.8
                    
                    for i, business_data in enumerate(results):
                        # Update progress
                        progress = 0.8 + (0.15 * (i / len(results)))
                        jobs_store[job_id]["progress"] = progress
                        jobs_store[job_id]["message"] = f"Generating email template for {business_data.get('name', 'Unknown')}"
                        
                        # Generate template
                        results[i] = email_generator.enrich_business_data_with_email_template(business_data)
                
                # Save results to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{query}_{location}_{timestamp}"
                filepath = data_dir / filename
                
                # Save in both formats
                save_results_to_file(results, str(filepath), "json")
                save_results_to_file(results, str(filepath), "csv")
                
                # Update job status
                jobs_store[job_id]["status"] = "completed"
                jobs_store[job_id]["progress"] = 1.0
                jobs_store[job_id]["message"] = f"Completed scraping {len(results)} businesses."
                jobs_store[job_id]["completed_at"] = datetime.now().isoformat()
                jobs_store[job_id]["results_file"] = filename
                
        except Exception as task_error:
            logger.error(f"Error in scraping task execution: {str(task_error)}")
            # Provide a more user-friendly error message
            error_message = str(task_error)
            
            # Check for specific errors and provide better messages
            if "executable needs to be in PATH" in error_message or "ChromeDriver" in error_message:
                error_message = "Chrome browser or ChromeDriver issue. Please ensure Google Chrome is installed and up to date."
            elif "not a valid Win32 application" in error_message:
                error_message = "ChromeDriver compatibility issue. Please ensure you have the latest version of Google Chrome installed."
            
            jobs_store[job_id]["status"] = "failed"
            jobs_store[job_id]["progress"] = None
            jobs_store[job_id]["message"] = f"Error: {error_message}"
            jobs_store[job_id]["completed_at"] = datetime.now().isoformat()
            
    except Exception as e:
        logger.error(f"Error in scrape task: {str(e)}")
        
        # Update job status
        jobs_store[job_id] = {
            "job_id": job_id,
            "status": "failed",
            "progress": None,
            "message": f"Error: {str(e)}",
            "completed_at": datetime.now().isoformat(),
            "results_file": None
        }

# Routes
@app.get("/")
async def root():
    """Get API information."""
    return {"message": "LeadHarvest API", "version": "1.0.0"}

@app.post("/scrape", response_model=ScraperResponse)
async def start_scraper(request: ScraperRequest, background_tasks: BackgroundTasks):
    """Start a new scraping job."""
    # Generate a job ID
    job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Start the background task
    background_tasks.add_task(
        scrape_task, 
        job_id, 
        request.query, 
        request.location, 
        request.max_results,
        request.include_emails,
        request.include_email_templates
    )
    
    # Initialize job status
    jobs_store[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "message": "Job queued, waiting to start...",
        "completed_at": None,
        "results_file": None
    }
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Scraping job started successfully"
    }

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a scraping job."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs_store[job_id]

@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    return list(jobs_store.values())

@app.get("/jobs/{job_id}/download/{file_format}")
async def download_job_results(job_id: str, file_format: str):
    """
    Download job results in specified format.
    
    Args:
        job_id (str): Job ID.
        file_format (str): File format (json, csv, or excel).
        
    Returns:
        FileResponse: File download response.
    """
    # Validate file format
    if file_format.lower() not in ["json", "csv", "excel"]:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_format}")
    
    # Check if job exists
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Check if job has completed
    if jobs_store[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job {job_id} has not completed")
    
    # Get results filename from job store
    filename_base = jobs_store[job_id].get("results_file")
    
    if not filename_base:
        raise HTTPException(status_code=404, detail=f"No results found for job {job_id}")
    
    # Construct full filepath
    filepath_base = data_dir / filename_base
    
    # Load the data from JSON (our base storage format)
    json_path = f"{filepath_base}.json"
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Results file for job {job_id} not found")
    
    # Create the requested format if needed
    if file_format.lower() == "json":
        file_path = f"{filepath_base}.json"
    else:
        # Generate the file in the requested format
        file_path = save_results_to_file(results, str(filepath_base), file_format.lower())
        
        if not file_path:
            raise HTTPException(status_code=500, detail=f"Failed to generate {file_format} file")
    
    # Return the file as a download
    return FileResponse(
        path=file_path,
        filename=f"{filename_base}.{file_format.lower()}",
        media_type="application/octet-stream"
    )

# Mount static files for the frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="app")

# Run the server
if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True) 

def save_results_to_file(results: List[Dict], filepath: str, file_format: str = "json"):
    """
    Save scraping results to a file.
    
    Args:
        results (List[Dict]): List of business data dictionaries.
        filepath (str): Base filepath (without extension).
        file_format (str): File format ("json", "csv", or "excel").
    
    Returns:
        str: Path to the saved file.
    """
    try:
        filepath_with_ext = ""
        
        if file_format.lower() == "json":
            filepath_with_ext = f"{filepath}.json"
            with open(filepath_with_ext, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
        elif file_format.lower() == "csv":
            import pandas as pd
            
            # Flatten nested dictionaries (hours, coordinates, emails)
            flattened_results = []
            for business in results:
                flat_business = flatten_business_data(business)
                flattened_results.append(flat_business)
            
            df = pd.DataFrame(flattened_results)
            filepath_with_ext = f"{filepath}.csv"
            df.to_csv(filepath_with_ext, index=False, encoding="utf-8")
            
        elif file_format.lower() == "excel":
            import pandas as pd
            
            # Flatten nested dictionaries (hours, coordinates, emails)
            flattened_results = []
            for business in results:
                flat_business = flatten_business_data(business)
                flattened_results.append(flat_business)
            
            df = pd.DataFrame(flattened_results)
            filepath_with_ext = f"{filepath}.xlsx"
            
            # Create a styled Excel file
            with pd.ExcelWriter(filepath_with_ext, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Business Leads', index=False)
                workbook = writer.book
                worksheet = writer.sheets['Business Leads']
                
                # Add formats
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Apply header format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
                # Set column widths
                for i, col in enumerate(df.columns):
                    column_width = max(df[col].astype(str).map(len).max(), len(col) + 2)
                    worksheet.set_column(i, i, column_width)
                
                # Add autofilter
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        else:
            logger.error(f"Unsupported file format: {file_format}")
            return None
            
        logger.info(f"Results saved to {filepath_with_ext}")
        return filepath_with_ext
    
    except Exception as e:
        logger.error(f"Error saving results to {file_format} file: {str(e)}")
        return None

def flatten_business_data(business: Dict) -> Dict:
    """
    Flatten nested business data for export.
    
    Args:
        business (Dict): Business data with nested structures.
        
    Returns:
        Dict: Flattened business data.
    """
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
    
    # Handle emails
    if "emails" in flat_business and isinstance(flat_business["emails"], list):
        # Add first 5 emails as separate fields
        for i, email in enumerate(flat_business["emails"][:5]):
            flat_business[f"email_{i+1}"] = email
        
        # Keep a comma-separated list of all emails
        flat_business["all_emails"] = ", ".join(flat_business["emails"])
        del flat_business["emails"]
    
    # Handle email template (limit length for CSV/Excel)
    if "email_template" in flat_business and isinstance(flat_business["email_template"], str):
        if len(flat_business["email_template"]) > 1000:
            flat_business["email_template"] = flat_business["email_template"][:997] + "..."
    
    return flat_business 