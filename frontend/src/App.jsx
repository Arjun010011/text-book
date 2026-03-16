import { useEffect, useMemo, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

const defaultFilters = {
  syllabus: '',
  school_type: '',
  grade: '',
  language: '',
  subject: '',
  topic: '',
  doc_type: ''
}

const gradeOptions = ['1','2','3','4','5','6','7','8','9','10','11','12']
const subjectOptions = [
  'Mathematics',
  'Science',
  'Social Science',
  'English',
  'Kannada',
  'Hindi',
  'Physics',
  'Chemistry',
  'Biology',
  'Computer Science',
  'History',
  'Geography',
  'Economics'
]
const languageOptions = ['English','Kannada','Hindi','Urdu']
const schoolTypeOptions = ['government','aided','private']
const topicOptions = ['Mathematics','Science','History','Literature','Kannada','English','Computer Science']
const docTypeOptions = ['Syllabus','Regulations','Specimen Papers','Question Papers','Time Table','Circular','Notification','Guidelines','Document']

function App() {
  const [providers, setProviders] = useState([])
  const [provider, setProvider] = useState('ktbs')
  const [filters, setFilters] = useState(defaultFilters)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [accessMap, setAccessMap] = useState({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(24)
  const [total, setTotal] = useState(0)

  const isExternal = provider === 'openlibrary' || provider === 'gutendex'
  const isKTBS = provider === 'ktbs'
  const isNCERT = provider === 'ncert'
  const isCISCE = provider === 'cisce'

  useEffect(() => {
    fetch(`${API_BASE}/providers`)
      .then((res) => res.json())
      .then((data) => setProviders(data.providers || []))
      .catch(() => setProviders([]))
  }, [])

  useEffect(() => {
    setFilters((prev) => {
      if (isKTBS) {
        return { ...defaultFilters, syllabus: 'KSEEB', school_type: 'government' }
      }
      if (isNCERT) {
        return { ...defaultFilters, syllabus: 'CBSE' }
      }
      if (isCISCE) {
        return { ...defaultFilters, syllabus: 'ICSE' }
      }
      return { ...defaultFilters }
    })
  }, [provider, isKTBS, isNCERT, isCISCE])

  const canSearch = useMemo(() => {
    if (isExternal) return filters.topic
    if (isKTBS) return filters.grade && filters.subject && filters.language && filters.school_type
    if (isNCERT) return filters.grade && filters.subject && filters.language
    if (isCISCE) return filters.grade && filters.subject && filters.doc_type
    return true
  }, [isExternal, isKTBS, isNCERT, isCISCE, filters])

  const handleSearch = async (nextPage = 1) => {
    setError('')
    if (!canSearch) {
      setError('Please select all required filters before searching.')
      return
    }
    setLoading(true)
    try {
      const params = new URLSearchParams({ provider })
      if (isExternal) params.set('q', filters.topic)
      if (isKTBS || isNCERT || isCISCE) {
        Object.entries(filters).forEach(([key, value]) => {
          if (value && key !== 'topic' && key !== 'syllabus') params.set(key, value)
        })
      }
      params.set('page', nextPage)
      params.set('page_size', pageSize)

      const res = await fetch(`${API_BASE}/search?${params.toString()}`)
      if (!res.ok) throw new Error(`Search failed (${res.status})`)
      const data = await res.json()
      setResults(data.results || [])
      setTotal(data.count || 0)
      setPage(data.page || nextPage)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const fetchAccess = async (bookId) => {
    setAccessMap((prev) => ({ ...prev, [bookId]: { loading: true } }))
    try {
      const res = await fetch(`${API_BASE}/book/openlibrary/${bookId}`)
      const data = await res.json()
      setAccessMap((prev) => ({ ...prev, [bookId]: data }))
    } catch (err) {
      setAccessMap((prev) => ({ ...prev, [bookId]: { error: 'Unable to load access info' } }))
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Karnataka eBook Library</p>
          <h1>Search official portals and free ebook APIs.</h1>
          <p className="subhead">
            All sources are online. Select the required filters to search.
          </p>
        </div>
        <div className="hero-card">
          <label className="field">
            Provider
            <select required value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          {isExternal && (
            <label className="field">
              Topic
              <select
                required
                value={filters.topic}
                onChange={(e) => setFilters({ ...filters, topic: e.target.value })}
              >
                <option value="" disabled>Select a topic</option>
                {topicOptions.map((topic) => (
                  <option key={topic} value={topic}>{topic}</option>
                ))}
              </select>
            </label>
          )}

          {(isKTBS || isNCERT || isCISCE) && (
            <div className="filters">
              <label className="field">
                Syllabus
                <select value={filters.syllabus} disabled>
                  <option value={filters.syllabus}>{filters.syllabus}</option>
                </select>
              </label>
              <label className="field">
                Grade
                <select
                  required
                  value={filters.grade}
                  onChange={(e) => setFilters({ ...filters, grade: e.target.value })}
                >
                  <option value="" disabled>Select grade</option>
                  {gradeOptions.map((grade) => (
                    <option key={grade} value={grade}>{grade}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                Subject
                <select
                  required
                  value={filters.subject}
                  onChange={(e) => setFilters({ ...filters, subject: e.target.value })}
                >
                  <option value="" disabled>Select subject</option>
                  {subjectOptions.map((subject) => (
                    <option key={subject} value={subject}>{subject}</option>
                  ))}
                </select>
              </label>
              {isKTBS && (
                <label className="field">
                  Language
                  <select
                    required
                    value={filters.language}
                    onChange={(e) => setFilters({ ...filters, language: e.target.value })}
                  >
                    <option value="" disabled>Select language</option>
                    {languageOptions.map((language) => (
                      <option key={language} value={language}>{language}</option>
                    ))}
                  </select>
                </label>
              )}
              {isKTBS && (
                <label className="field">
                  School Type
                  <select
                    required
                    value={filters.school_type}
                    onChange={(e) => setFilters({ ...filters, school_type: e.target.value })}
                  >
                    <option value="" disabled>Select school type</option>
                    {schoolTypeOptions.map((type) => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </label>
              )}
              {isNCERT && (
                <label className="field">
                  Language
                  <select
                    required
                    value={filters.language}
                    onChange={(e) => setFilters({ ...filters, language: e.target.value })}
                  >
                    <option value="" disabled>Select language</option>
                    {languageOptions.map((language) => (
                      <option key={language} value={language}>{language}</option>
                    ))}
                  </select>
                </label>
              )}
              {isCISCE && (
                <label className="field">
                  Document Type
                  <select
                    required
                    value={filters.doc_type}
                    onChange={(e) => setFilters({ ...filters, doc_type: e.target.value })}
                  >
                    <option value="" disabled>Select document type</option>
                    {docTypeOptions.map((docType) => (
                      <option key={docType} value={docType}>{docType}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}

          <label className="field">
            Page size
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
          <button className="primary" onClick={() => handleSearch(1)} disabled={loading}>
            {loading ? 'Searching...' : 'Find Books'}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </header>

      <section className="results">
        <div className="results-head">
          <h2>Results</h2>
          <span>
            {total} items · Page {page} of {totalPages}
          </span>
        </div>
        <div className="pagination">
          <button
            className="ghost"
            onClick={() => handleSearch(Math.max(1, page - 1))}
            disabled={page <= 1 || loading}
          >
            Previous
          </button>
          <button
            className="ghost"
            onClick={() => handleSearch(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages || loading}
          >
            Next
          </button>
        </div>
        <div className="grid">
          {results.map((book) => (
            <article key={`${book.provider}-${book.id}`} className="card">
              <div className="card-top">
                {book.cover_url ? (
                  <img src={book.cover_url} alt={book.title} />
                ) : (
                  <div className="cover-placeholder">No cover</div>
                )}
                <div>
                  <h3>{book.title}</h3>
                  <p className="meta">{(book.authors || []).join(', ')}</p>
                  <p className="meta">
                    {book.language || book.languages || book.grade ? (
                      <span>
                        {book.language || ''}
                        {book.languages ? book.languages.join(', ') : ''}
                        {book.grade ? ` • Grade ${book.grade}` : ''}
                      </span>
                    ) : (
                      ' '
                    )}
                  </p>
                </div>
              </div>
              <div className="card-actions">
                {book.download_url && (
                  <a className="ghost" href={book.download_url} target="_blank" rel="noreferrer">
                    Download
                  </a>
                )}
                {book.source_url && (
                  <a className="ghost" href={book.source_url} target="_blank" rel="noreferrer">
                    Open Source
                  </a>
                )}
                {book.provider === 'openlibrary' && (
                  <button className="ghost" onClick={() => fetchAccess(book.id)}>
                    Check Access
                  </button>
                )}
              </div>
              {accessMap[book.id] && (
                <div className="access">
                  {accessMap[book.id].loading && <span>Loading access...</span>}
                  {accessMap[book.id].error && <span>{accessMap[book.id].error}</span>}
                  {accessMap[book.id].access && (
                    <div>
                      <p>Status: {accessMap[book.id].access.status}</p>
                      {accessMap[book.id].access.preview_url && (
                        <a href={accessMap[book.id].access.preview_url} target="_blank" rel="noreferrer">
                          Preview
                        </a>
                      )}
                      {accessMap[book.id].access.borrow_url && (
                        <a href={accessMap[book.id].access.borrow_url} target="_blank" rel="noreferrer">
                          Borrow
                        </a>
                      )}
                    </div>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

export default App
