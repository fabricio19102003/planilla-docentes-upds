import { EmptyBoxIllustration } from './EmptyBoxIllustration'
import { EmptyCalendarIllustration } from './EmptyCalendarIllustration'
import { EmptyDocumentIllustration } from './EmptyDocumentIllustration'
import { EmptyInboxIllustration } from './EmptyInboxIllustration'
import { EmptySearchIllustration } from './EmptySearchIllustration'

export {
  EmptyBoxIllustration,
  EmptyCalendarIllustration,
  EmptyDocumentIllustration,
  EmptyInboxIllustration,
  EmptySearchIllustration,
}

export const illustrations = {
  'empty-box': EmptyBoxIllustration,
  'empty-inbox': EmptyInboxIllustration,
  'empty-calendar': EmptyCalendarIllustration,
  'empty-document': EmptyDocumentIllustration,
  'empty-search': EmptySearchIllustration,
}

export type IllustrationName = keyof typeof illustrations
