import logging
import os
import inspect

from .controller_kbot import KbotController

import openai
openai.verify_ssl_certs = False

logger = logging.getLogger(__name__)

# TODO this is going to need to work with async programming, and maybe celery
#  chatGPT WILL time out on us some times, need to handle these kinds of conditions
class GptController():
    def __init__(self):
        self.kbot_controller = KbotController()
        api_key_path = os.path.join('keys', f'openai_key.txt')
        if not os.path.isfile(api_key_path):
            raise Exception(f'no openai api key found: {api_key_path}')
        with open(api_key_path, "r") as f:
            the_key = f.read()
            openai.api_key = the_key.strip()

    # Same topic function
    def call_gpt(self, p_messages, p_parameters, global_cost):

      completion = openai.ChatCompletion.create(
        messages = p_messages,
        model = p_parameters['model'], 
        temperature = p_parameters['temperature'],
        max_tokens = p_parameters['max_tokens'],
        top_p = 1.0,
        frequency_penalty = 0.5,
        presence_penalty = 0.5
      )
      logger.info('openai call complete')
      
      cost = completion.usage
      cost["function"] = inspect.currentframe().f_code.co_name
      logger.info(cost)

      in_cost = (completion.usage['prompt_tokens'] * 0.003)/1000
      out_cost = (completion.usage['completion_tokens'] * 0.004)/1000
      global_cost[0] += (in_cost + out_cost)

      return ''.join(completion.choices[0].message.content)


    def respond_to_the_question(self, knowledge,conversation_summary,input_txt, global_cost):
      p_messages = [{'role': 'system', 'content' : "you are here to answer the question about the Triboo learning platform using the following user guide\n" + knowledge[:5000]},
                    {'role': 'user', 'content' : "what do you remember of the conversation so far"},
                    {'role': 'assistant', 'content' : conversation_summary},
                    {'role': 'user', 'content' : input_txt + "\nAnswer the question\nStick to answers from the user guide\nSeek confirmation or clarification"}
                  ]#Use the user guide to ask one funneling question at a time until you have a good answer

      p_parameters = {'model':'gpt-3.5-turbo-16k', 'temperature':0.3,'max_tokens':1000}

      kbot_reply = self.call_gpt(p_messages, p_parameters, global_cost)

      return kbot_reply

    def same_context(self, conversation_summary, input_txt, global_cost):
      p_messages = [
        {"role": "system", "content" : conversation_summary + "\n\nIs the following text a continuation of the previous conversation, [yes] or [no]\n"},
        {"role": "user", "content" : input_txt}
      ]

      p_parameters = {'model':'gpt-3.5-turbo', 'temperature':0.1,'max_tokens':1000}

      conversation_summary = self.call_gpt(p_messages, p_parameters, global_cost)

      return conversation_summary

    # Create a summary of the converstion so far to retain context (understand back references from the user, and gradually build up knowledge)
    def create_summary_text(self, conversation_summary, input_txt, global_cost):
      p_messages = [{'role': 'system', 'content' : "Here is the conversation so far"},
                    {'role': 'assistant', 'content' : conversation_summary},
                    {'role': 'user', 'content' : input_txt},
                    {'role': 'user', 'content' : "Summarise the conversation into a list.\nKeep just the relevant facts\nDo not speculate"}                
                   ]

      p_parameters = {'model':'gpt-3.5-turbo', 'temperature':0.1,'max_tokens':1000}

      conversation_summary = self.call_gpt(p_messages, p_parameters, global_cost)

      return conversation_summary

    #Create serch text
    def create_search_text(self, summary, input_txt, global_cost):
      p_messages = [{'role': 'system', 'content' : "You are typing into a search engine"},
                    {'role': 'user', 'content' : "convert the text into one concise sentance which would work well in a search engine.\nNot a list.\n" + summary + "\n" + input_txt}]

      p_parameters = {'model':'gpt-3.5-turbo', 'temperature':0.1,'max_tokens':1000}

      search_txt = self.call_gpt(p_messages, p_parameters, global_cost)
      return search_txt

    #Search and return relevant docs from the knowledge base
    def search_for_relevant_documents(self, search_txt):
      df_docs = self.kbot_controller.K_BOT(search_txt)

      knowledge = 'knowledge ID\tTitle\tContent'
      for index, row in df_docs.iterrows():
        knowledge = knowledge + '\n' + str(row['index']) + '\t'  + row['title'] + '\t'  + row['Content']

      return knowledge

    def same_context(self, previous_answer, question, global_cost):
      messages = [
        {"role": "system", "content" : previous_answer + "\n\nIs the following text a continuation of the previous conversation, [yes] or [no]\n"},
        {"role": "user", "content" : question}
      ]
      
      p_parameters = {'model':'gpt-3.5-turbo', 'temperature':0.1,'max_tokens':1000}

      search_txt = self.call_gpt(p_messages, p_parameters, global_cost)
      return search_txt


    # Function to summarise the user sequence into a concise string of key words for searching the KB
    def summarise_question(self, questions, global_cost):

      messages = [
          {"role": "system", "content" : "Return search criteria"},
          {"role": "user", "content" : "convert the text into one concise search criteria which would work well in a search engine\n" + questions},
          {"role": "assistant", "content" :"my search query"}
      ]
      
      logger.info('calling openai for chat completion')
      completion = openai.ChatCompletion.create(
        model="gpt-4", 
        temperature = 0.1,
        max_tokens  = 200,
        top_p=1,
        frequency_penalty = 1.5,
        presence_penalty  = 0.0,
        messages = messages
      )
      logger.info('openai call complete')
      cost = completion.usage
      cost["function"] = inspect.currentframe().f_code.co_name
      logger.info(cost)

      in_cost = (completion.usage['prompt_tokens'] * 0.03)/1000
      out_cost = (completion.usage['completion_tokens'] * 0.06)/1000
      # test that this works, if global_cost is passed by value it won't
      global_cost[0] += (in_cost + out_cost)

      return ''.join(completion.choices[0].message.content)
