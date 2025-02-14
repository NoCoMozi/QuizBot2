import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging
import json

logger = logging.getLogger(__name__)

class SheetsHelper:
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        self.creds = None
        self.service = None
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = 'Intake'
        self.initialize_service()

    def initialize_service(self):
        """Initialize the Google Sheets service."""
        try:
            # Load service account credentials
            self.creds = service_account.Credentials.from_service_account_file(
                'freshshare-b561dbef2edd.json',
                scopes=self.SCOPES
            )
            
            self.service = build('sheets', 'v4', credentials=self.creds)
            logger.info("Google Sheets service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Google Sheets service: {str(e)}")
            raise

    def setup_sheet(self, force_recreate=False):
        """Set up the sheet with headers."""
        try:
            # Get current sheets to check if our sheet exists
            sheets = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_exists = any(sheet['properties']['title'] == self.sheet_name 
                             for sheet in sheets['sheets'])
            
            if not sheet_exists or force_recreate:
                if force_recreate and sheet_exists:
                    # Clear existing content
                    self.service.spreadsheets().values().clear(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{self.sheet_name}!A:Z"
                    ).execute()
                
                # Start with user info and timestamp
                headers = ['Username', 'First Name', 'Last Name', 'User ID', 'Timestamp']
                
                # Load questions to get all field names
                with open('questions.json', 'r', encoding='utf-8') as f:
                    questions = json.load(f)['quiz']
                    for q in questions:
                        headers.append(q['text'])
                
                # Update headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A1",
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                
                logger.info("Sheet headers set up successfully")
            
        except Exception as e:
            logger.error(f"Error setting up sheet: {str(e)}")
            raise
            
    def test_setup(self):
        """Test the sheet setup and return status."""
        try:
            # 1. Check spreadsheet access
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            logger.info(f"✓ Successfully accessed spreadsheet: {spreadsheet['properties']['title']}")
            
            # 2. Check Form Responses sheet
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            if self.sheet_name not in sheet_names:
                logger.error(f"✗ '{self.sheet_name}' sheet not found")
                return False
            logger.info(f"✓ Found '{self.sheet_name}' sheet")
            
            # 3. Check headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:Z1"
            ).execute()
            
            if not result.get('values'):
                logger.error("✗ No headers found")
                return False
                
            headers = result['values'][0]
            logger.info(f"✓ Found {len(headers)} headers")
            
            # 4. Compare with questions
            with open('questions.json', 'r') as f:
                questions = json.load(f)['quiz']
                
            if len(headers) != len(questions) + 5:  # +5 for timestamp, username, first name, last name, user ID
                logger.error(f"✗ Header count mismatch. Expected {len(questions) + 5}, got {len(headers)}")
                return False
                
            logger.info("✓ Header count matches questions")
            return True
            
        except Exception as e:
            logger.error(f"Error testing setup: {str(e)}")
            return False

    def validate_headers(self):
        """Validate that headers match questions."""
        try:
            # Get current headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!1:1"
            ).execute()
            
            if 'values' not in result:
                logger.error("✗ No headers found")
                return False
                
            headers = result['values'][0]
            
            # Load questions
            with open('questions.json', 'r') as f:
                questions = json.load(f)['quiz']
                
            if len(headers) != len(questions) + 5:  # +5 for timestamp, username, first name, last name, user ID
                logger.error(f"✗ Header count mismatch. Expected {len(questions) + 5}, got {len(headers)}")
                return False
                
            logger.info("✓ Header count matches questions")
            return True
            
        except Exception as e:
            logger.error(f"Error validating headers: {str(e)}")
            return False

    def append_row(self, row_data):
        """Append a row of data to the sheet."""
        try:
            # Get the range
            range_name = f"{self.sheet_name}!A:Z"
            
            # Get current values to check if headers exist and find last row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            # If sheet is empty, add headers
            if 'values' not in result:
                self.setup_sheet(force_recreate=True)
                next_row = 2
            else:
                next_row = len(result.get('values', [])) + 1
            
            # Prepare request to write to specific row
            body = {
                'values': [row_data]
            }
            
            # Make request using update to specific row
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A{next_row}",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"Row appended successfully at row {next_row}")
            
        except Exception as e:
            logger.error(f"Error appending row: {str(e)}")
            raise
