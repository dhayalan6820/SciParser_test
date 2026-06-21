import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from tavily import TavilyClient

load_dotenv()

# ==========================================
# 1. Define the Input Schema for the LLM
# ==========================================
# This is what the LLM reads to understand WHICH parameters it can change dynamically.
class DynamicTavilySearchSchema(BaseModel):
    query: str = Field(
        ..., 
        description="The specific search query to execute on the web."
    )
    search_depth: str = Field(
        default="basic", 
        description="Use 'basic' for quick factual answers. Use 'advanced' for deep, comprehensive research that requires multiple sources."
    )
    time_range: str = Field(
        default=None, 
        description="Filter results by time. Useful for news. Valid options: 'day', 'week', 'month', 'year'. Leave as null for all time."
    )
    max_results: int = Field(
        default=3, 
        description="Number of search results to return. Increase this up to 10 if the topic is complex."
    )
    include_images: bool = Field(
        default=False, 
        description="Set to True ONLY if the user specifically asks for visual context, pictures, or images."
    )


@tool("ai_parser_dynamic_search", args_schema=DynamicTavilySearchSchema)
def dynamic_search_tool(query: str, search_depth: str = "basic", time_range: str = None, max_results: int = 3, include_images: bool = False):
    """
    AI Parser Web Search Engine.
    Use this tool to search the internet for up-to-date information, real-time news, and factual verification.
    You have dynamic control over the search. For example:
    - If the user asks about breaking news, set 'time_range' to 'day'.
    - If the user asks for an image of something, set 'include_images' to True.
    - If the user needs a deep dive on a complex topic, set 'search_depth' to 'advanced'.
    """
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    
    # The LLM passes its chosen parameters into the actual API call here
    response = client.search(
        query=query,
        search_depth=search_depth,
        time_range=time_range,
        max_results=max_results,
        include_images=include_images
    )
    return response

# ==========================================
# 3. The Agent Framework
# ==========================================
class AIParserAgent:
    def __init__(self):
        load_dotenv()
        if not os.getenv("TAVILY_API_KEY"):
            raise ValueError("Missing TAVILY_API_KEY in .env file.")
        
        # We attach the tool to the agent.
        # When you add an LLM later, you will bind this tool to the LLM.
        self.tools = [dynamic_search_tool]

    def manual_test_tool(self, simulated_llm_kwargs: dict):
        """
        Since you are adding the LLM later, this simulates how the LLM 
        will invoke the tool by passing in dynamic JSON arguments.
        """
        print(f"[AI Parser] Simulated LLM triggered search with parameters: \n{json.dumps(simulated_llm_kwargs, indent=2)}\n")
        
        # Execute the tool using the parameters the "LLM" decided on
        raw_output = dynamic_search_tool.invoke(simulated_llm_kwargs)
        
        return raw_output

