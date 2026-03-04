import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Alert as MuiAlert, Box, Button, Chip, CircularProgress, Paper, TextField, Typography } from '@mui/material'
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
      <Typography variant="h5" gutterBottom>
        Alert #{alert.id}{' '}
        <Chip label={alert.status} color={statusColor(alert.status) as 'success' | 'warning' | 'default' | 'info'} size="small" />
      </Typography>

      <Box display="flex" flexDirection={{ xs: 'column', md: 'row' }} gap={2}>
        <Box flex={2}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              Paper
            </Typography>
            <Typography variant="subtitle1">{paper.title}</Typography>
            <Typography variant="body2" color="text.secondary">
              {paper.journal} · PMID {paper.pmid} · Query: {paper.query_type}
            </Typography>
            {paper.doi && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                DOI: {paper.doi}
              </Typography>
            )}
            {paper.abstract && (
              <Typography variant="body2" sx={{ mt: 2, whiteSpace: 'pre-wrap' }}>
                {paper.abstract}
              </Typography>
            )}
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Reviewer decision
            </Typography>
            <TextField
              label="Reviewer note"
              fullWidth
              multiline
              minRows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              sx={{ mb: 2 }}
            />
            <Box display="flex" gap={1}>
              <Button
                variant="contained"
                color="success"
                disabled={saving}
                onClick={() => handleDecision('confirmed')}
              >
                Confirmed signal
              </Button>
              <Button
                variant="outlined"
                color="warning"
                disabled={saving}
                onClick={() => handleDecision('watch_list')}
              >
                Watch list
              </Button>
              <Button
                variant="outlined"
                color="inherit"
                disabled={saving}
                onClick={() => handleDecision('dismissed')}
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
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              Extracted data
            </Typography>
            <Typography variant="body2">
              <strong>Adverse event:</strong> {extraction.adverse_event || extraction.meddra_term}
            </Typography>
            <Typography variant="body2">
              <strong>Incidence:</strong>{' '}
              {extraction.incidence_pct != null ? `${extraction.incidence_pct}%` : 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Sample size:</strong> {extraction.sample_size ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Study type:</strong> {extraction.study_type ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Subgroup risk:</strong> {extraction.subgroup_risk ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Combination:</strong> {extraction.combination ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Population:</strong> {extraction.population ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Data source:</strong> {extraction.data_source ?? 'n/a'}
            </Typography>
            <Typography variant="body2">
              <strong>Severity:</strong> {extraction.severity ?? 'n/a'}
            </Typography>
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Score breakdown
            </Typography>
            <Typography variant="body2">
              <strong>Composite score:</strong> {score.composite_score.toFixed(1)}
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
          </Paper>
        </Box>
      </Box>

      {/* Second Opinion Section */}
      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="h6" gutterBottom>
          Claude Second Opinion & Label Context
        </Typography>
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
            <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {secondOpinion.claude_explanation}
              </Typography>
            </Paper>
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 'bold' }}>
              Relevant Label Sections ({secondOpinion.label_chunks.length}):
            </Typography>
            {secondOpinion.label_chunks.map((chunk, idx) => (
              <Paper
                key={idx}
                variant="outlined"
                sx={{ p: 1.5, mb: 1, bgcolor: 'background.default' }}
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


