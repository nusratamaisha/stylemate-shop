// The stylist's follow-up questions for an order started in the chat.
//
// The assistant only says "the customer wants this product" (its [ORDER ...] line, checked by
// Flask). These questions then fill in the rest: size, colour, and for a customizable piece any
// changes such as length or sleeves. The choices come from Flask (ChatOrder.to_dict()), so the
// customer can only pick what the shop really sells, and asking needs no extra call to the AI.
import { formatPriceChange } from './format.js'

// The questions in the customer's language. The stylist answers in the language the customer
// writes in (profile rule), so a Bangla answer means Bangla questions. Product, size, colour
// and option names stay as the shop wrote them.
const WORDS = {
  en: {
    size: (name, sizes) => `Which size would you like? The ${name} comes in ${listWords(sizes)}.`,
    colour: (colours) => `And which colour: ${listWords(colours, 'or')}?`,
    wantsChanges: 'Would you like any changes, such as a different length or sleeves? A changed piece is sewn to order.',
    noChanges: 'No changes',
    showChanges: 'Yes, show me',
    group: (group, current) => `${group}${current ? ` (now ${current})` : ''}: what would you like?`,
    keep: 'Keep as shown',
    done: "Here's your order. Check it and go to checkout when you're ready.",
  },
  bn: {
    size: (name, sizes) => `কোন সাইজটি নেবেন? ${name} পাওয়া যায় ${listWords(sizes, 'ও')} সাইজে।`,
    colour: (colours) => `কোন রঙটি নেবেন: ${listWords(colours, 'নাকি')}?`,
    wantsChanges: 'কোনো পরিবর্তন চান, যেমন লম্বা বা হাতা? পরিবর্তন করা পোশাক অর্ডার অনুযায়ী সেলাই করা হয়।',
    noChanges: 'কোনো পরিবর্তন নয়',
    showChanges: 'হ্যাঁ, দেখান',
    group: (group, current) => `${group}${current ? ` (এখন ${current})` : ''}: কোনটি চান?`,
    keep: 'যেমন আছে তেমনই',
    done: 'এই আপনার অর্ডার। দেখে নিয়ে চেকআউটে যান।',
  },
}

// Bangla script in the stylist's answer means the conversation is in Bangla
export const languageOf = (text) => (/[\u0980-\u09FF]/.test(text || '') ? 'bn' : 'en')

// A draft is the order being filled in. `order` is what Flask sent; the rest are the answers so far.
export function newDraft(id, order, lang = 'en') {
  return {
    id,
    order,
    lang,
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
  const words = WORDS[draft.lang] || WORDS.en
  if (!draft.size) {
    return {
      key: 'size',
      text: words.size(order.product.name, order.sizes),
      choices: order.sizes.map((size) => ({ label: size, value: size })),
    }
  }
  if (!draft.colour) {
    return {
      key: 'colour',
      text: words.colour(order.colours),
      choices: order.colours.map((colour) => ({ label: colour, value: colour })),
    }
  }
  if (draft.wantsChanges === null) {
    return {
      key: 'wantsChanges',
      text: words.wantsChanges,
      choices: [{ label: words.noChanges, value: false }, { label: words.showChanges, value: true }],
    }
  }
  const group = draft.wantsChanges && order.changes.find((item) => !(item.group in draft.changes))
  if (group) {
    return {
      key: 'change',
      group: group.group,
      text: words.group(group.group, group.current),
      choices: [
        { label: words.keep, value: 0 },
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

// What the stylist says above the finished order
export const doneText = (draft) => (WORDS[draft.lang] || WORDS.en).done

export function applyAnswer(draft, question, value) {
  if (question.key === 'change') draft.changes[question.group] = value
  else draft[question.key] = value
}

// The option ids chosen so far, for the price quote and the order
export const chosenOptionIds = (draft) => Object.values(draft.changes).filter(Boolean)

// Match a typed answer ("m", "size M", "yellow", "no") to one of the question's choices.
const YES = ['yes', 'yeah', 'yep', 'ha', 'haa', 'hya', 'hae', 'ji', 'হ্যাঁ']
const NO = ['no', 'nope', 'na', 'naa', 'না', 'no changes', 'কোনো পরিবর্তন নয়']
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
