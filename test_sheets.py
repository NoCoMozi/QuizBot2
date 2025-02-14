from sheets_helper import SheetsHelper
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
import json

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_sheets_integration():
    try:
        # Load environment variables
        load_dotenv()
        sheets = SheetsHelper()
        
        # Load questions to create test data
        with open('questions.json', 'r', encoding='utf-8') as f:
            questions = json.load(f)['quiz']
        
        # Create complete test data
        test_data = {
            'answers': {
                'age': '26-35',
                'source': 'Social Media',
                'gov_priority': ['Healthcare should be a right', 'Keep religion out of government'],
                'beliefs': ['Healthcare Rights', 'Free Speech', 'Environmental Issues'],
                'region': 'Northeast',
                'state': 'New York',
                'weekly_hours': '10-20',
                'strike_support': 'Yes',
                'activist_org': 'Yes',
                'encrypted_communication': 'Yes',
                'confidentiality': 'Yes',
                'enforcement_affiliation': 'No',
                'reporting_role': 'No',
                'mission_alignment': 'Strongly agree',
                'leadership': 'Yes, I\'m ready to lead',
                'social_media_platforms': ['3. BlueSky', '4. Instagram', '6. TikTok']
            }
        }
        
        # Format data for sheet
        formatted_answers = []
        for question in questions:
            answer = test_data['answers'].get(question['id'], '')
            if isinstance(answer, list):
                answer = ', '.join(answer)
            formatted_answers.append(str(answer))
        
        # Add timestamp
        formatted_answers.append(datetime.now().isoformat())
        
        # Get current headers to show what we're sending
        result = sheets.service.spreadsheets().values().get(
            spreadsheetId=sheets.spreadsheet_id,
            range=f"{sheets.sheet_name}!A1:Z1"
        ).execute()
        
        if 'values' in result:
            headers = result['values'][0]
            logger.info("\nSending the following data:")
            for header, value in zip(headers, formatted_answers):
                logger.info(f"{header}: {value}")
        
        # Send to sheet
        result = sheets.append_row(formatted_answers)
        logger.info(f"\nRow added successfully! Details:")
        logger.info(f"Updated {result.get('updates', {}).get('updatedRows', 0)} rows")
        logger.info(f"Updated {result.get('updates', {}).get('updatedColumns', 0)} columns")
        logger.info(f"Updated {result.get('updates', {}).get('updatedCells', 0)} cells")
        
        return True
            
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    test_sheets_integration()
