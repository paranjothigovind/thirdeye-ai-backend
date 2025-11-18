import type { FC } from 'react';
import { Box, Avatar, Paper, Typography } from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import PsychologyIcon from '@mui/icons-material/Psychology';
import CitationList from './CitationList';

interface Citation {
  title: string;
  reference: string;
}

interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

const MessageBubble: FC<MessageBubbleProps> = ({ role, content, citations = [] }) => {
  const isUser = role === 'user';

  return (
    <Box
      className="animate-fade-in"
      sx={{
        display: 'flex',
        gap: '12px',
        marginBottom: '16px',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      <Avatar
        sx={{
          width: 40,
          height: 40,
          background: isUser
            ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
            : 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
          flexShrink: 0,
        }}
      >
        {isUser ? <PersonIcon /> : <PsychologyIcon />}
      </Avatar>
      <Paper
        elevation={isUser ? 0 : 1}
        sx={{
          maxWidth: '70%',
          padding: '16px 20px',
          borderRadius: '16px',
          background: isUser
            ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
            : 'white',
          color: isUser ? 'white' : 'text.primary',
          boxShadow: isUser ? 'none' : '0 2px 12px rgba(0, 0, 0, 0.08)',
        }}
      >
        <Typography
          variant="body1"
          sx={{
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </Typography>
        {!isUser && citations.length > 0 && <CitationList citations={citations} />}
      </Paper>
    </Box>
  );
};

export default MessageBubble;