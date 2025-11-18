import { useState, type FC } from 'react';
import { Box, Typography, Collapse, IconButton } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AutoStoriesIcon from '@mui/icons-material/AutoStories';

interface Citation {
  title: string;
  reference: string;
}

interface CitationListProps {
  citations: Citation[];
}

const CitationList: FC<CitationListProps> = ({ citations }) => {
  const [expanded, setExpanded] = useState(false);

  if (citations.length === 0) return null;

  return (
    <Box
      sx={{
        marginTop: '12px',
        padding: '12px',
        backgroundColor: 'grey.100',
        borderRadius: '8px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AutoStoriesIcon sx={{ fontSize: '18px', color: 'primary.main' }} />
          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
            Sources ({citations.length})
          </Typography>
        </Box>
        <IconButton
          size="small"
          sx={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.3s',
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ marginTop: '8px' }}>
          {citations.map((citation, index) => (
            <Box
              key={index}
              sx={{
                marginTop: index > 0 ? '8px' : 0,
                paddingLeft: '12px',
                borderLeft: '2px solid',
                borderColor: 'primary.main',
              }}
            >
              <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
                {citation.title} - {citation.reference}
              </Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default CitationList;