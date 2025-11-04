// Chat functionality
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');

// API base URL - configurable for different environments
const API_BASE_URL = window.API_BASE_URL || '/api';

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Disable input
    messageInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage('user', message);
    messageInput.value = '';

    // Show typing indicator
    const typingIndicator = addTypingIndicator();

    try {
        // Call API with streaming
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: [
                    { role: 'user', content: message }
                ],
                stream: true
            })
        });

        if (!response.ok) {
            throw new Error('Failed to get response');
        }

        // Remove typing indicator
        typingIndicator.remove();

        // Create assistant message container
        const messageDiv = addMessage('assistant', '');
        const contentDiv = messageDiv.querySelector('.message-content');

        // Read stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let citations = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'content') {
                        fullResponse += data.chunk;
                        contentDiv.textContent = fullResponse;
                        scrollToBottom();
                    } else if (data.type === 'citations') {
                        citations = data.citations;
                    } else if (data.type === 'done') {
                        // Add citations if present
                        if (citations.length > 0) {
                            addCitations(messageDiv, citations);
                        }
                    } else if (data.type === 'error') {
                        contentDiv.textContent = 'Error: ' + data.error;
                    }
                }
            }
        }

    } catch (error) {
        console.error('Error:', error);
        addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendButton.disabled = false;
        messageInput.focus();
    }
}

function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🙏';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    chatContainer.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🙏';

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator show';
    indicator.innerHTML = '<span></span><span></span><span></span>';

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(indicator);

    chatContainer.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

function addCitations(messageDiv, citations) {
    const citationsDiv = document.createElement('div');
    citationsDiv.className = 'citations';

    const header = document.createElement('div');
    header.className = 'citations-header';
    header.textContent = `📚 Sources (${citations.length})`;
    header.onclick = () => {
        list.classList.toggle('show');
    };

    const list = document.createElement('div');
    list.className = 'citations-list';

    citations.forEach(citation => {
        const item = document.createElement('div');
        item.className = 'citation-item';
        item.textContent = `${citation.title} - ${citation.reference}`;
        list.appendChild(item);
    });

    citationsDiv.appendChild(header);
    citationsDiv.appendChild(list);

    const contentDiv = messageDiv.querySelector('.message-content');
    contentDiv.appendChild(citationsDiv);
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Upload functionality
async function uploadPDF() {
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];

    if (!file) {
        showUploadStatus('Please select a PDF file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        showUploadStatus('Uploading PDF...', 'success');

        const response = await fetch(`${API_BASE_URL}/ingest`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showUploadStatus(`PDF uploaded successfully! Job ID: ${result.job_id}`, 'success');
            fileInput.value = '';
        } else {
            showUploadStatus(`Error: ${result.detail}`, 'error');
        }
    } catch (error) {
        showUploadStatus(`Error: ${error.message}`, 'error');
    }
}

async function ingestURLs() {
    const urlInput = document.getElementById('urlInput');
    const urls = urlInput.value.split(',').map(url => url.trim()).filter(url => url);

    if (urls.length === 0) {
        showUploadStatus('Please enter at least one URL', 'error');
        return;
    }

    try {
        showUploadStatus('Ingesting URLs...', 'success');

        const response = await fetch(`${API_BASE_URL}/ingest/urls`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ urls })
        });

        const result = await response.json();

        if (response.ok) {
            showUploadStatus(`URLs queued for ingestion! Job ID: ${result.job_id}`, 'success');
            urlInput.value = '';
        } else {
            showUploadStatus(`Error: ${result.detail}`, 'error');
        }
    } catch (error) {
        showUploadStatus(`Error: ${error.message}`, 'error');
    }
}

function showUploadStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.className = `status-message ${type}`;
    statusDiv.textContent = message;

    setTimeout(() => {
        statusDiv.textContent = '';
        statusDiv.className = '';
    }, 5000);
}