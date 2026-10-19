import i18n from '../i18n';
import { localeFor } from '../i18n/languages';

/** A date in the active UI language, e.g. "19 oct. 2026" / "19 Oct 2026" / "19 окт. 2026 г.". */
export function formatDate(date: string) {
  return new Date(date).toLocaleDateString(localeFor(i18n.language), {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}
