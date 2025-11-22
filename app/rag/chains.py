"""LangChain chains for RAG"""
from typing import List, Dict, Any, AsyncIterator
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.core.logging import get_logger
from app.models.azure_openai import azure_openai_client
from app.rag.retriever import hybrid_retriever
from app.rag.prompts import SYSTEM_PROMPT, ANGELITIC_RAG_PROMPT

logger = get_logger(__name__)


class RAGChain:
    """Simple RAG chain for question answering"""
    
    def __init__(self):
        """Initialize RAG chain"""
        self.retriever = hybrid_retriever
        self.llm = azure_openai_client
    
    async def invoke(
        self,
        query: str,
        use_angelitic: bool = True,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Run RAG chain with streaming"""
        try:
            # Retrieve context
            if use_angelitic:
                context = await self._retrieve_angelitic_context(query)
            else:
                documents = await self.retriever.retrieve(query)
                logger.info(f"✅ Retrieved {len(documents)} documents for RAG context")
                context = self._format_context(documents)
            
            # Generate response
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ]
            
            async for chunk in self.llm.generate_response(messages, stream=stream):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in RAG chain: {e}")
            raise
    
    async def _retrieve_angelitic_context(self, query: str) -> str:
        """Retrieve context using Angelitic RAG layers with robust fallbacks"""
        # Retrieve from each layer with resilience to errors/None
        try:
            canonical_docs = await self.retriever.retrieve_by_layer(query, "canonical", top_k=2)
        except Exception as e:
            logger.error(f"Angelitic layer retrieval failed for 'canonical': {e}")
            canonical_docs = []
        try:
            safety_docs = await self.retriever.retrieve_by_layer(query, "safety", top_k=2)
        except Exception as e:
            logger.error(f"Angelitic layer retrieval failed for 'safety': {e}")
            safety_docs = []
        try:
            practices_docs = await self.retriever.retrieve_by_layer(query, "practices", top_k=2)
        except Exception as e:
            logger.error(f"Angelitic layer retrieval failed for 'practices': {e}")
            practices_docs = []
        try:
            qa_docs = await self.retriever.retrieve_by_layer(query, "qa", top_k=2)
        except Exception as e:
            logger.error(f"Angelitic layer retrieval failed for 'qa': {e}")
            qa_docs = []
        
        # Normalize None to empty lists
        canonical_docs = canonical_docs or []
        safety_docs = safety_docs or []
        practices_docs = practices_docs or []
        qa_docs = qa_docs or []
        
        # Format each layer
        canonical_context = self._format_context(canonical_docs)
        safety_context = self._format_context(safety_docs)
        practices_context = self._format_context(practices_docs)
        qa_context = self._format_context(qa_docs)
        
        # Combine using template with safe defaults
        return ANGELITIC_RAG_PROMPT.format(
            canonical_context=canonical_context or "No canonical teachings found.",
            safety_context=safety_context or "No safety information found.",
            practices_context=practices_context or "No practice information found.",
            qa_context=qa_context or "No Q&A examples found.",
            query=query
        )
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
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
    
    def extract_citations(self, response: str) -> List[Dict[str, str]]:
        """Extract citations from response"""
        import re
        
        # Pattern: [Source: title, page/url]
        pattern = r'\[Source:\s*([^,]+),\s*([^\]]+)\]'
        matches = re.findall(pattern, response)
        
        citations = []
        for title, reference in matches:
            citations.append({
                "title": title.strip(),
                "reference": reference.strip()
            })
        
        return citations

    async def clear_all(self) -> Dict[str, Any]:
        """Delete all documents and recreate the index"""
        try:
            # Delete the existing index
            try:
                self.index_client.delete_index(settings.AZURE_SEARCH_INDEX)
                logger.info(f"Deleted index: {settings.AZURE_SEARCH_INDEX}")
            except Exception as e:
                logger.warning(f"Index {settings.AZURE_SEARCH_INDEX} may not exist: {e}")

            # Recreate the index
            self._ensure_index()
            logger.info(f"Recreated index: {settings.AZURE_SEARCH_INDEX}")

            return {
                "status": "success",
                "message": "All vector data cleared and index recreated"
            }

        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# Global chain instance
rag_chain = RAGChain()