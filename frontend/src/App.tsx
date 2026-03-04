import { CssBaseline, Container, AppBar, Toolbar, Typography, Box, Button, ThemeProvider, createTheme } from '@mui/material'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import WarningIcon from '@mui/icons-material/Warning'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ScienceIcon from '@mui/icons-material/Science'
import AlertsListPage from './pages/AlertsListPage'
import AlertDetailPage from './pages/AlertDetailPage'
import PipelineViewPage from './pages/PipelineViewPage'

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
      light: '#42a5f5',
      dark: '#1565c0',
    },
    secondary: {
      main: '#dc004e',
      light: '#ff5983',
      dark: '#9a0036',
    },
    background: {
      default: '#f5f7fa',
      paper: '#ffffff',
    },
    error: {
      main: '#d32f2f',
    },
    warning: {
      main: '#ed6c02',
    },
    success: {
      main: '#2e7d32',
    },
    info: {
      main: '#0288d1',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
          boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        },
        elevation1: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 8,
        },
      },
    },
  },
})

function App() {
  const location = useLocation()

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="sticky" elevation={0}>
        <Toolbar sx={{ py: 1 }}>
          <ScienceIcon sx={{ mr: 1.5, fontSize: 28 }} />
          <Typography
            variant="h5"
            component={Link}
            to="/"
            sx={{
              color: 'inherit',
              textDecoration: 'none',
              fontWeight: 700,
              letterSpacing: '-0.5px',
              mr: 4,
            }}
          >
            Keytruda Safety Signals
          </Typography>
          <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
            <Button
              component={Link}
              to="/"
              startIcon={<WarningIcon />}
              sx={{
                color: 'inherit',
                backgroundColor: location.pathname === '/' ? 'rgba(255,255,255,0.2)' : 'transparent',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.15)',
                },
                fontWeight: location.pathname === '/' ? 600 : 400,
              }}
            >
              Alerts
            </Button>
            <Button
              component={Link}
              to="/pipeline"
              startIcon={<DashboardIcon />}
              sx={{
                color: 'inherit',
                backgroundColor: location.pathname === '/pipeline' ? 'rgba(255,255,255,0.2)' : 'transparent',
                '&:hover': {
                  backgroundColor: 'rgba(255,255,255,0.15)',
                },
                fontWeight: location.pathname === '/pipeline' ? 600 : 400,
              }}
            >
              Pipeline View
            </Button>
          </Box>
        </Toolbar>
      </AppBar>
      <Box
        sx={{
          minHeight: 'calc(100vh - 64px)',
          background: 'linear-gradient(to bottom, #f5f7fa 0%, #ffffff 100%)',
        }}
      >
        <Container maxWidth="xl" sx={{ pt: 4, pb: 6 }}>
          <Routes>
            <Route path="/" element={<AlertsListPage />} />
            <Route path="/alerts/:id" element={<AlertDetailPage />} />
            <Route path="/pipeline" element={<PipelineViewPage />} />
          </Routes>
        </Container>
      </Box>
    </ThemeProvider>
  )
}

export default App
