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
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

class QuizBot:
    def __init__(self):
        self.updater = Updater(BOT_TOKEN)
        self.dispatcher = self.updater.dispatcher
        self.sheets = SheetsHelper()
        
        # Load questions
        with open('questions.json', 'r') as f:
            self.questions = json.load(f)['quiz']
        
        # Add handlers
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('quiz', self.quiz))
        self.dispatcher.add_handler(CallbackQueryHandler(self.handle_button))
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_text))
        
    def start(self, update: Update, context: CallbackContext):
        update.message.reply_text("Welcome! Use /quiz to start.")
        
    def quiz(self, update: Update, context: CallbackContext):
        context.user_data['current_question'] = 0
        context.user_data['answers'] = {}
        self.send_question(update.message, context)
        
    def send_question(self, message, context: CallbackContext):
        q_index = context.user_data.get('current_question', 0)
        
        if q_index >= len(self.questions):
            self.finish_quiz(message, context)
            return
            
        question = self.questions[q_index]
        text = f"Question {q_index + 1}: {question['question']}"
        
        if question.get('type') == 'yes_no':
            keyboard = [
                [InlineKeyboardButton("Yes", callback_data="Yes")],
                [InlineKeyboardButton("No", callback_data="No")]
            ]
            message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif 'options' in question:
            # For multiple choice, use numbers as callback data
            keyboard = []
            for i, opt in enumerate(question['options']):
                keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=str(i))])
            message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            message.reply_text(text)
            
    def handle_button(self, update: Update, context: CallbackContext):
        query = update.callback_query
        q_index = context.user_data.get('current_question', 0)
        question = self.questions[q_index]
        
        # Get answer text
        if question.get('type') == 'yes_no':
            answer = query.data
        else:
            # For multiple choice, get the full option text
            answer = question['options'][int(query.data)]
            
        # Save answer
        context.user_data['answers'][str(q_index)] = answer
        context.user_data['current_question'] = q_index + 1
        
        # Show answer
        query.edit_message_text(f"{query.message.text}\nYour answer: {answer}")
        
        # Next question
        self.send_question(query.message, context)
        
    def handle_text(self, update: Update, context: CallbackContext):
        q_index = context.user_data.get('current_question', 0)
        
        if q_index >= len(self.questions):
            update.message.reply_text("Quiz is finished. Use /quiz to start again.")
            return
            
        # Save answer
        context.user_data['answers'][str(q_index)] = update.message.text
        context.user_data['current_question'] = q_index + 1
        
        # Next question
        self.send_question(update.message, context)
        
    def finish_quiz(self, message, context: CallbackContext):
        answers = context.user_data.get('answers', {})
        row = []
        
        # Format answers in order
        for i in range(len(self.questions)):
            answer = answers.get(str(i), '')
            row.append(str(answer))
            
        # Add timestamp
        row.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Save to sheets
        if self.sheets.append_row(row):
            message.reply_text("Thank you for completing the quiz!")
        else:
            message.reply_text("Error saving responses. Please try again.")
            
    def run(self):
        self.updater.start_polling()
        logger.info("Bot started")
        self.updater.idle()

if __name__ == '__main__':
    bot = QuizBot()
    bot.run()
