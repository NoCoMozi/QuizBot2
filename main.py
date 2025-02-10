import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

from sheets_helper import SheetsHelper

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

class QuizBot:
    def __init__(self):
        """Initialize the bot and load quiz questions."""
        logger.info("Initializing QuizBot...")
        
        try:
            self.updater = Updater(BOT_TOKEN)
            self.dispatcher = self.updater.dispatcher
            logger.info("Bot updater and dispatcher initialized")
            
            # Initialize sheets helper
            logger.info("Initializing sheets helper...")
            self.sheets = SheetsHelper()
            logger.info("Sheets helper initialized")
            
            # Load questions
            logger.info("Loading questions...")
            with open('questions.json', 'r') as f:
                self.questions = json.load(f)['quiz']
            logger.info(f"Loaded {len(self.questions)} questions")
            
            # Add handlers
            logger.info("Adding command handlers...")
            self.dispatcher.add_handler(CommandHandler('start', self.start))
            self.dispatcher.add_handler(CommandHandler('quiz', self.quiz))
            self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_response))
            self.dispatcher.add_handler(CallbackQueryHandler(self.handle_button))
            
            # Add error handler
            self.dispatcher.add_error_handler(self.error_handler)
            logger.info("All handlers added successfully")
            
        except Exception as e:
            logger.error(f"Error initializing bot: {str(e)}", exc_info=True)
            raise
        
    def error_handler(self, update: Update, context: CallbackContext) -> None:
        """Log errors caused by updates."""
        logger.error(f"Update {update} caused error {context.error}")
        
    def start(self, update: Update, context: CallbackContext) -> None:
        """Start command."""
        logger.info("Received start command")
        update.message.reply_text("Welcome! Use /quiz to start the quiz.")

    def quiz(self, update: Update, context: CallbackContext) -> None:
        """Start the quiz."""
        logger.info("Received quiz command")
        context.user_data.clear()  # Clear all previous data
        context.user_data['quiz_data'] = {
            'current_question': 0,
            'answers': {}
        }
        self.send_question(update.message, context)

    def send_question(self, message, context: CallbackContext) -> None:
        """Send the next question."""
        try:
            logger.info("Sending next question...")
            quiz_data = context.user_data.get('quiz_data', {})
            q_index = quiz_data.get('current_question', 0)

            if q_index >= len(self.questions):
                return self.complete_quiz(message, context)

            question = self.questions[q_index]
            question_type = question.get('type', 'text')
            text = f"Q{q_index + 1}: {question['question']}"
            
            # Add type-specific instructions
            if question_type == 'text' and question.get('min_length'):
                text += f"\n\nPlease provide at least {question['min_length']} characters in your response."
            elif question_type == 'number':
                text += "\n\nPlease enter a number."
            elif question_type == 'text':
                text += "\n\nPlease type your answer."
            
            if question_type == 'multiple_choice' and 'options' in question:
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"{q_index}:{i}")] 
                           for i, opt in enumerate(question['options'])]
                message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            elif question_type == 'yes_no':
                keyboard = [[InlineKeyboardButton("Yes", callback_data=f"{q_index}:yes"),
                           InlineKeyboardButton("No", callback_data=f"{q_index}:no")]]
                message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                message.reply_text(text)
                
        except Exception as e:
            logger.error(f"Error sending question {q_index + 1}: {str(e)}")
            message.reply_text("Sorry, there was an error. Please try /quiz again.")

    def handle_button(self, update: Update, context: CallbackContext) -> None:
        """Handle button clicks for multiple choice questions."""
        logger.info("Received button click")
        query = update.callback_query
        
        try:
            q_index_str, response = query.data.split(':')
            q_index = int(q_index_str)
            
            quiz_data = context.user_data.get('quiz_data', {})
            current_q = quiz_data.get('current_question', 0)
            
            # Verify this is the current question
            if q_index != current_q:
                query.answer("Please answer the current question")
                return
                
            question = self.questions[q_index]
            question_type = question.get('type', 'text')
            
            # Get actual response text
            if question_type == 'multiple_choice' and 'options' in question:
                try:
                    user_response = question['options'][int(response)]
                except (ValueError, IndexError):
                    user_response = response
            elif question_type == 'yes_no':
                user_response = response.capitalize()
            else:
                user_response = response
                
            # Save response and move to next question
            quiz_data['answers'][str(q_index)] = user_response
            quiz_data['current_question'] = q_index + 1
            
            # Answer callback query
            query.answer()
            
            # Send next question
            self.send_question(query.message, context)
            
        except Exception as e:
            logger.error(f"Error handling button: {str(e)}")
            query.answer("Sorry, there was an error. Please try again.")

    def handle_response(self, update: Update, context: CallbackContext) -> None:
        """Handle text responses."""
        logger.info("Received text response")
        if not update.message:
            return
            
        quiz_data = context.user_data.get('quiz_data', {})
        if not quiz_data:
            update.message.reply_text("Please start the quiz with /quiz first!")
            return
            
        q_index = quiz_data.get('current_question', 0)
        if q_index >= len(self.questions):
            return

        question = self.questions[q_index]
        question_type = question.get('type', 'text')
        
        # Ignore text responses for button questions
        if question_type in ['multiple_choice', 'yes_no']:
            return
            
        user_response = update.message.text
        message = update.message
            
        # Only validate number type for number questions
        if question_type == 'number':
            try:
                user_response = int(user_response)
                # Add basic age validation
                if user_response < 0 or user_response > 120:
                    message.reply_text("Please enter a valid age between 0 and 120.")
                    return
            except ValueError:
                message.reply_text("Please enter a valid number.")
                return
                
        # Only validate minimum length for text questions
        elif question_type == 'text' and question.get('min_length'):
            min_length = question['min_length']
            if len(user_response) < min_length:
                message.reply_text(
                    f"Your response is too short. Please provide at least {min_length} characters.\n"
                    f"Current length: {len(user_response)} characters"
                )
                return
        
        # Save the response and move to next question
        quiz_data['answers'][str(q_index)] = user_response
        quiz_data['current_question'] = q_index + 1
        self.send_question(message, context)

    def complete_quiz(self, message, context: CallbackContext) -> None:
        """Save quiz responses and complete."""
        logger.info("Completing quiz...")
        try:
            quiz_data = context.user_data.get('quiz_data', {})
            answers = quiz_data.get('answers', {})
            
            if not answers:
                message.reply_text("No answers to save. Please start the quiz again with /quiz")
                return
                
            # Format answers for spreadsheet
            row = []
            for i in range(len(self.questions)):
                answer = answers.get(str(i), '')
                row.append(str(answer))
                
            # Add timestamp
            from datetime import datetime
            row.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            logger.info(f"Attempting to save row: {row}")
            
            # Try to create/setup sheet first
            try:
                self.sheets.setup_sheet()
                logger.info("Sheet setup successful")
            except Exception as e:
                logger.error(f"Sheet setup failed: {str(e)}")
                message.reply_text("There was an error setting up the response sheet. Please try again later.")
                return
                
            # Save to spreadsheet
            try:
                success = self.sheets.append_row(row)
                if success:
                    message.reply_text("Thank you for completing the quiz! Your responses have been saved. ")
                    logger.info("Successfully saved responses")
                else:
                    raise Exception("Failed to append row")
            except Exception as e:
                logger.error(f"Failed to save to spreadsheet: {str(e)}")
                message.reply_text("There was an error saving your responses. Please try again later.")
                
        except Exception as e:
            logger.error(f"Error completing quiz: {str(e)}")
            message.reply_text("There was an error completing the quiz. Please try again.")
        finally:
            # Clear quiz data
            if 'quiz_data' in context.user_data:
                del context.user_data['quiz_data']

def main():
    """Run the bot."""
    try:
        # Check for existing instances
        import psutil
        current_pid = os.getpid()
        python_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == 'python.exe' and proc.pid != current_pid:
                    python_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        if python_count > 0:
            logger.error("Another Python instance is running. Please close it first.")
            return
            
        bot = QuizBot()
        # Start the Bot
        logger.info("Starting bot...")
        bot.updater.start_polling()
        logger.info("Bot started successfully!")
        bot.updater.idle()
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)

if __name__ == '__main__':
    import os
    import psutil
    main()
