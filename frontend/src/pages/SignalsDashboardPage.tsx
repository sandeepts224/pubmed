import { useEffect, useState } from 'react'
import {
  Alert as MuiAlert,
  Box,
  Chip,
  CircularProgress,
  Link,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import api from '../api'

type AlertSummary = {
  id: number
  status: string
}

type Score = {
  id: number
  composite_score: number
  novelty_score: number
  incidence_delta_score: number
  subpopulation_score: number
  temporal_score: number
  combination_score: number
  evidence_multiplier: number
  created_at: string
}

type Extraction = {
  id: number
  adverse_event?: string | null
  meddra_term?: string | null
  incidence_pct?: number | null
  sample_size?: number | null
  study_type?: string | null
}

type Paper = {
  id: number
  pmid: string
  title?: string | null
  journal?: string | null
  query_type: string
}

type Signal = {
  score: Score
  extraction: Extraction | null
  paper: Paper | null
  alert: AlertSummary | null
}

function alertStatusChip(alert: AlertSummary | null) {
  if (!alert) {
    return <Chip label="no_alert" size="small" variant="outlined" />
  }
  return (
    <Chip
      label={alert.status}
      color={
        (alert.status === 'confirmed'
          ? 'success'
          : alert.status === 'watch_list'
            ? 'warning'
            : alert.status === 'dismissed'
              ? 'default'
              : 'info') as 'success' | 'warning' | 'default' | 'info'
      }
      size="small"
    />
  )
}

export default function SignalsDashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const res = await api.get<Signal[]>('/signals', { params: { limit: 200 } })
        if (!cancelled) {
          setSignals(res.data)
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to load signals'
        if (!cancelled) {
          setError(message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={4}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <MuiAlert severity="error" sx={{ mt: 2 }}>
        {error}
      </MuiAlert>
    )
  }

  if (!signals.length) {
    return (
      <Typography variant="body1" sx={{ mt: 2 }}>
        No scored signals yet.
      </Typography>
    )
  }

  const total = signals.length
  const withAlerts = signals.filter((s) => s.alert).length
  const aboveThreshold = signals.filter((s) => s.score.composite_score >= 50).length

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Signals dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        All scored Keytruda safety signals, including items below the alert threshold. Use this view for
        exploratory analysis beyond alerts.
      </Typography>

      <Box display="flex" gap={1} flexWrap="wrap" sx={{ mb: 2 }}>
        <Chip label={`Total scored: ${total}`} size="small" />
        <Chip label={`Above threshold (>=50): ${aboveThreshold}`} color="primary" size="small" />
        <Chip label={`With alerts: ${withAlerts}`} color="success" size="small" />
      </Box>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Score ID</TableCell>
            <TableCell>Alert</TableCell>
            <TableCell>Composite</TableCell>
            <TableCell>Adverse event</TableCell>
            <TableCell>Incidence</TableCell>
            <TableCell>Sample size</TableCell>
            <TableCell>Paper</TableCell>
            <TableCell>Created</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {signals.map((s) => (
            <TableRow key={s.score.id} hover>
              <TableCell>{s.score.id}</TableCell>
              <TableCell>{alertStatusChip(s.alert)}</TableCell>
              <TableCell>{s.score.composite_score.toFixed(1)}</TableCell>
              <TableCell>
                {s.extraction?.adverse_event || s.extraction?.meddra_term || <Typography variant="caption">n/a</Typography>}
              </TableCell>
              <TableCell>
                {s.extraction?.incidence_pct != null ? `${s.extraction.incidence_pct}%` : (
                  <Typography variant="caption">n/a</Typography>
                )}
              </TableCell>
              <TableCell>
                {s.extraction?.sample_size != null ? s.extraction.sample_size : (
                  <Typography variant="caption">n/a</Typography>
                )}
              </TableCell>
              <TableCell>
                {s.paper ? (
                  <Box>
                    <Typography variant="body2" noWrap>
                      <Link component={RouterLink} to={`/alerts/${s.alert?.id ?? ''}`}>
                        {s.paper.title || `PMID ${s.paper.pmid}`}
                      </Link>
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {s.paper.journal} · PMID {s.paper.pmid}
                    </Typography>
                  </Box>
                ) : (
                  <Typography variant="caption">n/a</Typography>
                )}
              </TableCell>
              <TableCell>{new Date(s.score.created_at).toLocaleString()}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  )
}


