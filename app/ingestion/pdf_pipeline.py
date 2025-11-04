"""PDF ingestion pipeline"""
from typing import Dict, Any, BinaryIO
import fitz  # PyMuPDF
import re
from datetime import datetime

from app.core.logging import get_logger
from app.ingestion.storage import blob_storage
from app.ingestion.vectorstore import vector_store
from app.rag.splitters import document_splitter

logger = get_logger(__name__)


class PDFPipeline:
    """PDF ingestion and processing pipeline"""
    
    def __init__(self):
        """Initialize PDF pipeline"""
        self.storage = blob_storage
        self.vector_store = vector_store
        self.splitter = document_splitter
    
    async def process_pdf(
        self,
        file: BinaryIO,
        filename: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process PDF file end-to-end"""
        try:
            logger.info(f"Processing PDF: {filename}")
            
            # Upload to blob storage
            blob_name = self.storage.upload_file(
                file,
                filename,
                metadata=metadata
            )
            
            # Download and parse
            file_bytes = self.storage.download_file(blob_name)
            documents = self._parse_pdf(file_bytes, filename)
            
            # Clean and chunk
            chunks = self._chunk_documents(documents, filename)
            
            # Determine version
            doc_id = self._generate_doc_id(filename)
            version = await self._get_next_version(doc_id)
            
            # Upsert to vector store
            result = await self.vector_store.upsert_documents(
                chunks,
                doc_id=doc_id,
                version=version
            )
            
            return {
                "status": "success",
                "filename": filename,
                "blob_name": blob_name,
                "doc_id": doc_id,
                "version": version,
                "total_pages": len(documents),
                "total_chunks": result["total_chunks"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF {filename}: {e}")
            return {
                "status": "error",
                "filename": filename,
                "error": str(e)
            }
    
    def _parse_pdf(self, file_bytes: bytes, filename: str) -> list:
        """Parse PDF and extract text by page"""
        documents = []
        
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text = page.get_text()
                
                # Clean text
                text = self._clean_text(text)
                
                if text.strip():
                    documents.append({
                        "content": text,
                        "page": page_num + 1,
                        "source": "pdf",
                        "title": filename
                    })
            
            pdf_document.close()
            logger.info(f"Parsed {len(documents)} pages from {filename}")
            
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise
        
        return documents
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers (simple heuristic)
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove headers/footers (simple heuristic)
        lines = text.split('\n')
        if len(lines) > 2:
            # Skip first and last line if they're very short
            if len(lines[0]) < 50:
                lines = lines[1:]
            if len(lines[-1]) < 50:
                lines = lines[:-1]
        
        return '\n'.join(lines).strip()
    
    def _chunk_documents(
        self,
        documents: list,
        filename: str
    ) -> list:
        """Chunk documents for vector store"""
        all_chunks = []
        
        for doc in documents:
            # Add filename to metadata
            doc["title"] = filename
            
            # Split into chunks
            chunks = self.splitter.split_text(
                doc["content"],
                metadata={
                    "page": doc["page"],
                    "source": doc["source"],
                    "title": doc["title"]
                }
            )
            
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _generate_doc_id(self, filename: str) -> str:
        """Generate document ID from filename"""
        # Remove extension and normalize
        doc_id = filename.rsplit('.', 1)[0]
        doc_id = re.sub(r'[^a-zA-Z0-9_-]', '_', doc_id)
        return doc_id.lower()
    
    async def _get_next_version(self, doc_id: str) -> int:
        """Get next version number for document"""
        try:
            # Query for existing versions
            results = self.vector_store.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}'",
                select=["version"],
                top=1,
                order_by=["version desc"]
            )
            
            for result in results:
                return result["version"] + 1
            
            return 1
            
        except Exception as e:
            logger.warning(f"Error getting version, defaulting to 1: {e}")
            return 1


# Global pipeline instance
pdf_pipeline = PDFPipeline()