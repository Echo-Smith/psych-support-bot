from langgraph.graph import END, START, StateGraph

from psych_support_bot.ai.nodes.intent_router import route_intent
from psych_support_bot.ai.nodes.knowledge import load_knowledge_context
from psych_support_bot.ai.nodes.memory import load_memory_context
from psych_support_bot.ai.nodes.response_generator import generate_response
from psych_support_bot.ai.nodes.risk_classifier import classify_risk
from psych_support_bot.ai.nodes.safety_reviewer import review_response
from psych_support_bot.ai.nodes.summary_writer import write_summary
from psych_support_bot.ai.schemas.state import GraphState


def _route_after_risk(state: GraphState) -> str:
    return "crisis" if state["risk_result"].needs_crisis_mode else "normal"


def build_conversation_graph():
    graph = StateGraph(GraphState)
    graph.add_node("risk_classifier", classify_risk)
    graph.add_node("intent_router", route_intent)
    graph.add_node("memory_loader", load_memory_context)
    graph.add_node("knowledge_loader", load_knowledge_context)
    graph.add_node("response_generator", generate_response)
    graph.add_node("safety_reviewer", review_response)
    graph.add_node("summary_writer", write_summary)

    graph.add_edge(START, "risk_classifier")
    graph.add_conditional_edges(
        "risk_classifier",
        _route_after_risk,
        {"crisis": "response_generator", "normal": "intent_router"},
    )
    graph.add_edge("intent_router", "memory_loader")
    graph.add_edge("memory_loader", "knowledge_loader")
    graph.add_edge("knowledge_loader", "response_generator")
    graph.add_edge("response_generator", "safety_reviewer")
    graph.add_edge("safety_reviewer", "summary_writer")
    graph.add_edge("summary_writer", END)
    return graph.compile()


conversation_graph = build_conversation_graph()
