import os
import logging
import json
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
logger = logging.getLogger(__name__)

class FormBot:
    def __init__(self):
        self.questions = self.load_questions()
        
    def load_questions(self):
        """Load and validate questions from JSON file."""
        try:
            with open('questions.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Validate question format
                for q in data['quiz']:
                    if 'question' not in q or 'options' not in q:
                        logger.error(f"Invalid question format: {q}")
                return data['quiz']
        except Exception as e:
            logger.error(f"Error loading questions: {str(e)}")
            return []

    @staticmethod
    def get_user_data(context: CallbackContext):
        """Initialize or get user data with proper structure."""
        if 'form_data' not in context.user_data:
            context.user_data['form_data'] = {
                'current_question': 0,
                'answers': {},
                'start_time': datetime.now().isoformat(),
                'completed': False
            }
        return context.user_data['form_data']

    def save_response(self, user_id: int, form_data: dict):
        """Save user responses to JSON file."""
        try:
            filename = f'responses/response_{user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            os.makedirs('responses', exist_ok=True)
            
            response_data = {
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'answers': form_data['answers'],
                'completion_time': (
                    datetime.now() - datetime.fromisoformat(form_data['start_time'])
                ).total_seconds()
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2)
                
            logger.info(f"Saved response for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving response: {str(e)}")
            return False

    def start(self, update: Update, context: CallbackContext) -> None:
        """Handle the /start command."""
        user = update.effective_user
        welcome_text = (
            f"👋 Welcome {user.first_name}!\n\n"
            "This is a form bot for Voices Ignited.\n\n"
            "📝 Use /form to start filling out the form\n"
            "❓ Use /help to see all available commands\n"
            "🔄 Use /reset if you need to start over"
        )
        update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

    def help_command(self, update: Update, context: CallbackContext) -> None:
        """Handle the /help command."""
        help_text = (
            "Available commands:\n\n"
            "📝 /form - Start or continue the form\n"
            "🔄 /reset - Reset your progress\n"
            "❓ /help - Show this help message\n"
            "📊 /status - Check your form completion status\n"
            "🚫 /cancel - Cancel current form submission"
        )
        update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    def form(self, update: Update, context: CallbackContext) -> None:
        """Handle the /form command."""
        if not self.questions:
            update.message.reply_text(
                "⚠️ Sorry, the form is currently unavailable. Please try again later."
            )
            return

        form_data = self.get_user_data(context)
        
        if form_data['completed']:
            update.message.reply_text(
                "✅ You've already completed the form.\n"
                "Use /reset if you want to start over."
            )
            return

        self.send_question(update, context, form_data)

    def send_question(self, update: Update, context: CallbackContext, form_data: dict) -> None:
        """Send the current question to user."""
        current_q = form_data['current_question']
        
        if current_q >= len(self.questions):
            self.complete_form(update, context, form_data)
            return

        question = self.questions[current_q]
        
        # Create keyboard with options
        keyboard = []
        for i, option in enumerate(question['options']):
            keyboard.append([InlineKeyboardButton(option, callback_data=f"ans_{i}")])
        
        # Add navigation buttons if needed
        nav_buttons = []
        if current_q > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data="nav_prev"))
        if len(form_data['answers']) > current_q:
            nav_buttons.append(InlineKeyboardButton("➡️ Skip", callback_data="nav_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"Question {current_q + 1} of {len(self.questions)}:\n\n"
            f"{question['question']}"
        )
        
        if isinstance(update, Update):
            update.message.reply_text(message, reply_markup=reply_markup)
        else:
            # For callback queries
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=reply_markup
            )

    def handle_button(self, update: Update, context: CallbackContext) -> None:
        """Handle button presses."""
        query = update.callback_query
        query.answer()
        
        form_data = self.get_user_data(context)
        data = query.data
        
        if data.startswith('ans_'):
            # Handle answer selection
            selected_option = int(data.split('_')[1])
            form_data['answers'][str(form_data['current_question'])] = selected_option
            form_data['current_question'] += 1
            query.edit_message_text("Response recorded ✅")
            self.send_question(update.effective_chat.id, context, form_data)
            
        elif data.startswith('nav_'):
            # Handle navigation
            if data == 'nav_prev' and form_data['current_question'] > 0:
                form_data['current_question'] -= 1
            elif data == 'nav_next':
                form_data['current_question'] += 1
            
            query.edit_message_text("Navigating...")
            self.send_question(update.effective_chat.id, context, form_data)

    def complete_form(self, update: Update, context: CallbackContext, form_data: dict) -> None:
        """Handle form completion."""
        user_id = update.effective_user.id
        
        # Save responses
        if self.save_response(user_id, form_data):
            form_data['completed'] = True
            
            # Generate response summary
            summary = "✅ Form completed! Here are your responses:\n\n"
            for q_num, ans_idx in form_data['answers'].items():
                q_num = int(q_num)
                question = self.questions[q_num]
                answer = question['options'][ans_idx]
                summary += f"Q{q_num + 1}: {question['question']}\n"
                summary += f"A: {answer}\n\n"
            
            summary += "\nThank you for completing the form! 🎉"
            
            # Send summary in chunks if needed
            if len(summary) > 4000:
                for i in range(0, len(summary), 4000):
                    context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=summary[i:i+4000]
                    )
            else:
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=summary
                )
        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ There was an error saving your responses. Please try again later."
            )

    def reset(self, update: Update, context: CallbackContext) -> None:
        """Reset user's form progress."""
        if 'form_data' in context.user_data:
            del context.user_data['form_data']
        update.message.reply_text(
            "🔄 Your form progress has been reset.\n"
            "Use /form to start over."
        )

    def status(self, update: Update, context: CallbackContext) -> None:
        """Show form completion status."""
        form_data = self.get_user_data(context)
        current_q = form_data['current_question']
        total_q = len(self.questions)
        answered = len(form_data['answers'])
        
        status_text = (
            f"📊 Form Status:\n\n"
            f"Total questions: {total_q}\n"
            f"Questions answered: {answered}\n"
            f"Current question: {current_q + 1}\n"
            f"Completion: {(answered/total_q)*100:.1f}%"
        )
        
        update.message.reply_text(status_text)

def main() -> None:
    """Start the bot."""
    # Create bot instance
    bot = FormBot()
    
    # Get bot token
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("No BOT_TOKEN found in environment variables!")
        return

    try:
        # Create updater
        updater = Updater(token)
        dispatcher = updater.dispatcher

        # Add handlers
        dispatcher.add_handler(CommandHandler("start", bot.start))
        dispatcher.add_handler(CommandHandler("help", bot.help_command))
        dispatcher.add_handler(CommandHandler("form", bot.form))
        dispatcher.add_handler(CommandHandler("reset", bot.reset))
        dispatcher.add_handler(CommandHandler("status", bot.status))
        dispatcher.add_handler(CallbackQueryHandler(bot.handle_button))

        # Log startup
        logger.info(f"Bot started with {len(bot.questions)} questions")

        # Start the Bot
        updater.start_polling()
        updater.idle()

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()