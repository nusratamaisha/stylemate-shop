// Every call to Flask goes through here, so errors are handled the same way everywhere.

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const options = { method, headers: {} }
  if (form) {
    options.body = form // FormData: the browser sets the multipart header itself
  } else if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`/api${path}`, options)
  } catch {
    throw new ApiError("Can't reach the shop. Check your connection and try again.", 0)
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(data.error || `Something went wrong (error ${response.status}).`, response.status)
  }
  return data
}
