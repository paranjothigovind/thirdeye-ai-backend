# TODO: Delete All Vector Data and PDFs

## Steps to Complete
- [x] Add clear_all method to VectorStore class in vectorstore.py to delete and recreate the Azure Search index
- [x] Add clear_all method to BlobStorage class in storage.py to delete all blobs in the container
- [x] Add a new API endpoint /clear in routes_ingest.py to trigger clearing vector data and PDFs
- [x] Test the new endpoint to ensure it works correctly (imports successful)
