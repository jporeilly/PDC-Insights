import { useEffect, useState } from 'react'
import Markdown from './Markdown.jsx'

// Generic document popup: renders markdown, either passed directly (`text`)
// or fetched from an endpoint (`url`). Same component as the Policy Generator.
export default function DocModal({ title, url, text: given, onClose }) {
  const [text, setText] = useState(given ?? null)

  useEffect(() => {
    if (given != null) { setText(given); return undefined }
    fetch(url)
      .then((r) => r.text())
      .then(setText)
      .catch(() => setText(`Could not load ${title}.`))
    return undefined
  }, [url, title, given])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h3>{title}</h3>
          <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="modal-body">
          {text === null ? <p className="loading">Loading…</p> : <Markdown text={text} />}
        </div>
      </div>
    </div>
  )
}
