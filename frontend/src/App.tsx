import { CssBaseline, Container, AppBar, Toolbar, Typography, Box } from '@mui/material'
import { Routes, Route, Link } from 'react-router-dom'
import AlertsListPage from './pages/AlertsListPage'
import AlertDetailPage from './pages/AlertDetailPage'
import PipelineViewPage from './pages/PipelineViewPage'

function App() {
  return (
    <>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography
            variant="h6"
            component={Link}
            to="/"
            sx={{ color: 'inherit', textDecoration: 'none', mr: 4 }}
          >
            Keytruda Safety Signals
          </Typography>
          <Box sx={{ flexGrow: 1, display: 'flex', gap: 2 }}>
            <Typography
              component={Link}
              to="/"
              sx={{ color: 'inherit', textDecoration: 'none', fontSize: '0.95rem' }}
            >
              Alerts
            </Typography>
            <Typography
              component={Link}
              to="/pipeline"
              sx={{ color: 'inherit', textDecoration: 'none', fontSize: '0.95rem' }}
            >
              Pipeline View
            </Typography>
          </Box>
        </Toolbar>
      </AppBar>
      <Container sx={{ mt: 3, mb: 4 }}>
        <Routes>
          <Route path="/" element={<AlertsListPage />} />
          <Route path="/alerts/:id" element={<AlertDetailPage />} />
          <Route path="/pipeline" element={<PipelineViewPage />} />
        </Routes>
      </Container>
    </>
  )
}

export default App
