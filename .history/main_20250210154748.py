import os
import logging
import json
from datetime import datetime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from dotenv import load_dotenv
from sheets_helper import SheetsHelper

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Enable logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QuizBot:
    def __init__(self):
        """Initialize the bot and load quiz questions."""
        with open('questions.json', 'r') as f:
            self.questions = json.load(f)['quiz']
        
        self.sheets = SheetsHelper()

    def start(self, update: Update, context: CallbackContext) -> None:
        """Start command."""
        update.message.reply_text("Welcome! Use /quiz to start the quiz.")

    def quiz(self, update: Update, context: CallbackContext) -> None:
        """Start the quiz."""
        context.user_data['quiz_data'] = {'current_question': 0, 'answers': {}}
        self.send_question(update.message, context)

    def send_question(self, message, context: CallbackContext) -> None:
        """Send the next question."""
        quiz_data = context.user_data.get('quiz_data', {})
        q_index = quiz_data.get('current_question', 0)

        if q_index >= len(self.questions):
            return self.complete_quiz(message, context)

        question = self.questions[q_index]
        text = f"Q{q_index + 1}: {question['question']}"
        
        if 'options' in question:
            keyboard = [[InlineKeyboardButton(opt, callback_data=str(i))] for i, opt in enumerate(question['options'])]
            message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            message.reply_text(text + "\n\nPlease type your answer.")

    def handle_response(self, update: Update, context: CallbackContext) -> None:
        """Handle user responses."""
        quiz_data = context.user_data.get('quiz_data', {})
        q_index = quiz_data.get('current_question', 0)

        if q_index >= len(self.questions):
            return

        question = self.questions[q_index]
        user_response = update.message.text if question.get('options') is None else update.callback_query.data
        
        quiz_data['answers'][q_index] = user_response
        quiz_data['current_question'] += 1
        self.send_question(update.message, context)

    def complete_quiz(self, message, context: CallbackContext) -> None:
        """Save responses and complete the quiz."""
        user = message.from_user
        quiz_data = context.user_data.get('quiz_data', {})
        
        if self.sheets.save_response(user.id, user.username, quiz_data['answers'], self.questions):
            message.reply_text("Quiz completed! Your responses have been saved.")
        else:
            message.reply_text("Error saving responses. Please try again.")

def main():
    """Run the bot."""
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    bot = QuizBot()

    dispatcher.add_handler(CommandHandler("start", bot.start))
    dispatcher.add_handler(CommandHandler("quiz", bot.quiz))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, bot.handle_response))
    dispatcher.add_handler(CallbackQueryHandler(bot.handle_response))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

