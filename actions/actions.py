# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

import os
import traceback
from typing import Any, Text, Dict, List

import requests
from dotenv import load_dotenv
from openai import AzureOpenAI
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

load_dotenv()

nytimes_api_key=os.getenv("NYTIMES_API_KEY")

endpoint = os.getenv("ENDPOINT_URL")
deployment = os.getenv("DEPLOYMENT_NAME")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")

# Initialize Azure OpenAI client with key-based authentication
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version="2025-01-01-preview",
)

# Prepare the system prompt
system_prompt = [
    {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": "You are an AI assistant that helps people find information."
            }
        ]
    }
]


# Action to handle the start of a session, welcoming the user
class ActionSessionStart(Action):

    def name(self) -> str:
        return "action_session_start"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_welcome")
        return []


# Action to insert a newline in the conversation for better readability
class ActionNewline(Action):

    def name(self) -> str:
        return "action_newline"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="\n")
        return []


# Action to fetch news articles from the New York Times API based on user-specified category
class ActionNYTimes(Action):

    def name(self) -> Text:
        return "action_get_news"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        category = tracker.get_slot('news_category')
        if not category or category.strip() == "":
            dispatcher.utter_message(text="Please specify a news category (e.g. world, business, technology).\n")
        else:
            url = f"https://api.nytimes.com/svc/news/v3/content/all/{category}.json"
            params = {'api-key': nytimes_api_key, 'limit': 5}
            try:
                response = requests.get(url, params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if "results" not in data or not data["results"]:
                    dispatcher.utter_message(text=f"No articles found for category '{category}'.\n")
                    return []

                for i, each_news in enumerate(data["results"], start=1):
                    output_msg = (
                        f"{i}. {each_news.get('title','No title')} - section: {each_news.get('section','N/A')}, "
                        f"published on {each_news.get('published_date','N/A')}\n"
                        f"Summary: {each_news.get('abstract','No summary')}\n"
                        f"Read more: {each_news.get('url','No link')}\n"
                    )
                    dispatcher.utter_message(text=output_msg)
            except Exception as e:
                print(f"Error fetching NYT news:")
                print(str(e))
                print(traceback.format_exc())
                dispatcher.utter_message(text="Sorry, something went wrong while fetching the news.\n")
        
        return []


# Action to handle user queries and generate responses using the Azure Openai LLM
class ActionAzureOpenAIResponse(Action):

  def name(self) -> Text:  
    return "action_azure_openai_response" 
  
  def run(self, dispatcher: CollectingDispatcher,  
          tracker: Tracker,  
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]: 
        
        user_message = tracker.latest_message.get("text", "")
        if not user_message or user_message.strip() == "":
            dispatcher.utter_message(text="Could you repeat your query?\n")
        else:
            try:
                # Prepare the user prompt
                user_prompt = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_message
                            }
                        ]
                    }
                ]

                # Combine to form the chat prompt
                chat_prompt = system_prompt + user_prompt

                # Generate the completion
                completion = client.chat.completions.create(
                    model=deployment,
                    messages=chat_prompt,
                    max_tokens=1024,
                    temperature=0.7,
                    top_p=0.95,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stop=None,
                    stream=False
                )

                answer = str(completion.choices[0].message.content).strip()
                if answer:
                    dispatcher.utter_message(text=answer)
                else:
                    dispatcher.utter_message(text="Sorry, I couldn't find a good answer for that.\n")
            except Exception as e:
                print("Error in Azure OpenAI request:")
                print(str(e))
                print(traceback.format_exc())
                dispatcher.utter_message(text="Sorry, something went wrong while contacting the model.\n")
        
        return []


