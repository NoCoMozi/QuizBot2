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
            questions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'questions.json')
            with open(questions_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Validate question format
                if not isinstance(data, dict) or 'quiz' not in data or not isinstance(data['quiz'], list):
                    logger.error("Invalid questions.json format: must have a 'quiz' list")
                    raise ValueError("Invalid questions.json format")
                
                for q in data['quiz']:
                    if not isinstance(q, dict):
                        logger.error(f"Invalid question format - not a dict: {q}")
                        raise ValueError("Invalid question format")
                    
                    required_fields = ['id', 'question', 'type']
                    for field in required_fields:
                        if field not in q:
                            logger.error(f"Question missing required field '{field}': {q}")
                            raise ValueError(f"Question missing required field '{field}'")
                    
                    if q['type'] in ['multiple_choice', 'multiple_select'] and ('options' not in q or not q['options']):
                        logger.error(f"Multiple choice/select question missing options: {q}")
                        raise ValueError("Multiple choice/select question missing options")
                
                logger.info(f"Successfully loaded {len(data['quiz'])} questions")
                return data['quiz']
        except Exception as e:
            logger.error(f"Error loading questions: {str(e)}", exc_info=True)
            raise  # Re-raise the error to stop bot initialization
            
    def load_state_links(self):
        """Load state links from CSV file."""
        state_links = {}
        try:
            csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'forum_topics_with_links.csv')
            with open(csv_path, 'r', encoding='utf-8') as f:
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

    def get_user_data(self, context: CallbackContext):
        """Initialize or get user data with proper structure."""
        try:
            if 'form_data' not in context.user_data:
                context.user_data['form_data'] = {
                    'current_question': 0,
                    'answers': {},
                    'start_time': datetime.now().isoformat()
                }
            return context.user_data['form_data']
        except Exception as e:
            logger.error(f"Error in get_user_data: {str(e)}", exc_info=True)
            raise

    def start(self, update: Update, context: CallbackContext):
        """Start the conversation and send first question."""
        try:
            if not self.questions:
                logger.error("No questions loaded")
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
                "Let's stand together for justice, equality, and real change—let's get started!\n "
                "Please answer all questions to complete your profile."
            )
            update.message.reply_text(welcome_text)
            self.send_question(update, context)
        except Exception as e:
            logger.error(f"Error in start: {str(e)}", exc_info=True)
            update.message.reply_text("Sorry, something went wrong. Please try again later.")

    def send_question(self, update: Update, context: CallbackContext):
        """Send the current question to the user."""
        try:
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
                
                if update.callback_query:
                    update.callback_query.message.edit_text(
                        text=question_text,
                        reply_markup=reply_markup
                    )
                elif update.message:
                    update.message.reply_text(
                        text=question_text,
                        reply_markup=reply_markup
                    )
                else:
                    logger.error("No valid message object found in update")
                    raise ValueError("No valid message object found in update")
            else:
                # For text input questions
                if update.callback_query:
                    update.callback_query.message.edit_text(question_text)
                elif update.message:
                    update.message.reply_text(question_text)
                else:
                    logger.error("No valid message object found in update")
                    raise ValueError("No valid message object found in update")
                    
        except Exception as e:
            logger.error(f"Error in send_question: {str(e)}", exc_info=True)
            try:
                if update.callback_query:
                    update.callback_query.message.reply_text("Sorry, something went wrong. Please try /start again.")
                elif update.message:
                    update.message.reply_text("Sorry, something went wrong. Please try /start again.")
            except Exception as inner_e:
                logger.error(f"Error sending error message: {str(inner_e)}", exc_info=True)

    def handle_response(self, update: Update, context: CallbackContext):
        """Handle text responses."""
        user_data = self.get_user_data(context)
        current_idx = user_data['current_question']
        current_question = self.questions[current_idx]
        
        if current_idx >= len(self.questions):
            update.message.reply_text("You've already completed the form!")
            return

        # Handle number type questions
        if current_question['type'] == 'number':
            try:
                number = int(update.message.text)
                if current_question['id'] == 'age':
                    if number < 13 or number > 120:
                        update.message.reply_text("Please enter a valid age between 13 and 120.")
                        return
                    if number < 18:
                        update.message.reply_text(
                            "We apologize, but you must be 18 or older to participate in Voices Ignited. "
                            "Thank you for your interest!"
                        )
                        return
            except ValueError:
                update.message.reply_text("Please enter a valid number.")
                return

        # Save the answer and move to next question
        user_data['answers'][current_question['id']] = update.message.text
        user_data['current_question'] += 1
        self.send_question(update, context)

    def handle_callback(self, update: Update, context: CallbackContext):
        """Handle button callbacks."""
        try:
            query = update.callback_query
            user_data = self.get_user_data(context)
            current_idx = user_data['current_question']
            current_question = self.questions[current_idx]
            
            # For multiple choice questions, process immediately
            if query.data != "DONE_SELECTING":
                user_data['answers'][current_question['id']] = query.data
                user_data['current_question'] += 1
                query.answer()  # Acknowledge the button press
                self.send_question(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_callback: {str(e)}", exc_info=True)
            if update.callback_query:
                update.callback_query.message.reply_text("Sorry, something went wrong. Please try /start again.")

    def process_answer(self, update: Update, context: CallbackContext, answer: str):
        """Process the user's answer and move to next question."""
        user_data = self.get_user_data(context)
        current_idx = user_data['current_question']
        current_question = self.questions[current_idx]
        
        # Save the answer
        user_data['answers'][current_question['id']] = answer
        
        # Move to next question
        user_data['current_question'] += 1
        
        # Check if we're done with all questions
        if user_data['current_question'] >= len(self.questions):
            self.finish_form(update, context)
            return
            
        # Send next question
        self.send_question(update, context)

    def finish_form(self, update: Update, context: CallbackContext):
        """Handle form completion."""
        user_data = self.get_user_data(context)
        
        # Get the user's state and leadership preference from their answers
        user_state = user_data['answers'].get('state')
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
        if update.callback_query:
            update.callback_query.message.reply_text(completion_text, parse_mode=ParseMode.HTML)
        elif update.message:
            update.message.reply_text(completion_text, parse_mode=ParseMode.HTML)
            
        # Clear user data
        context.user_data.clear()

def main():
    """Run the bot."""
    try:
        # Enable more verbose logging
        logging.getLogger('telegram').setLevel(logging.DEBUG)
        logging.getLogger('telegram.ext').setLevel(logging.DEBUG)
        
        bot = FormBot()
        token = os.getenv('BOT_TOKEN')
        if not token:
            raise ValueError("No bot token found in environment")
            
        updater = Updater(token, use_context=True)
        bot.updater = updater
        
        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        # Add handlers
        dp.add_handler(CommandHandler('start', bot.start))
        dp.add_handler(CommandHandler('quiz', bot.start))  # Use the same handler for both commands
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, bot.handle_response))
        dp.add_handler(CallbackQueryHandler(bot.handle_callback))

        # Add error handler
        def error_handler(update: Update, context: CallbackContext):
            error = context.error
            logger.error(f"Error occurred: {error}", exc_info=True)
            try:
                if update and update.effective_message:
                    update.effective_message.reply_text("Sorry, something went wrong. Please try again later.")
                elif update and update.callback_query:
                    update.callback_query.message.reply_text("Sorry, something went wrong. Please try again later.")
            except Exception as e:
                logger.error(f"Error in error handler: {e}", exc_info=True)
        
        dp.add_error_handler(error_handler)
        
        # Start the bot
        logger.info("Starting bot with token ending in ...%s", token[-4:])
        updater.start_polling(
            timeout=30,
            read_latency=5,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        updater.idle()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
