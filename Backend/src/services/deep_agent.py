import json
import logging
from typing import TypedDict, List, Optional, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

logger = logging.getLogger("sciparser")

class DeepAgentState(TypedDict):
    messages: List[BaseMessage]
    proposed_response: Optional[AIMessage]
    critic_feedback: str
    is_valid: bool
    retry_count: int

class DeepAgent:
    """
    A specialized subgraph that implements an Actor-Critic cognitive loop.
    Instead of accepting the very first tool call proposed by the LLM, 
    this agent proposes an action, evaluates it against recent state, 
    and refines it before returning it to the main orchestrator.
    """
    def __init__(self, llm_with_tools, max_retries: int = 3):
        self.llm_with_tools = llm_with_tools
        self.max_retries = max_retries
        self.critic_llm = llm_with_tools

        workflow = StateGraph(DeepAgentState)
        workflow.add_node("actor", self.node_actor)
        workflow.add_node("critic", self.node_critic)
        
        workflow.set_entry_point("actor")
        
        workflow.add_conditional_edges(
            "critic",
            self.edge_router,
            {"actor": "actor", END: END}
        )
        workflow.add_edge("actor", "critic")

        self.app = workflow.compile()

    async def execute(self, current_messages: List[BaseMessage]) -> AIMessage:
        """
        Executes the deep reflection loop and returns the final refined AIMessage.
        """
        state = {
            "messages": current_messages,
            "proposed_response": None,
            "critic_feedback": "",
            "is_valid": False,
            "retry_count": 0
        }
        
        final_state = await self.app.ainvoke(state)
        return final_state["proposed_response"]

    async def node_actor(self, state: DeepAgentState):
        msgs = state["messages"].copy()
        
        if state.get("critic_feedback"):
            msgs.append(HumanMessage(
                content=f"SYSTEM CRITIQUE OF PREVIOUS PLAN:\n{state['critic_feedback']}\n\nPlease revise your proposed tool calls or parameters based on this critique."
            ))
            
        response = await self.llm_with_tools.ainvoke(msgs)
        return {
            "proposed_response": response,
            "retry_count": state.get("retry_count", 0) + 1
        }

    async def node_critic(self, state: DeepAgentState):
        response = state["proposed_response"]
        
        # If no tools were called, pass it through.
        if not response.tool_calls:
            return {"is_valid": True, "critic_feedback": ""}
            
        # Extract the proposed tool calls
        proposed_tools = json.dumps([{"name": t["name"], "args": t["args"]} for t in response.tool_calls], indent=2)
        
        critic_prompt = (
            "You are an expert autonomous web automation Critic.\n"
            "Your job is to review the Actor's proposed tool calls and identify OBVIOUS flaws, repetitive loops, or syntax errors.\n"
            f"PROPOSED TOOL CALLS:\n{proposed_tools}\n\n"
            "Evaluate:\n"
            "1. Are we trapped in a loop (e.g., repeating the same failed click)?\n"
            "2. Are the arguments valid and specific?\n"
            "If the plan is SOLID, output EXACTLY the word 'VALID'.\n"
            "If the plan is FLAWED, output a brief explanation of the flaw."
        )
        
        critic_msgs = [SystemMessage(content=critic_prompt)]
        
        llm_text_only = getattr(self.critic_llm, "bind", lambda **kwargs: self.critic_llm)(tools=[]) if hasattr(self.critic_llm, "bind") else self.critic_llm
        
        try:
            critique_resp = await llm_text_only.ainvoke(critic_msgs)
            content = critique_resp.content.strip()
            if "VALID" in content.upper() and len(content) < 50:
                return {"is_valid": True, "critic_feedback": ""}
            else:
                logger.info(f"[DeepAgent] Critic caught a flaw: {content}")
                return {"is_valid": False, "critic_feedback": content}
        except Exception as e:
            logger.warning(f"[DeepAgent] Critic failed, defaulting to valid. Error: {e}")
            return {"is_valid": True, "critic_feedback": ""}

    def edge_router(self, state: DeepAgentState) -> str:
        if state["is_valid"] or state.get("retry_count", 0) >= self.max_retries:
            return END
        return "actor"

class ObstaclePlanner:
    """
    Dynamically generates a step-by-step resolution plan for a detected obstacle 
    (e.g., modals, interstitials) based on the page state, adapting if previous plans failed.
    """
    def __init__(self, llm):
        # ensure we use a text-only LLM instance (no tools attached)
        self.llm = getattr(llm, "bind", lambda **kwargs: llm)(tools=[]) if hasattr(llm, "bind") else llm

    async def generate_plan(self, obstacle_type: str, observation_text: str, previous_failures: List[str]) -> str:
        prompt = (
            f"You are an expert autonomous web automation Planner.\n"
            f"The execution agent is currently blocked by an obstacle of type: {obstacle_type.upper()}.\n\n"
            f"CURRENT PAGE OBSERVATION:\n{observation_text[:3000]}\n\n"
        )
        
        if previous_failures:
            fails_str = "\n".join(f"- {f}" for f in previous_failures)
            prompt += (
                f"WARNING! The agent already tried to resolve this but failed.\n"
                f"PREVIOUS FAILED ATTEMPTS:\n{fails_str}\n\n"
                f"You MUST provide a DIFFERENT strategy than what was already tried.\n\n"
            )
            
        prompt += (
            "Based on the DOM observation above, generate a concise, step-by-step plan "
            "for the agent to bypass this obstacle using its available tools.\n"
            "Output ONLY the numbered steps."
        )
        
        try:
            resp = await self.llm.ainvoke([SystemMessage(content=prompt)])
            return resp.content.strip()
        except Exception as e:
            logger.error(f"[ObstaclePlanner] Failed to generate plan: {e}")
            return "1. Analyze the page and use an appropriate tool to dismiss the obstacle."
