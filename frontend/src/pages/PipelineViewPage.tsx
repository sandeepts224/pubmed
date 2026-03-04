import { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Alert as MuiAlert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  Card,
  CardContent,
  Grid,
  IconButton,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ArticleIcon from '@mui/icons-material/Article'
import AssessmentIcon from '@mui/icons-material/Assessment'
import api from '../api'

type Paper = {
  id: number
  pmid: string
  title?: string | null
  journal?: string | null
  abstract?: string | null
  doi?: string | null
  query_type: string
  created_at: string
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

type Score = {
  id: number
  composite_score: number
  novelty_score: number
  incidence_delta_score: number
  subpopulation_score: number
  temporal_score: number
  combination_score: number
  evidence_multiplier: number
}

type Alert = {
  id: number
  status: string
  created_at: string
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

type PipelinePaper = {
  paper: Paper
  extraction?: Extraction | null
  score?: Score | null
  alert?: Alert | null
}

type PipelineResponse = {
  papers: PipelinePaper[]
  total: number
  with_extraction: number
  with_score: number
  with_alert: number
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

export default function PipelineViewPage() {
  const [data, setData] = useState<PipelineResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [secondOpinions, setSecondOpinions] = useState<Map<number, SecondOpinion>>(new Map())
  const [loadingSecondOpinions, setLoadingSecondOpinions] = useState<Set<number>>(new Set())

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const res = await api.get<PipelineResponse>('/pipeline/last7d')
        if (!cancelled) {
          setData(res.data)
        }
      } catch (e: unknown) {
        if (!cancelled) {
          const err = e as { message?: string }
          setError(err.message ?? 'Failed to load pipeline data')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleRow = async (paperId: number, scoreId: number | null) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(paperId)) {
        next.delete(paperId)
      } else {
        next.add(paperId)
        // Fetch second opinion if we have a score and haven't loaded it yet
        if (scoreId && !secondOpinions.has(scoreId) && !loadingSecondOpinions.has(scoreId)) {
          setLoadingSecondOpinions((prev) => new Set(prev).add(scoreId))
          api
            .get<SecondOpinion>(`/scores/${scoreId}/second_opinion`)
            .then((res) => {
              setSecondOpinions((prev) => new Map(prev).set(scoreId, res.data))
            })
            .catch((e: unknown) => {
              const err = e as { message?: string }
              console.error(`Failed to load second opinion for score ${scoreId}:`, err.message)
            })
            .finally(() => {
              setLoadingSecondOpinions((prev) => {
                const next = new Set(prev)
                next.delete(scoreId)
                return next
              })
            })
        }
      }
      return next
    })
  }

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

  if (!data || !data.papers.length) {
    return (
      <Typography variant="body1" sx={{ mt: 2 }}>
        No papers found in the last 7 days.
      </Typography>
    )
  }

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 700, color: '#1a1a1a' }}>
          Pipeline View
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Comprehensive view of all Keytruda papers processed in the last 7 days, including extraction status, scoring,
          and alert generation.
        </Typography>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      Total Papers
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                      {data.total}
                    </Typography>
                  </Box>
                  <ArticleIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', color: 'white' }}>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      With Extraction
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                      {data.with_extraction}
                    </Typography>
                  </Box>
                  <AssessmentIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', color: 'white' }}>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      With Score
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                      {data.with_score}
                    </Typography>
                  </Box>
                  <AssessmentIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', color: 'white' }}>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      With Alert
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                      {data.with_alert}
                    </Typography>
                  </Box>
                  <AssessmentIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>

      <Paper elevation={0} sx={{ borderRadius: 3, overflow: 'hidden' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: '#f8f9fa' }}>
              <TableCell sx={{ fontWeight: 600, width: 50 }}>ID</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Paper</TableCell>
              <TableCell sx={{ fontWeight: 600, width: 120 }}>Extraction</TableCell>
              <TableCell sx={{ fontWeight: 600, width: 120 }}>Score</TableCell>
              <TableCell sx={{ fontWeight: 600, width: 120 }}>Alert</TableCell>
              <TableCell sx={{ fontWeight: 600, width: 100 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
        <TableBody>
          {data.papers.map((item) => {
            const { paper, extraction, score, alert } = item
            const isExpanded = expandedRows.has(paper.id)
            return (
              <>
                <TableRow
                  key={paper.id}
                  hover
                  sx={{
                    '&:hover': { backgroundColor: '#f8f9fa' },
                    '&:last-child td': { border: 0 },
                  }}
                >
                  <TableCell>{paper.id}</TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="bold">
                      {paper.title || `PMID ${paper.pmid}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {paper.journal} · PMID {paper.pmid}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {extraction ? (
                      <Chip label="Yes" color="success" size="small" />
                    ) : (
                      <Chip label="No" color="default" size="small" />
                    )}
                  </TableCell>
                  <TableCell>
                    {score ? (
                      <Chip label={score.composite_score.toFixed(1)} color="info" size="small" />
                    ) : (
                      <Chip label="No" color="default" size="small" />
                    )}
                  </TableCell>
                  <TableCell>
                    {alert ? (
                      <Chip
                        label={alert.status}
                        color={statusColor(alert.status) as 'success' | 'warning' | 'default' | 'info'}
                        size="small"
                        component={RouterLink}
                        to={`/alerts/${alert.id}`}
                        clickable
                      />
                    ) : (
                      <Chip label="None" color="default" size="small" />
                    )}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={() => toggleRow(paper.id, score?.id ?? null)}
                      sx={{
                        color: 'primary.main',
                        '&:hover': { backgroundColor: 'primary.light', color: 'white' },
                      }}
                    >
                      {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </IconButton>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell colSpan={6} sx={{ py: 0, border: 0, backgroundColor: '#fafbfc' }}>
                    <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                      <Box sx={{ p: 3 }}>
                        {extraction && (
                          <Paper elevation={0} sx={{ p: 2.5, mb: 2, borderRadius: 2, border: '1px solid #e0e0e0' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a' }}>
                              Extracted Data
                            </Typography>
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
                          </Paper>
                        )}

                        {score && (
                          <Paper elevation={0} sx={{ p: 2.5, mb: 2, borderRadius: 2, border: '1px solid #e0e0e0' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a' }}>
                              Score Breakdown
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
                        )}

                        {score && (
                          <Paper elevation={0} sx={{ p: 2.5, mb: 2, borderRadius: 2, border: '1px solid #e0e0e0' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a' }}>
                              Claude Second Opinion & Label Context
                            </Typography>
                            {loadingSecondOpinions.has(score.id) ? (
                              <Box display="flex" justifyContent="center" py={2}>
                                <CircularProgress size={24} />
                              </Box>
                            ) : secondOpinions.has(score.id) ? (
                              <>
                                <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
                                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                                    {secondOpinions.get(score.id)!.claude_explanation}
                                  </Typography>
                                </Paper>
                                <Typography variant="subtitle2" sx={{ mt: 2, mb: 1, fontWeight: 'bold' }}>
                                  Relevant Label Sections ({secondOpinions.get(score.id)!.label_chunks.length}):
                                </Typography>
                                {secondOpinions.get(score.id)!.label_chunks.map((chunk, idx) => (
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
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                Click "Details" to load second opinion.
                              </Typography>
                            )}
                          </Paper>
                        )}

                        {paper.abstract && (
                          <Paper elevation={0} sx={{ p: 2.5, borderRadius: 2, border: '1px solid #e0e0e0' }}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: '#1a1a1a' }}>
                              Abstract
                            </Typography>
                            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                              {paper.abstract}
                            </Typography>
                          </Paper>
                        )}
                      </Box>
                    </Collapse>
                  </TableCell>
                </TableRow>
              </>
            )
          })}
        </TableBody>
      </Table>
      </Paper>
    </Box>
  )
}

