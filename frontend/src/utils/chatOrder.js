// The stylist's follow-up questions for an order started in the chat.
//
// The assistant only says "the customer wants this product" (its [ORDER ...] line, checked by
// Flask). These questions then fill in the rest: size, colour, and for a customizable piece any
// changes such as length or sleeves. The choices come from Flask (ChatOrder.to_dict()), so the
// customer can only pick what the shop really sells, and asking needs no extra call to the AI.
import { formatPriceChange } from './format.js'

// A draft is the order being filled in. `order` is what Flask sent; the rest are the answers so far.
export function newDraft(id, order) {
  return {
    id,
    order,
    size: order.size,
    colour: order.colour,
    quantity: order.quantity,
    wantsChanges: order.changes.length ? null : false, // null: not asked yet
    changes: {}, // { group name: option id, or 0 for "as shown" }
  }
}

// The next question to ask, or null when the order is complete.
export function nextQuestion(draft) {
  const { order } = draft
  const name = order.product.name
  if (!draft.size) {
    return {
      key: 'size',
      text: `Which size would you like? The ${name} comes in ${listWords(order.sizes)}.`,
      choices: order.sizes.map((size) => ({ label: size, value: size })),
    }
  }
  if (!draft.colour) {
    return {
      key: 'colour',
      text: `And which colour: ${listWords(order.colours, 'or')}?`,
      choices: order.colours.map((colour) => ({ label: colour, value: colour })),
    }
  }
  if (draft.wantsChanges === null) {
    return {
      key: 'wantsChanges',
      text: 'Would you like any changes, such as a different length or sleeves? A changed piece is sewn to order.',
      choices: [{ label: 'No changes', value: false }, { label: 'Yes, show me', value: true }],
    }
  }
  const group = draft.wantsChanges && order.changes.find((item) => !(item.group in draft.changes))
  if (group) {
    return {
      key: 'change',
      group: group.group,
      text: `${group.group}${group.current ? ` (now ${group.current})` : ''}: what would you like?`,
      choices: [
        { label: 'Keep as shown', value: 0 },
        ...group.options.map((option) => ({
          label: optionLabel(option),
          note: option.extra_price_bdt ? formatPriceChange(option.extra_price_bdt) : '',
          value: option.id,
        })),
      ],
    }
  }
  return null
}

export function applyAnswer(draft, question, value) {
  if (question.key === 'change') draft.changes[question.group] = value
  else draft[question.key] = value
}

// The option ids chosen so far, for the price quote and the order
export const chosenOptionIds = (draft) => Object.values(draft.changes).filter(Boolean)

// Match a typed answer ("m", "size M", "yellow", "no") to one of the question's choices.
const YES = ['yes', 'yeah', 'yep', 'ha', 'haa', 'hya', 'hae', 'ji', 'হ্যাঁ']
const NO = ['no', 'nope', 'na', 'naa', 'না', 'no changes']
export function matchTypedAnswer(question, text) {
  const typed = text.trim().toLowerCase().replace(/^size\s+/, '').replace(/[.!]+$/, '')
  if (question.key === 'wantsChanges') {
    if (YES.includes(typed)) return question.choices.find((choice) => choice.value === true)
    if (NO.includes(typed)) return question.choices.find((choice) => choice.value === false)
  }
  return question.choices.find((choice) => choice.label.toLowerCase() === typed
    || choice.label.toLowerCase().replace(/\s*\(.*\)$/, '') === typed) || null
}

function optionLabel(option) {
  if (option.new_length_inches) return `${option.label} (${option.new_length_inches} in)`
  if (option.sleeve_length_inches) return `${option.label} (${option.sleeve_length_inches} in)`
  return option.label
}

function listWords(items, last = 'and') {
  return items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} ${last} ${items.at(-1)}`
}
