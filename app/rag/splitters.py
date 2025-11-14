"""Text splitting utilities"""
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentSplitter:
    """Document chunking with token-aware splitting"""
    
    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP
    ):
        """Initialize splitter"""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize tokenizer for accurate token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}, using character-based splitting")
            self.tokenizer = None
        
        # Create splitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self._token_length if self.tokenizer else len,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )
    
    def _token_length(self, text: str) -> int:
        """Calculate token length"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text)
    
    def split_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Split text into chunks with metadata"""
        chunks = self.splitter.split_text(text)
        
        result = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "content": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "token_count": self._token_length(chunk),
            }
            
            # Add provided metadata
            if metadata:
                chunk_data.update(metadata)
            
            result.append(chunk_data)
        
        logger.info(f"Split text into {len(chunks)} chunks")
        return result
    
    def split_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Split multiple documents"""
        all_chunks = []
        
        for doc in documents:
            text = doc.get("content", "")
            metadata = {k: v for k, v in doc.items() if k != "content"}
            
            chunks = self.split_text(text, metadata)
            all_chunks.extend(chunks)
        
        return all_chunks


# Global splitter instance
document_splitter = DocumentSplitter()