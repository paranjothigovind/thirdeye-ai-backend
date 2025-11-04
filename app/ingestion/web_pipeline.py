"""Web scraping ingestion pipeline"""
from typing import List, Dict, Any
import asyncio
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.vectorstore import vector_store
from app.rag.splitters import document_splitter

logger = get_logger(__name__)


class WebPipeline:
    """Web scraping and ingestion pipeline"""
    
    def __init__(self):
        """Initialize web pipeline"""
        self.vector_store = vector_store
        self.splitter = document_splitter
        self.rate_limit = 1.0 / settings.WEB_SCRAPING_RPS
    
    async def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Process multiple URLs"""
        results = []
        
        for url in urls:
            # Rate limiting
            await asyncio.sleep(self.rate_limit)
            
            result = await self._process_single_url(url)
            results.append(result)
        
        return results
    
    async def _process_single_url(self, url: str) -> Dict[str, Any]:
        """Process a single URL"""
        try:
            logger.info(f"Processing URL: {url}")
            
            # Check robots.txt
            if not self._check_robots_txt(url):
                return {
                    "status": "skipped",
                    "url": url,
                    "reason": "Disallowed by robots.txt"
                }
            
            # Fetch content
            content = self._fetch_url(url)
            
            # Parse and clean
            document = self._parse_html(content, url)
            
            # Chunk
            chunks = self._chunk_document(document)
            
            # Generate doc_id
            doc_id = self._generate_doc_id(url)
            version = await self._get_next_version(doc_id)
            
            # Upsert to vector store
            result = await self.vector_store.upsert_documents(
                chunks,
                doc_id=doc_id,
                version=version
            )
            
            return {
                "status": "success",
                "url": url,
                "doc_id": doc_id,
                "version": version,
                "total_chunks": result["total_chunks"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return {
                "status": "error",
                "url": url,
                "error": str(e)
            }
    
    def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch("*", url)
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt: {e}, allowing by default")
            return True
    
    def _fetch_url(self, url: str) -> str:
        """Fetch URL content"""
        headers = {
            "User-Agent": "ThirdEyeMeditationBot/1.0 (Educational purposes)"
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.text
    
    def _parse_html(self, html: str, url: str) -> Dict[str, Any]:
        """Parse HTML and extract content"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract title
        title = soup.title.string if soup.title else urlparse(url).path
        
        # Extract main content
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        
        # Clean text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return {
            "content": text,
            "title": title,
            "url": url,
            "source": "web",
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk document for vector store"""
        chunks = self.splitter.split_text(
            document["content"],
            metadata={
                "title": document["title"],
                "url": document["url"],
                "source": document["source"],
                "fetched_at": document["fetched_at"]
            }
        )
        
        return chunks
    
    def _generate_doc_id(self, url: str) -> str:
        """Generate document ID from URL"""
        parsed = urlparse(url)
        doc_id = f"{parsed.netloc}{parsed.path}".replace('/', '_').replace('.', '_')
        return doc_id.lower()
    
    async def _get_next_version(self, doc_id: str) -> int:
        """Get next version number for document"""
        try:
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
web_pipeline = WebPipeline()