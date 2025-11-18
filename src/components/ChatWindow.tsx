import { useState, useRef, useEffect, type FC } from 'react';
import { Box, Paper, Typography, Container } from '@mui/material';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import FileUpload from './FileUpload';
import TypingIndicator from './TypingIndicator';

interface Citation {
  title: string;
  reference: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

const API_BASE_URL = '/api';

const ChatWindow: FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Welcome! I'm here to guide you through Third Eye (Ajna) meditation practices. Ask me about techniques, benefits, safety considerations, or any questions about your practice. All my guidance is grounded in authentic teachings and includes proper citations.",
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = { role: 'user', content };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [{ role: 'user', content }],
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let citations: Citation[] = [];

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'content') {
                  fullResponse += data.chunk;
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMessage = newMessages[newMessages.length - 1];
                    if (lastMessage && lastMessage.role === 'assistant') {
                      lastMessage.content = fullResponse;
                    } else {
                      newMessages.push({ role: 'assistant', content: fullResponse });
                    }
                    return newMessages;
                  });
                } else if (data.type === 'citations') {
                  citations = data.citations;
                } else if (data.type === 'done') {
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastMessage = newMessages[newMessages.length - 1];
                    if (lastMessage && lastMessage.role === 'assistant') {
                      lastMessage.citations = citations;
                    }
                    return newMessages;
                  });
                } else if (data.type === 'error') {
                  throw new Error(data.error);
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ height: '100vh', display: 'flex', alignItems: 'center', padding: '20px' }}>
      <Paper
        elevation={8}
        sx={{
          width: '100%',
          height: '90vh',
          borderRadius: '24px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          background: 'white',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
        }}
      >
        {/* Header */}
        <Box
          sx={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            padding: '32px',
            textAlign: 'center',
          }}
        >
          <Typography variant="h1" sx={{ fontSize: '2rem', marginBottom: '8px', fontWeight: 700 }}>
            🧘 Third Eye Meditation AI
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.95, fontSize: '0.95rem' }}>
            Your compassionate guide to Ajna chakra meditation
          </Typography>
        </Box>

        {/* Chat Messages */}
        <Box
          ref={chatContainerRef}
          className="scrollbar-hidden"
          sx={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
            background: 'grey.50',
          }}
        >
          {messages.map((message, index) => (
            <MessageBubble
              key={index}
              role={message.role}
              content={message.content}
              citations={message.citations}
            />
          ))}
          {isLoading && (
            <Box className="animate-fade-in" sx={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                🙏
              </Box>
              <Paper
                elevation={1}
                sx={{
                  borderRadius: '16px',
                  background: 'white',
                  boxShadow: '0 2px 12px rgba(0, 0, 0, 0.08)',
                }}
              >
                <TypingIndicator />
              </Paper>
            </Box>
          )}
        </Box>

        {/* File Upload */}
        <FileUpload />

        {/* Chat Input */}
        <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
      </Paper>
    </Container>
  );
};

export default ChatWindow;