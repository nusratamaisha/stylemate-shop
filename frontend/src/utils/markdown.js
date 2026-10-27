// The assistant answers in Markdown (**bold**, lists). Turn it into HTML, then
// remove anything unsafe before it reaches the page.
import { marked } from 'marked'
import DOMPurify from 'dompurify'

export function renderMarkdown(text) {
  const html = marked.parse(text || '', { breaks: true })
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
