"""Post-Class Support Agent for post-meditation class inquiries"""
from typing import List, Dict, Any, AsyncIterator
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.core.logging import get_logger
from app.models.azure_openai import azure_openai_client
from app.rag.retriever import hybrid_retriever
from app.rag.prompts import SYSTEM_PROMPT

logger = get_logger(__name__)


class PostClassSupportAgent:
    """Specialized agent for post-class support questions"""
    
    def __init__(self):
        """Initialize Post-Class Support Agent"""
        self.retriever = hybrid_retriever
        self.llm = azure_openai_client
    
    async def invoke(
        self,
        query: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Run Post-Class Support Agent with streaming"""
        try:
            # Retrieve context with focus on post-practice integration and support
            documents = await self.retriever.retrieve(
                query,
                filters={"context": "post_class_support"}
            )
            logger.info(f"âœ… Retrieved {len(documents)} documents for Post-Class Support Agent context")
            context = self._format_context(documents)
            
            # Generate response with post-class specific instructions
            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ]
            
            async for chunk in self.llm.generate_response(messages, stream=stream):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in Post-Class Support Agent: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Get specialized system prompt for Post-Class Support Agent"""
        return """You are the Post-Class Support Assistant for the Third Eye Meditation AI Chatbot.
        
        Your role is to assist users with questions and experiences after they have attended a meditation class or completed a course.
        
        PRIMARY FUNCTIONS:
        - Help users integrate meditation experiences into daily life
        - Address common post-meditation questions and experiences
        - Provide guidance on maintaining practice consistency
        - Explain normal variations in meditation experiences
        - Offer support for challenges that arise after practice
        - Suggest ways to deepen understanding between classes
        - Clarify techniques learned in recent sessions
        
        GUIDELINES:
        - Base responses strictly on provided post-practice integration and support documentation
        - Do not initiate new meditation practices unless explicitly requested
        - Focus on integration and application of learned techniques
        - Normalize common experiences without pathologizing them
        - Encourage gentle, sustainable practice approaches
        - For persistent difficulties, suggest consulting with instructors
        - Maintain a supportive, understanding tone
        
        LANGUAGE:
        - Default: English
        - If user input is primarily Tamil, respond fully in Tamil
        - Never mix languages in a single response
        
        STYLE:
        - Warm, supportive, and grounding
        - Default length: 2-5 lines
        - Expand only when explicitly requested for detailed guidance
        
        SOURCE USE:
        - Use ONLY provided post-class support documentation and teaching logs
        - Do not speculate about experiences not covered in the documentation"""
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
        if not documents:
            return "No relevant post-class support information found."
        
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


# Global agent instance
post_class_support_agent = PostClassSupportAgent()
