"""Top-level LangGraph composition for the role-matching system.

Open this file to see the system-level workflow. Each named node is implemented in a single module
under `workflows/nodes/`, so later Gmail, profile, embedding, retrieval, and response nodes can be
added here without turning this file into an implementation dump.

Current workflow:

    START -> query_processing -> gmail_connection -> gmail_retrieval -> candidate_text_extraction
        -> candidate_embedding -> role_retrieval -> response_planning -> result_formatting -> END

Planned successors after query-processing validation:

    query_processing -> gmail_connection -> gmail_retrieval -> candidate_text_extraction
        -> candidate_embedding -> role_retrieval -> response
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from role_matching.workflows.nodes.candidate_embedding import candidate_embedding_node
from role_matching.workflows.nodes.candidate_text_extraction import candidate_text_extraction_node
from role_matching.workflows.nodes.gmail_connection import gmail_connection_node
from role_matching.workflows.nodes.gmail_retrieval import gmail_retrieval_node
from role_matching.workflows.nodes.query_processing import query_processing_node
from role_matching.workflows.nodes.response_planning import response_planning_node
from role_matching.workflows.nodes.result_formatting import result_formatting_node
from role_matching.workflows.nodes.role_retrieval import role_retrieval_node
from role_matching.workflows.state import RoleMatchingState


def _route_after_query_processing(state: RoleMatchingState) -> str:
    """Only touch Gmail after query validation produced a trusted MatchRequest."""

    if state.get("status") == "completed" and state.get("match_request"):
        return "gmail_connection"
    return "end"


def _route_after_gmail_connection(state: RoleMatchingState) -> str:
    """Do not read even approved-label metadata when credential validation failed."""

    return "gmail_retrieval" if state.get("gmail_connection_ok") else "end"


def _route_after_gmail_retrieval(state: RoleMatchingState) -> str:
    """Do not attempt extraction when the bounded label query returned no messages."""

    return "candidate_text_extraction" if state.get("submission_references") else "end"


def _route_after_candidate_extraction(state: RoleMatchingState) -> str:
    """Only create vectors when at least one candidate yielded usable text."""

    return "candidate_embedding" if state.get("candidate_documents") else "end"


def _route_after_candidate_embedding(state: RoleMatchingState) -> str:
    """Only query Qdrant when at least one valid local candidate vector was created."""

    return "role_retrieval" if state.get("candidate_vectors") else "end"


def _route_after_role_retrieval(state: RoleMatchingState) -> str:
    """Plan presentation only after deterministic role retrieval succeeds."""

    return "response_planning" if state.get("role_matches") else "end"


def build_role_matching_graph():
    """Compile the system-level graph.

    Deterministic result formatting follows Qdrant role retrieval. The graph intentionally ends
    before any optional future explanation feature, which must stay grounded in retrieved evidence.
    """

    graph = StateGraph(RoleMatchingState)
    graph.add_node("query_processing", query_processing_node)
    graph.add_node("gmail_connection", gmail_connection_node)
    graph.add_node("gmail_retrieval", gmail_retrieval_node)
    graph.add_node("candidate_text_extraction", candidate_text_extraction_node)
    graph.add_node("candidate_embedding", candidate_embedding_node)
    graph.add_node("role_retrieval", role_retrieval_node)
    graph.add_node("response_planning", response_planning_node)
    graph.add_node("result_formatting", result_formatting_node)
    graph.add_edge(START, "query_processing")
    graph.add_conditional_edges(
        "query_processing",
        _route_after_query_processing,
        {"gmail_connection": "gmail_connection", "end": END},
    )
    graph.add_conditional_edges(
        "gmail_connection",
        _route_after_gmail_connection,
        {"gmail_retrieval": "gmail_retrieval", "end": END},
    )
    graph.add_conditional_edges(
        "gmail_retrieval",
        _route_after_gmail_retrieval,
        {"candidate_text_extraction": "candidate_text_extraction", "end": END},
    )
    graph.add_conditional_edges(
        "candidate_text_extraction",
        _route_after_candidate_extraction,
        {"candidate_embedding": "candidate_embedding", "end": END},
    )
    graph.add_conditional_edges(
        "candidate_embedding",
        _route_after_candidate_embedding,
        {"role_retrieval": "role_retrieval", "end": END},
    )
    graph.add_conditional_edges(
        "role_retrieval",
        _route_after_role_retrieval,
        {"response_planning": "response_planning", "end": END},
    )
    graph.add_edge("response_planning", "result_formatting")
    graph.add_edge("result_formatting", END)
    return graph.compile()
