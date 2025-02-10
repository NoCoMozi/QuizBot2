from sheets_helper import SheetsHelper
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

def main():
    """Test Google Sheets setup."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize helper
        helper = SheetsHelper()
        
        # Test current setup
        print("\nTesting current setup...")
        if helper.test_setup():
            print("✓ Current setup looks good!")
        else:
            print("✗ Current setup needs fixing")
            
            # Try to fix by recreating
            print("\nTrying to fix by recreating sheet...")
            helper.setup_sheet(force_recreate=True)
            
            # Test again
            print("\nTesting new setup...")
            if helper.test_setup():
                print("✓ Fixed! Sheet is now properly set up")
            else:
                print("✗ Still having issues. Please check the logs above")
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == '__main__':
    main()
