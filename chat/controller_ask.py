import logging
import openai
import requests
import inspect
from traceback import format_exc
from urllib.parse import urljoin

from .controller_gpt import GptController
from .controller_kbot import KbotController
from chat import tasks as chat_tasks

logger = logging.getLogger(__name__)

class AskController():
    def __init__(self, chat_data, request_data, session_key):
        self.chat_data = chat_data
        self.request_data = request_data
        self.session_key = session_key
        self.kbot_controller = KbotController()
        self.gpt_controller = GptController()
        self.global_cost = [0.0]
        self.question_summary = ''
        self.history = []
        self.conversation_summary = ''
        self.transcript = ''
        self.knowledge = ''
        self.current_response_text = ''
        self.input_txt = self.request_data.get('input_text')
        self.kbot_only = self.request_data.get('kbot_only')
        if self.kbot_only:
            print("user requested kbot_only processing")
        self.supplied_search_text = self.request_data.get('search_text')
        self.list_ids = ''

    def ask(self):
        # always return data or an errors array, never throw exceptions
        try:
            response = self.ask_triboo()
            return response
        except Exception as e:
            logger.error(f'error processing request for Triboo')
            logger.error(format_exc())
            self.chat_data['errors'] = str(e)
            return {
                'errors': [str(e)],
            }

    def get_history(self):
        #Check to see if context changed before submitting the question to the CosSim KB function
        self.question_summary = self.input_txt # search criteria from new question only
        self.conversation_summary = self.chat_data.get('conversation_summary', '')
        if not self.chat_data.get('chat_history'): # new conversation
            logger.info('NEW CONVO CONTEXT')
            self.conversation_summary = self.gpt_controller.create_search_text(
                self.conversation_summary, self.question_summary, self.global_cost) #returns search_txt
            # self.conversation_summary = self.gpt_controller.summarise_question(
            #     self.question_summary, self.global_cost) 
            return

        self.history = self.chat_data.get('chat_history')

        context = self.gpt_controller.same_context(self.conversation_summary, self.input_txt, self.global_cost).lower()
        if context == 'yes':
            self.question_summary += (' ' + self.input_txt) # search criteria from whole conversation
            logger.info(f'UNCHANGED CONTEXT')
        else:
            self.question_summary = self.input_txt # search criteria from new question only
            self.history = []
            logger.info(f'CHANGED CONTEXT')
        self.conversation_summary = self.gpt_controller.create_search_text(
            self.conversation_summary, self.question_summary, self.global_cost) #returns search_txt
#        self.conversation_summary = self.gpt_controller.summarise_question(self.question_summary, self.global_cost) 

    def add_q_and_a_to_chat_history(self):
        #add Q&A to a list tracking the conversation
        self.history.append({"role": "user", "content": self.input_txt}) 
        self.history.append({"role": "assistant", "content": self.current_response_text}) 

    def save_conversation_data(self):
        #summarise transcription for question answer function (this is after the results to reduce wait time)

        logger.info(f'\nTHE QUESTION IS: {self.input_txt}')
        logger.info(f"I SEARCHED FOR DOCUMENTS RELATED TO: {self.conversation_summary}")
        logger.info(f'I REPLIED: {self.current_response_text}')
        conversation_summary = self.gpt_controller.create_summary_text(self.conversation_summary,self.input_txt, self.global_cost)      #returns conversation_summary
 
        self.chat_data['chat_history'] = self.history 
        self.chat_data['conversation_summary'] = conversation_summary


    def ask_triboo(self):
        self.get_history()
#        conversation_summary = self.gpt_controller.create_summary_text(self.conversation_summary,self.input_txt, self.global_cost)      #returns conversation_summary
#        search_txt = self.gpt_controller.create_search_text(self.conversation_summary, self.input_txt, self.global_cost)                 #returns search_txt
        knowledge = self.gpt_controller.search_for_relevant_documents(search_txt)                           #returns knowledge
        kbot_reply = self.gpt_controller.respond_to_the_question(knowledge,self.conversation_summary, self.input_txt, self.global_cost)  #returns kbot_reply

        self.add_q_and_a_to_chat_history()
        self.save_conversation_data()

        logger.info(f'CONVERSATION SUMMARY: {self.conversation_summary}')
        logger.info(f'Cost: ${self.global_cost[0]}')

        return {
            'response_text': self.current_response_text,
        }

