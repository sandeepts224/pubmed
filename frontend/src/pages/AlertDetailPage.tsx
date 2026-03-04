import { useEffect, useState } from 'react'
import { useParams, Link as RouterLink } from 'react-router-dom'
import {
  Alert as MuiAlert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  TextField,
  Typography,
  Divider,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WatchLaterIcon from '@mui/icons-material/WatchLater'
import CancelIcon from '@mui/icons-material/Cancel'
import api from '../api'

type Alert = {
  id: number
  status: string
  reviewer_note?: string | null
  created_at: string
  updated_at: string
  score_id: number
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
  details_json?: string | null
}

type Extraction = {
  id: number
  adverse_event?: string | null
  meddra_term?: string | null
  incidence_pct?: number | null
  sample_size?: number | null
  study_type?: string | null
  subgroup_risk?: string | null
  combination?: string | null
  population?: string | null
  data_source?: string | null
  severity?: string | null
}

type Paper = {
  id: number
  pmid: string
  title?: string | null
  journal?: string | null
  abstract?: string | null
  doi?: string | null
  query_type: string
}

type AlertDetailResponse = {
  alert: Alert
  score: Score
  extraction: Extraction
  paper: Paper
}

type LabelChunk = {
  type: string
  section: string
  meddra_pt?: string | null
  category: string
  text: string
  label_version_id: number
}

type SecondOpinion = {
  label_chunks: LabelChunk[]
  claude_explanation: string
}

function statusColor(status: string) {
  switch (status) {
    case 'confirmed':
      return 'success'
    case 'watch_list':
      return 'warning'
    case 'dismissed':
      return 'default'
    default:
      return 'info'
  }
}

export default function AlertDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<AlertDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [secondOpinion, setSecondOpinion] = useState<SecondOpinion | null>(null)
  const [loadingSecondOpinion, setLoadingSecondOpinion] = useState(false)
  const [secondOpinionError, setSecondOpinionError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const res = await api.get<AlertDetailResponse>(`/alerts/${id}`)
        if (!cancelled) {
          setData(res.data)
          setNote(res.data.alert.reviewer_note ?? '')
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to load alert'
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
  }, [id])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    ;(async () => {
      try {
        setLoadingSecondOpinion(true)
        setSecondOpinionError(null)
        const res = await api.get<SecondOpinion>(`/alerts/${id}/second_opinion`)
        if (!cancelled) {
          setSecondOpinion(res.data)
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to load second opinion'
        if (!cancelled) {
          setSecondOpinionError(message)
        }
      } finally {
        if (!cancelled) setLoadingSecondOpinion(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id])

  const handleDecision = async (status: 'confirmed' | 'watch_list' | 'dismissed') => {
    if (!id) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const res = await api.post(`/alerts/${id}/decision`, {
        status,
        reviewer_note: note || null,
      })
      setData((prev) => (prev ? { ...prev, alert: res.data } : prev))
      setSaveSuccess(true)
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to save decision'
      setSaveError(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={4}>
        <CircularProgress />
      </Box>
    )
  }

  if (error || !data) {
    return (
      <MuiAlert severity="error" sx={{ mt: 2 }}>
        {error ?? 'Not found'}
      </MuiAlert>
    )
  }

  const { alert, score, extraction, paper } = data

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} sx={{ mb: 3 }}>
        <Button
          component={RouterLink}
          to="/"
          startIcon={<ArrowBackIcon />}
          variant="outlined"
          size="small"
          sx={{ borderRadius: 2 }}
        >
          Back to Alerts
        </Button>
        <Typography variant="h4" sx={{ fontWeight: 700, color: '#1a1a1a', flexGrow: 1 }}>
          Alert #{alert.id}
        </Typography>
        <Chip
          label={alert.status.replace('_', ' ')}
          color={statusColor(alert.status) as 'success' | 'warning' | 'default' | 'info'}
          size="medium"
          sx={{ fontWeight: 600, fontSize: '0.9rem' }}
        />
      </Box>

      <Box display="flex" flexDirection={{ xs: 'column', md: 'row' }} gap={3}>
        <Box flex={2}>
          <Paper elevation={0} sx={{ p: 3, mb: 3, borderRadius: 3, border: '1px solid #e0e0e0' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a', mb: 2 }}>
              Paper Information
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1.5, color: '#1a1a1a' }}>
              {paper.title}
            </Typography>
            <Box display="flex" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
              <Chip label={paper.journal} size="small" variant="outlined" />
              <Chip label={`PMID: ${paper.pmid}`} size="small" variant="outlined" />
              <Chip label={paper.query_type} size="small" color="primary" />
            </Box>
            {paper.doi && (
              <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                <strong>DOI:</strong> {paper.doi}
              </Typography>
            )}
            {paper.abstract && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, color: '#1a1a1a' }}>
                  Abstract
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, color: 'text.secondary' }}>
                  {paper.abstract}
                </Typography>
              </Box>
            )}
          </Paper>

          <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid #e0e0e0' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a', mb: 2 }}>
              Reviewer Decision
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <TextField
              label="Reviewer note"
              fullWidth
              multiline
              minRows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              sx={{ mb: 2 }}
            />
            <Box display="flex" gap={1.5} flexWrap="wrap">
              <Button
                variant="contained"
                color="success"
                disabled={saving}
                onClick={() => handleDecision('confirmed')}
                startIcon={<CheckCircleIcon />}
                sx={{ borderRadius: 2, fontWeight: 600 }}
              >
                Confirm Signal
              </Button>
              <Button
                variant="outlined"
                color="warning"
                disabled={saving}
                onClick={() => handleDecision('watch_list')}
                startIcon={<WatchLaterIcon />}
                sx={{ borderRadius: 2, fontWeight: 600 }}
              >
                Watch List
              </Button>
              <Button
                variant="outlined"
                color="error"
                disabled={saving}
                onClick={() => handleDecision('dismissed')}
                startIcon={<CancelIcon />}
                sx={{ borderRadius: 2, fontWeight: 600 }}
              >
                Dismiss
              </Button>
            </Box>
            {saveError && (
              <MuiAlert severity="error" sx={{ mt: 2 }}>
                {saveError}
              </MuiAlert>
            )}
            {saveSuccess && (
              <MuiAlert severity="success" sx={{ mt: 2 }}>
                Decision saved.
              </MuiAlert>
            )}
          </Paper>
        </Box>

        <Box flex={1}>
          <Paper elevation={0} sx={{ p: 2.5, mb: 2, borderRadius: 3, border: '1px solid #e0e0e0' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a', mb: 2 }}>
              Extracted Data
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ '& > *': { mb: 1.5 } }}>
              <Typography variant="body2">
                <strong>Adverse event:</strong> {extraction.adverse_event || extraction.meddra_term || 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Incidence:</strong>{' '}
                {extraction.incidence_pct != null ? `${extraction.incidence_pct}%` : 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Sample size:</strong> {extraction.sample_size ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Study type:</strong> {extraction.study_type ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Subgroup risk:</strong> {extraction.subgroup_risk ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Combination:</strong> {extraction.combination ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Population:</strong> {extraction.population ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Data source:</strong> {extraction.data_source ?? 'N/A'}
              </Typography>
              <Typography variant="body2">
                <strong>Severity:</strong> {extraction.severity ?? 'N/A'}
              </Typography>
            </Box>
          </Paper>

          <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3, border: '1px solid #e0e0e0' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a', mb: 2 }}>
              Score Breakdown
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ '& > *': { mb: 1.5 } }}>
              <Typography variant="body2">
                <strong>Composite score:</strong>{' '}
                <Chip label={score.composite_score.toFixed(1)} size="small" color="primary" sx={{ ml: 1 }} />
              </Typography>
              <Typography variant="body2">
                <strong>Novelty:</strong> {score.novelty_score.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                <strong>Incidence delta:</strong> {score.incidence_delta_score.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                <strong>Subpopulation:</strong> {score.subpopulation_score.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                <strong>Temporal:</strong> {score.temporal_score.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                <strong>Combination:</strong> {score.combination_score.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                <strong>Evidence multiplier:</strong> {score.evidence_multiplier.toFixed(2)}
              </Typography>
            </Box>
          </Paper>
        </Box>
      </Box>

      {/* Second Opinion Section */}
      <Paper elevation={0} sx={{ p: 3, mt: 3, borderRadius: 3, border: '1px solid #e0e0e0' }}>
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a', mb: 2 }}>
          Claude Second Opinion & Label Context
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {loadingSecondOpinion && (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={24} />
          </Box>
        )}
        {secondOpinionError && (
          <MuiAlert severity="warning" sx={{ mb: 2 }}>
            {secondOpinionError}
          </MuiAlert>
        )}
        {secondOpinion && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 'bold' }}>
              Claude Analysis:
            </Typography>
            <Paper
              elevation={0}
              variant="outlined"
              sx={{ p: 2.5, mb: 2, bgcolor: '#f8f9fa', borderRadius: 2, border: '1px solid #e0e0e0' }}
            >
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {secondOpinion.claude_explanation}
              </Typography>
            </Paper>
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 'bold' }}>
              Relevant Label Sections ({secondOpinion.label_chunks.length}):
            </Typography>
            {secondOpinion.label_chunks.map((chunk, idx) => (
              <Paper
                key={idx}
                elevation={0}
                variant="outlined"
                sx={{ p: 2, mb: 1.5, bgcolor: '#fafbfc', borderRadius: 2, border: '1px solid #e0e0e0' }}
              >
                <Box display="flex" gap={1} flexWrap="wrap" mb={0.5}>
                  {chunk.section && (
                    <Chip label={`Section ${chunk.section}`} size="small" color="primary" />
                  )}
                  {chunk.meddra_pt && (
                    <Chip label={chunk.meddra_pt} size="small" color="secondary" />
                  )}
                  <Chip label={chunk.category} size="small" variant="outlined" />
                </Box>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                  {chunk.text}
                </Typography>
              </Paper>
            ))}
          </>
        )}
      </Paper>
    </Box>
  )
}


