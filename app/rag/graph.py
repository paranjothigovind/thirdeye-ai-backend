"""LangGraph implementation for stateful RAG"""
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator

from app.core.logging import get_logger
from app.rag.retriever import hybrid_retriever
from app.rag.prompts import SYSTEM_PROMPT, QUERY_REWRITE_PROMPT
from app.models.azure_openai import azure_openai_client
from app.rag.guardrails import guardrails

logger = get_logger(__name__)


class GraphState(TypedDict):
    """State for the RAG graph"""
    query: str
    rewritten_query: str
    documents: List[Dict[str, Any]]
    response: str
    citations: List[Dict[str, str]]
    needs_retry: bool
    retry_count: int
    messages: Annotated[List[Dict[str, str]], operator.add]


class RAGGraph:
    """Stateful RAG graph with corrective loops"""
    
    def __init__(self):
        """Initialize RAG graph"""
        self.retriever = hybrid_retriever
        self.llm = azure_openai_client
        self.guardrails = guardrails
        self.max_retries = 2
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("rewrite_query", self._rewrite_query_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("check_retrieval", self._check_retrieval_node)
        workflow.add_node("generate", self._generate_node)
        workflow.add_node("check_response", self._check_response_node)
        workflow.add_node("add_citations", self._add_citations_node)
        
        # Set entry point
        workflow.set_entry_point("rewrite_query")
        
        # Add edges
        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("retrieve", "check_retrieval")
        
        # Conditional edge after retrieval check
        workflow.add_conditional_edges(
            "check_retrieval",
            self._should_retry_retrieval,
            {
                "retry": "rewrite_query",
                "continue": "generate"
            }
        )
        
        workflow.add_edge("generate", "check_response")
        
        # Conditional edge after response check
        workflow.add_conditional_edges(
            "check_response",
            self._should_retry_generation,
            {
                "retry": "retrieve",
                "continue": "add_citations"
            }
        )
        
        workflow.add_edge("add_citations", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    async def _rewrite_query_node(self, state: GraphState) -> GraphState:
        """Rewrite query for better retrieval"""
        try:
            query = state["query"]
            
            # Simple rewrite using LLM
            prompt = QUERY_REWRITE_PROMPT.format(query=query)
            
            rewritten = ""
            async for chunk in self.llm.generate_response(
                [{"role": "user", "content": prompt}],
                stream=False
            ):
                rewritten += chunk
            
            logger.info(f"Rewrote query: '{query}' -> '{rewritten}'")
            
            return {
                **state,
                "rewritten_query": rewritten.strip(),
                "retry_count": state.get("retry_count", 0)
            }
        except Exception as e:
            logger.error(f"Error rewriting query: {e}")
            return {**state, "rewritten_query": state["query"]}
    
    async def _retrieve_node(self, state: GraphState) -> GraphState:
        """Retrieve relevant documents"""
        try:
            query = state.get("rewritten_query", state["query"])
            
            # Retrieve from all layers for Angelitic RAG
            canonical_docs = await self.retriever.retrieve_by_layer(query, "canonical", top_k=2)
            safety_docs = await self.retriever.retrieve_by_layer(query, "safety", top_k=2)
            practices_docs = await self.retriever.retrieve_by_layer(query, "practices", top_k=2)
            qa_docs = await self.retriever.retrieve_by_layer(query, "qa", top_k=2)
            
            # Combine and deduplicate
            all_docs = canonical_docs + safety_docs + practices_docs + qa_docs
            
            # Remove duplicates based on content
            seen = set()
            unique_docs = []
            for doc in all_docs:
                content_hash = hash(doc["content"][:100])
                if content_hash not in seen:
                    seen.add(content_hash)
                    unique_docs.append(doc)
            
            logger.info(f"Retrieved {len(unique_docs)} unique documents")
            
            return {**state, "documents": unique_docs}
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return {**state, "documents": []}
    
    async def _check_retrieval_node(self, state: GraphState) -> GraphState:
        """Check if retrieval was successful"""
        documents = state.get("documents", [])
        retry_count = state.get("retry_count", 0)
        
        # Check if we have enough documents
        needs_retry = len(documents) < 2 and retry_count < self.max_retries
        
        if needs_retry:
            logger.warning(f"Insufficient documents ({len(documents)}), retrying...")
        
        return {
            **state,
            "needs_retry": needs_retry,
            "retry_count": retry_count + 1 if needs_retry else retry_count
        }
    
    def _should_retry_retrieval(self, state: GraphState) -> str:
        """Decide whether to retry retrieval"""
        return "retry" if state.get("needs_retry", False) else "continue"
    
    async def _generate_node(self, state: GraphState) -> GraphState:
        """Generate response from documents"""
        try:
            query = state["query"]
            documents = state.get("documents", [])
            
            # Format context
            context = self._format_context(documents)
            
            # Generate response
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ]
            
            response = ""
            async for chunk in self.llm.generate_response(messages, stream=False):
                response += chunk
            
            logger.info(f"Generated response of length {len(response)}")
            
            return {**state, "response": response}
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {**state, "response": "I apologize, but I encountered an error generating a response."}
    
    async def _check_response_node(self, state: GraphState) -> GraphState:
        """Check response quality"""
        response = state.get("response", "")
        retry_count = state.get("retry_count", 0)
        
        # Check with guardrails
        check = self.guardrails.check_response(response)
        
        # Decide if retry needed
        critical_issues = ["missing_citations", "contains_medical_advice"]
        has_critical_issue = any(issue in check["issues"] for issue in critical_issues)
        needs_retry = has_critical_issue and retry_count < self.max_retries
        
        if needs_retry:
            logger.warning(f"Response has issues: {check['issues']}, retrying...")
        
        return {
            **state,
            "needs_retry": needs_retry,
            "retry_count": retry_count + 1 if needs_retry else retry_count
        }
    
    def _should_retry_generation(self, state: GraphState) -> str:
        """Decide whether to retry generation"""
        return "retry" if state.get("needs_retry", False) else "continue"
    
    async def _add_citations_node(self, state: GraphState) -> GraphState:
        """Extract and add citations"""
        response = state.get("response", "")
        
        # Extract citations
        from app.rag.chains import RAGChain
        chain = RAGChain()
        citations = chain.extract_citations(response)
        
        logger.info(f"Extracted {len(citations)} citations")
        
        return {**state, "citations": citations}
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format documents as context"""
        if not documents:
            return "No relevant information found."
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            title = doc.get("title", "Unknown")
            content = doc.get("content", "")
            source = doc.get("source", "")
            page = doc.get("page")
            url = doc.get("url")
            
            # Format reference
            if source == "pdf" and page:
                ref = f"[Source: {title}, page {page}]"
            elif source == "web" and url:
                ref = f"[Source: {title}, {url}]"
            else:
                ref = f"[Source: {title}]"
            
            context_parts.append(f"{i}. {ref}\n{content}\n")
        
        return "\n".join(context_parts)
    
    async def invoke(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        """Invoke the graph"""
        initial_state = {
            "query": query,
            "rewritten_query": "",
            "documents": [],
            "response": "",
            "citations": [],
            "needs_retry": False,
            "retry_count": 0,
            "messages": []
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            result = await self.graph.ainvoke(initial_state, config)
            return result
        except Exception as e:
            logger.error(f"Error in graph execution: {e}")
            raise


# Global graph instance
rag_graph = RAGGraph()