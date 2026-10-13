"""Course & Class Agent for meditation course and class inquiries"""
from typing import List, Dict, Any, AsyncIterator
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.core.logging import get_logger
from app.models.azure_openai import azure_openai_client
from app.rag.retriever import hybrid_retriever
from app.rag.prompts import SYSTEM_PROMPT

logger = get_logger(__name__)


class CourseClassAgent:
    """Specialized agent for course and class related questions"""
    
    def __init__(self):
        """Initialize Course & Class Agent"""
        self.retriever = hybrid_retriever
        self.llm = azure_openai_client
    
    async def invoke(
        self,
        query: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Run Course & Class Agent with streaming"""
        try:
            # Retrieve context with focus on course/class related content
            documents = await self.retriever.retrieve(
                query,
                filters={"context": "course_materials"}
            )
            logger.info(f"âœ… Retrieved {len(documents)} documents for Course & Class Agent context")
            context = self._format_context(documents)
            
            # Generate response with course/class specific instructions
            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
            ]
            
            async for chunk in self.llm.generate_response(messages, stream=stream):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in Course & Class Agent: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Get specialized system prompt for Course & Class Agent"""
        return """You are the Course & Class Assistant for the Third Eye Meditation AI Chatbot.
        
        Your role is to assist users with questions about meditation courses, classes, workshops, and training programs.
        
        PRIMARY FUNCTIONS:
        - Provide information about available meditation courses and classes
        - Explain course structure, duration, and prerequisites
        - Describe what participants can expect to learn in different courses
        - Help users choose appropriate courses based on their experience level
        - Provide details about class formats (online, in-person, hybrid)
        - Share information about instructors and their qualifications
        
        GUIDELINES:
        - Base responses strictly on provided course and class documentation
        - If specific course information is not available, state this clearly
        - Do not make up course details or schedules
        - Focus on factual information about course offerings
        - For questions about registration or enrollment, direct users to official channels
        - Maintain a helpful, informative tone
        
        LANGUAGE:
        - Default: English
        - If user input is primarily Tamil, respond fully in Tamil
        - Never mix languages in a single response
        
        STYLE:
        - Clear, informative, and helpful
        - Default length: 2-5 lines
        - Expand only when explicitly requested for detailed course information
        
        SOURCE USE:
        - Use ONLY provided course and class documentation and teaching logs
        - Do not speculate about courses not in the documentation"""
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
        if not documents:
            return "No relevant course or class information found."
        
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
course_class_agent = CourseClassAgent()
