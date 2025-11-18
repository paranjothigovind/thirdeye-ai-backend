import { useState, type FC, type ChangeEvent } from 'react';
import { Box, TextField, Button, Typography, Paper, Alert } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import LinkIcon from '@mui/icons-material/Link';

const API_BASE_URL = '/api';

const FileUpload: FC = () => {
  const [urls, setUrls] = useState('');
  const [status, setStatus] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setStatus({ message: 'Uploading PDF...', type: 'success' });

      const response = await fetch(`${API_BASE_URL}/ingest`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        setStatus({ message: `PDF uploaded successfully! Job ID: ${result.job_id}`, type: 'success' });
        event.target.value = '';
      } else {
        setStatus({ message: `Error: ${result.detail}`, type: 'error' });
      }
    } catch (error) {
      setStatus({ message: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`, type: 'error' });
    }

    setTimeout(() => setStatus(null), 5000);
  };

  const handleURLIngest = async () => {
    const urlList = urls.split(',').map((url) => url.trim()).filter((url) => url);

    if (urlList.length === 0) {
      setStatus({ message: 'Please enter at least one URL', type: 'error' });
      return;
    }

    try {
      setStatus({ message: 'Ingesting URLs...', type: 'success' });

      const response = await fetch(`${API_BASE_URL}/ingest/urls`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ urls: urlList }),
      });

      const result = await response.json();

      if (response.ok) {
        setStatus({ message: `URLs queued for ingestion! Job ID: ${result.job_id}`, type: 'success' });
        setUrls('');
      } else {
        setStatus({ message: `Error: ${result.detail}`, type: 'error' });
      }
    } catch (error) {
      setStatus({ message: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`, type: 'error' });
    }

    setTimeout(() => setStatus(null), 5000);
  };

  return (
    <Paper
      elevation={0}
      sx={{
        padding: '20px',
        borderTop: '1px solid',
        borderColor: 'grey.200',
        background: 'grey.50',
      }}
    >
      <Typography variant="body2" sx={{ marginBottom: '12px', fontWeight: 600, color: 'text.secondary' }}>
        📚 Ingest Knowledge
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <Box sx={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <Button
            component="label"
            variant="outlined"
            startIcon={<CloudUploadIcon />}
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              borderColor: 'grey.300',
              color: 'text.primary',
              '&:hover': {
                borderColor: 'primary.main',
                backgroundColor: 'primary.50',
              },
            }}
          >
            Upload PDF
            <input type="file" hidden accept=".pdf" onChange={handleFileUpload} />
          </Button>
          <TextField
            size="small"
            value={urls}
            onChange={(e) => setUrls(e.target.value)}
            placeholder="Enter URLs (comma-separated)"
            sx={{
              flex: 1,
              minWidth: '200px',
              '& .MuiOutlinedInput-root': {
                borderRadius: '12px',
                backgroundColor: 'white',
              },
            }}
          />
          <Button
            variant="contained"
            startIcon={<LinkIcon />}
            onClick={handleURLIngest}
            sx={{
              borderRadius: '12px',
              textTransform: 'none',
              background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #63408a 0%, #5568d3 100%)',
              },
            }}
          >
            Ingest URLs
          </Button>
        </Box>
        {status && (
          <Alert severity={status.type} sx={{ borderRadius: '12px' }}>
            {status.message}
          </Alert>
        )}
      </Box>
    </Paper>
  );
};

export default FileUpload;