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
        self.sheet_name = 'Form Responses'
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
        """Create Form Responses sheet if it doesn't exist and set up headers."""
        try:
            # Get spreadsheet info
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            # Delete sheet if force recreate
            if force_recreate and self.sheet_name in sheet_names:
                logger.info(f"Force recreating sheet: {self.sheet_name}")
                sheet_id = None
                for sheet in sheets:
                    if sheet['properties']['title'] == self.sheet_name:
                        sheet_id = sheet['properties']['sheetId']
                        break
                        
                if sheet_id:
                    requests = [{
                        'deleteSheet': {
                            'sheetId': sheet_id
                        }
                    }]
                    self.service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body={'requests': requests}
                    ).execute()
                    sheet_names.remove(self.sheet_name)
            
            # Create sheet if it doesn't exist
            if self.sheet_name not in sheet_names:
                logger.info(f"Creating sheet: {self.sheet_name}")
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': self.sheet_name,
                            'gridProperties': {
                                'frozenRowCount': 1  # Freeze header row
                            }
                        }
                    }
                }]
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()
                
                # Add headers
                with open('questions.json', 'r') as f:
                    questions = json.load(f)['quiz']
                    
                headers = []
                for q in questions:
                    headers.append(q['question'])
                headers.append("Timestamp")
                
                # Update headers
                range_name = f'{self.sheet_name}!A1'
                body = {
                    'values': [headers]
                }
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                logger.info("Headers added successfully")
                
            return True
                
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
                
            if len(headers) != len(questions) + 1:  # +1 for timestamp
                logger.error(f"✗ Header count mismatch. Expected {len(questions) + 1}, got {len(headers)}")
                return False
                
            logger.info("✓ Header count matches questions")
            return True
            
        except Exception as e:
            logger.error(f"Error testing setup: {str(e)}")
            return False

    def append_row(self, values):
        """Append a row to the Google Sheet."""
        try:
            body = {
                'values': [values]
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A1',  # This will append to the first empty row
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            logger.info(f"Appended row to Google Sheet: {result}")
            return result
        except Exception as e:
            logger.error(f"Error appending to Google Sheet: {str(e)}")
            raise
