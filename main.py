import os
import logging
import json
import csv
from datetime import datetime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler,
    Filters,
    CallbackContext
)
from dotenv import load_dotenv
from sheets_helper import SheetsHelper

# Load environment variables
load_dotenv()

# Enable logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Set Telegram API logger to WARNING to avoid exposing token
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.bot').setLevel(logging.WARNING)
logging.getLogger('telegram.ext.updater').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class FormBot:
    def __init__(self):
        self.questions = self.load_questions()
        self.state_links = self.load_state_links()
        self.leadership_links = {
            'general': 'https://t.me/c/2399831251/13132',
            'veterans_educators_nurses': 'https://t.me/c/2399831251/289114',
            'marginalized_underrepresented': 'https://t.me/c/2399831251/231957'
        }
        self.social_media_links = {
            "BlueSky": "https://bsky.app/profile/voicesignited.bsky.social",
            "TikTok": "https://www.tiktok.com/@voices_united",
            "Substack": "https://voicesignited.substack.com/",
            "YouTube": "https://www.youtube.com/@VoicesIgnited",
            "Instagram": "https://www.instagram.com/voicesignited",
            "Linktree": "https://linktr.ee/voices_ignited",
            "Keybase": "keybase://team-page/quiz_team"
        }
        
    def load_questions(self):
        """Load and validate questions from JSON file."""
        try:
            with open('questions.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Validate question format
                for q in data['quiz']:
                    if 'question' not in q:
                        logger.error(f"Invalid question format: {q}")
                return data['quiz']
        except Exception as e:
            logger.error(f"Error loading questions: {str(e)}")
            return []

    def load_state_links(self):
        """Load state links from CSV file."""
        state_links = {}
        try:
            with open('forum_topics_with_links.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert state name to match the format in questions.json
                    state_name = row['title'].strip().title()
                    if state_name in [
                        "Alabama", "Alaska", "Arizona", "Arkansas", "California",
                        "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
                        "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
                        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
                        "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
                        "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
                        "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
                        "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
                        "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
                        "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
                    ]:
                        state_links[state_name] = row['link']
        except Exception as e:
            logger.error(f"Error loading state links: {str(e)}")
        return state_links

    @staticmethod
    def get_user_data(context: CallbackContext):
        """Initialize or get user data with proper structure."""
        if 'form_data' not in context.user_data:
            context.user_data['form_data'] = {
                'current_question': 0,
                'answers': {},
                'start_time': datetime.now().isoformat()
            }
        return context.user_data['form_data']

    def start(self, update: Update, context: CallbackContext):
        """Start the conversation and send first question."""
        if not self.questions:
            update.message.reply_text("Sorry, there was an error loading the questions. Please try again later.")
            return

        # Reset user data
        context.user_data['form_data'] = {
            'current_question': 0,
            'answers': {},
            'start_time': datetime.now().isoformat()
        }

        # Send welcome message and first question
        welcome_text = (
            "Hello and welcome to Voices Ignited! \n\n"
            "We are a movement fighting for a government that truly serves its people, not corporations.\n"
            "This short quiz will help us understand your values and how you'd like to contribute.\n"
            "Let's stand together for justice, equality, and real change—let's get started! "
        )
        update.message.reply_text(welcome_text)
        self.send_question(update, context)

    def send_question(self, update: Update, context: CallbackContext):
        """Send the current question to the user."""
        user_data = self.get_user_data(context)
        current_idx = user_data['current_question']
        
        if current_idx >= len(self.questions):
            self.finish_form(update, context)
            return

        question = self.questions[current_idx]
        question_text = f"{current_idx + 1}. {question['question']}"
        
        # Add description if present
        if 'description' in question:
            question_text += f"\n\n{question['description']}"

        if question.get('type') in ['multiple_choice', 'multiple_select'] and 'options' in question:
            # For multiple choice questions, create inline keyboard
            keyboard = []
            for option in question['options']:
                keyboard.append([InlineKeyboardButton(option, callback_data=option)])
                
            # For multiple select, add a "Done" button
            if question.get('type') == 'multiple_select':
                # Initialize selected options in user data if not present
                if 'selected_options' not in user_data:
                    user_data['selected_options'] = []
                keyboard.append([InlineKeyboardButton("✅ Done", callback_data="DONE_SELECTING")])
                # Add note about multiple selection
                question_text += "\n\n(You can select multiple options. Click '✅ Done' when finished.)"
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query'):
                update.callback_query.message.edit_text(
                    text=question_text,
                    reply_markup=reply_markup
                )
            else:
                update.message.reply_text(
                    text=question_text,
                    reply_markup=reply_markup
                )
        elif question.get('type') == 'yes_no':
            # For yes/no questions, create Yes/No buttons
            keyboard = [[
                InlineKeyboardButton("Yes", callback_data="Yes"),
                InlineKeyboardButton("No", callback_data="No")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query'):
                update.callback_query.message.edit_text(
                    text=question_text,
                    reply_markup=reply_markup
                )
            else:
                update.message.reply_text(
                    text=question_text,
                    reply_markup=reply_markup
                )
        else:
            # For text/number questions, just send the question
            if hasattr(update, 'callback_query'):
                update.callback_query.message.edit_text(
                    text=question_text
                )
            else:
                update.message.reply_text(
                    text=question_text
                )

    def handle_response(self, update: Update, context: CallbackContext):
        """Handle text responses."""
        user_data = self.get_user_data(context)
        current_idx = user_data['current_question']
        
        if current_idx >= len(self.questions):
            update.message.reply_text("You've already completed the form!")
            return

        # Save the answer
        user_data['answers'][str(current_idx)] = update.message.text
        user_data['current_question'] += 1

        # Send next question
        self.send_question(update, context)

    def handle_callback(self, update: Update, context: CallbackContext):
        """Handle button callbacks."""
        query = update.callback_query
        user_data = self.get_user_data(context)
        
        try:
            current_idx = user_data['current_question']
            current_question = self.questions[current_idx]
            
            # Handle multiple select questions
            if current_question.get('type') == 'multiple_select':
                if query.data == "DONE_SELECTING":
                    if not user_data.get('selected_options'):
                        # If no options selected, remind user to select at least one
                        query.answer("Please select at least one option")
                        return
                    
                    # Join selected options with comma and save
                    answer = ", ".join(user_data['selected_options'])
                    # Clear selected options for next multiple select question
                    user_data['selected_options'] = []
                else:
                    # Toggle selection
                    if 'selected_options' not in user_data:
                        user_data['selected_options'] = []
                    
                    if query.data in user_data['selected_options']:
                        user_data['selected_options'].remove(query.data)
                        query.answer(f"Removed: {query.data}")
                    else:
                        user_data['selected_options'].append(query.data)
                        query.answer(f"Added: {query.data}")
                    
                    # Update question text to show selected options
                    question_text = f"{current_idx + 1}. {current_question['question']}\n\nSelected: {', '.join(user_data['selected_options'])}"
                    query.message.edit_text(
                        text=question_text + "\n\n(You can select multiple options. Click '✅ Done' when finished.)",
                        reply_markup=query.message.reply_markup
                    )
                    return
            
            # For regular multiple choice or when DONE_SELECTING is clicked
            if query.data != "DONE_SELECTING":  # Skip processing if it's just a selection
                answer = query.data
            
            # Process the answer
            self.process_answer(update, context, answer)
            
        finally:
            # Always clear the processing flag
            if 'processing_callback' in context.user_data:
                del context.user_data['processing_callback']

    def process_answer(self, update: Update, context: CallbackContext, answer: str):
        """Process the user's answer and move to next question."""
        user_data = self.get_user_data(context)
        current_idx = user_data['current_question']
        current_question = self.questions[current_idx]
        
        # Store the answer
        user_data['answers'][current_question['id']] = answer
        
        # Check age if this was the age question
        if current_question['id'] == 'age':
            try:
                age = int(answer)
                if age < 18:
                    update.callback_query.message.reply_text(
                        "We apologize, but you must be 18 or older to participate in Voices Ignited. "
                        "Thank you for your interest!"
                    )
                    return
            except ValueError:
                # If age is not a valid number, let's skip the check
                pass
        
        # Move to next question
        user_data['current_question'] += 1
        self.send_question(update, context)

    def finish_form(self, update: Update, context: CallbackContext):
        """Handle form completion."""
        user_data = self.get_user_data(context)
        
        # Get the user's state and leadership preference from their answers
        user_state = user_data['answers'].get('location_state')
        leadership_interest = user_data['answers'].get('leadership')
        selected_platforms = user_data['answers'].get('social_media_platforms', '').split(', ')
        
        # Prepare completion message
        completion_text = (
            "Thank you for completing the Voices Ignited questionnaire! "
            "Your responses will help us better understand how to work together for change."
        )
        
        # Add state-specific link if available
        if user_state and user_state in self.state_links:
            completion_text += f"\n\nJoin your local state group here: {self.state_links[user_state]}"
            
            # Add general channels that everyone should join
            general_channels = [
                ("Mental Health Check In", "https://t.me/c/2399831251/227321"),
                ("Public Announcements", "https://t.me/c/2399831251/465"),
                ("Official Media & Information", "https://t.me/c/2399831251/202409"),
                ("Open Discussion", "https://t.me/c/2399831251/8684")
            ]
            
            completion_text += "\n\nHere are some important general channels you should join:"
            for channel_name, channel_link in general_channels:
                completion_text += f"\n• {channel_name}: {channel_link}"

        # Add leadership application links if user expressed interest
        if leadership_interest in ["Yes, I'm ready to lead", "Maybe, I'd like to learn first"]:
            completion_text += "\n\nSince you expressed interest in leadership, here are our leadership application channels:"
            completion_text += f"\n• General Leadership Applications: {self.leadership_links['general']}"
            completion_text += f"\n• Veterans, Educators & Nurses Leadership: {self.leadership_links['veterans_educators_nurses']}"
            completion_text += f"\n• Marginalized/Underrepresented Community Leadership: {self.leadership_links['marginalized_underrepresented']}"
            completion_text += "\n\nPlease apply through the channel that best fits your background and experience."

        # Add social media follow links
        completion_text += "\n\nPlease follow us on our social media channels:"
        
        # Map selected platforms to our actual social media links
        platform_mapping = {
            "1. Twitter/X": None,  # No Twitter link provided
            "2. Facebook": None,  # No Facebook link provided
            "3. BlueSky": self.social_media_links["BlueSky"],
            "4. Instagram": self.social_media_links["Instagram"],
            "5. Reddit": None,  # No Reddit link provided
            "6. TikTok": self.social_media_links["TikTok"],
            "7. LinkedIn": None,  # No LinkedIn link provided
            "8. Mastodon": None  # No Mastodon link provided
        }
        
        # Add all available social media links
        completion_text += f"\n• BlueSky: {self.social_media_links['BlueSky']}"
        completion_text += f"\n• TikTok: {self.social_media_links['TikTok']}"
        completion_text += f"\n• Instagram: {self.social_media_links['Instagram']}"
        completion_text += f"\n• YouTube: {self.social_media_links['YouTube']}"
        completion_text += f"\n• Substack: {self.social_media_links['Substack']}"
        completion_text += f"\n• Keybase Team: {self.social_media_links['Keybase']}"
        completion_text += f"\n\nAll our social links: {self.social_media_links['Linktree']}"
        
        # Send the completion message
        if hasattr(update, 'callback_query'):
            update.callback_query.message.reply_text(completion_text, parse_mode=ParseMode.HTML)
        else:
            update.message.reply_text(completion_text, parse_mode=ParseMode.HTML)
            
        # Clear user data
        context.user_data.clear()

def main():
    """Start the bot."""
    # Get the token from environment variable
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("No token found! Make sure to set BOT_TOKEN in .env file")
        return

    # Create the bot
    try:
        bot = FormBot()
        updater = Updater(token)

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        # Add handlers
        dp.add_handler(CommandHandler('start', bot.start))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, bot.handle_response))
        dp.add_handler(CallbackQueryHandler(bot.handle_callback))

        # Start the bot
        logger.info("Starting bot...")
        updater.start_polling()

        # Run the bot until you send a signal to stop
        updater.idle()

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")

if __name__ == '__main__':
    main()
