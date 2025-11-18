import type { FC } from 'react';
import { Box } from '@mui/material';

const TypingIndicator: FC = () => {
  return (
    <Box sx={{ display: 'flex', gap: '6px', alignItems: 'center', padding: '12px 16px' }}>
      <Box
        sx={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: 'primary.main',
          animation: 'pulse 1.4s ease-in-out infinite',
        }}
      />
      <Box
        sx={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: 'primary.main',
          animation: 'pulse 1.4s ease-in-out 0.2s infinite',
        }}
      />
      <Box
        sx={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: 'primary.main',
          animation: 'pulse 1.4s ease-in-out 0.4s infinite',
        }}
      />
    </Box>
  );
};

export default TypingIndicator;