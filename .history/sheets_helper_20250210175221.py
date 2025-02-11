from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SheetsHelper:
    def __init__(self):
        """Initialize the Google Sheets helper."""
        self.SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
        if not self.SPREADSHEET_ID:
            raise ValueError("SPREADSHEET_ID not found in environment variables")
            
        self.SHEET_NAME = 'Sheet1'  # Changed to Sheet1 since it's the default sheet
        
        try:
            # Load credentials
            logger.debug("Loading service account credentials...")
            creds = service_account.Credentials.from_service_account_file(
                'service_account.json',
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            logger.info("Successfully loaded credentials")
            
            # Create service
            logger.debug("Initializing Google Sheets service...")
            self.service = build('sheets', 'v4', credentials=creds)
            self.sheet = self.service.spreadsheets()
            logger.info("Successfully initialized Google Sheets service")
            
        except Exception as e:
            logger.error(f"Failed to initialize sheets helper: {str(e)}")
            raise
            
    def setup_sheet(self, force_recreate=False):
        """Create Responses sheet if it doesn't exist and set up headers."""
        try:
            # Get spreadsheet info
            spreadsheet = self.sheet.get(spreadsheetId=self.SPREADSHEET_ID).execute()
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            # Delete sheet if force recreate
            if force_recreate and self.SHEET_NAME in sheet_names:
                logger.info(f"Force recreating sheet: {self.SHEET_NAME}")
                sheet_id = None
                for sheet in sheets:
                    if sheet['properties']['title'] == self.SHEET_NAME:
                        sheet_id = sheet['properties']['sheetId']
                        break
                        
                if sheet_id:
                    requests = [{
                        'deleteSheet': {
                            'sheetId': sheet_id
                        }
                    }]
                    self.sheet.batchUpdate(
                        spreadsheetId=self.SPREADSHEET_ID,
                        body={'requests': requests}
                    ).execute()
                    sheet_names.remove(self.SHEET_NAME)
            
            # Create sheet if it doesn't exist
            if self.SHEET_NAME not in sheet_names:
                logger.info(f"Creating sheet: {self.SHEET_NAME}")
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': self.SHEET_NAME,
                            'gridProperties': {
                                'frozenRowCount': 1  # Freeze header row
                            }
                        }
                    }
                }]
                self.sheet.batchUpdate(
                    spreadsheetId=self.SPREADSHEET_ID,
                    body={'requests': requests}
                ).execute()
                
                # Add headers
                with open('questions.json', 'r') as f:
                    questions = json.load(f)['quiz']
                    
                headers = []
                for i, q in enumerate(questions):
                    headers.append(f"Q{i+1}: {q['question']}")
                headers.append("Timestamp")
                
                # Update headers
                range_name = f'{self.SHEET_NAME}!A1'
                body = {
                    'values': [headers]
                }
                self.sheet.values().update(
                    spreadsheetId=self.SPREADSHEET_ID,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                # Format headers
                sheet_id = None
                spreadsheet = self.sheet.get(spreadsheetId=self.SPREADSHEET_ID).execute()
                for sheet in spreadsheet['sheets']:
                    if sheet['properties']['title'] == self.SHEET_NAME:
                        sheet_id = sheet['properties']['sheetId']
                        break
                        
                if sheet_id:
                    requests = [{
                        'repeatCell': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 1
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {
                                        'red': 0.8,
                                        'green': 0.8,
                                        'blue': 0.8
                                    },
                                    'textFormat': {
                                        'bold': True
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                        }
                    }]
                    self.sheet.batchUpdate(
                        spreadsheetId=self.SPREADSHEET_ID,
                        body={'requests': requests}
                    ).execute()
                    
                logger.info("Headers added and formatted successfully")
                
            return True
                
        except Exception as e:
            logger.error(f"Error setting up sheet: {str(e)}")
            raise
            
    def test_setup(self):
        """Test the sheet setup and return status."""
        try:
            # 1. Check spreadsheet access
            spreadsheet = self.sheet.get(spreadsheetId=self.SPREADSHEET_ID).execute()
            logger.info(f"✓ Successfully accessed spreadsheet: {spreadsheet['properties']['title']}")
            
            # 2. Check Responses sheet
            sheets = spreadsheet.get('sheets', [])
            sheet_names = [s['properties']['title'] for s in sheets]
            
            if self.SHEET_NAME not in sheet_names:
                logger.error(f"✗ '{self.SHEET_NAME}' sheet not found")
                return False
            logger.info(f"✓ Found '{self.SHEET_NAME}' sheet")
            
            # 3. Check headers
            result = self.sheet.values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=f"{self.SHEET_NAME}!A1:Z1"
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
        
    def append_row(self, row_data):
        """Append a row of data to the spreadsheet."""
        try:
            logger.info(f"Appending row to sheet {self.SHEET_NAME}")
            logger.debug(f"Row data: {row_data}")
            
            range_name = f'{self.SHEET_NAME}!A:Z'
            body = {
                'values': [row_data]
            }
            
            logger.debug(f"Making API call to append row...")
            result = self.sheet.values().append(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Successfully appended row. API response: {result}")
            return True
            
        except Exception as e:
            logger.error(f"Error appending row: {str(e)}")
            logger.error(f"Spreadsheet ID: {self.SPREADSHEET_ID}")
            logger.error(f"Sheet name: {self.SHEET_NAME}")
            return False
