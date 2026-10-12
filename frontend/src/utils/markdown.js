// The assistant answers in Markdown (**bold**, lists). Turn it into HTML, then
// remove anything unsafe before it reaches the page.
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// For short previews (the owner dashboard): the answer as plain text, without ** and list marks.
export function plainText(text) {
  return (text || '').replace(/[*_`#>]/g, '').replace(/^\s*[-+]\s+/gm, '').replace(/\s+/g, ' ').trim()
}

export function renderMarkdown(text) {
  const html = marked.parse(text || '', { breaks: true })
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
