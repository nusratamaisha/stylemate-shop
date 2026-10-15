// The shop's sections, in the order customers see them. The first name is the product's
// category in the CSV; the second is the heading customers see. A category not listed
// here still gets its own section at the end, under its own name.
// Used by the home page (category tiles) and the shop page (sections), so the two agree.
export const SECTIONS = [
  ['Dress', 'Dresses'],
  ['Top', 'Tops'],
  ['Bottoms', 'Pants and skirts'],
  ['Co-ord set', 'Sets'],
]

export const sectionTitle = (name) => SECTIONS.find(([category]) => category === name)?.[1] || name
