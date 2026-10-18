import type {
  ConnectionStatus,
  Institution,
  InstitutionConnection,
} from '../../api/types';

/** An IDNP is 13 digits; spaces typed while copying it are ignored. */
export function normalizeIdnp(value: string): string {
  return value.replace(/\s+/g, '');
}

export function validateIdnp(value: string): string | null {
  const idnp = normalizeIdnp(value);
  if (!idnp) return 'Enter your IDNP.';
  if (!/^\d+$/.test(idnp)) return 'The IDNP contains only digits.';
  if (idnp.length !== 13) return 'The IDNP is 13 digits long.';
  return null;
}

/**
 * The newest connection per institution. The list comes back newest first
 * and keeps every past attempt, so the first one seen wins. Revoked
 * connections are history: the institution can simply be added again.
 */
export function latestConnections(
  connections: InstitutionConnection[]
): Map<string, InstitutionConnection> {
  const latest = new Map<string, InstitutionConnection>();
  for (const connection of connections) {
    if (!latest.has(connection.institution_id)) {
      latest.set(connection.institution_id, connection);
    }
  }
  for (const [institutionId, connection] of latest) {
    if (connection.status === 'revoked') latest.delete(institutionId);
  }
  return latest;
}

const LIVE_STATUSES: ConnectionStatus[] = [
  'pending_consent',
  'authorizing',
  'active',
];

export function isLive(connection: InstitutionConnection | undefined): boolean {
  return Boolean(connection && LIVE_STATUSES.includes(connection.status));
}

/** Institutions that can still be connected (no live connection). */
export function connectable(
  institutions: Institution[],
  latest: Map<string, InstitutionConnection>,
  type: Institution['type']
): Institution[] {
  return institutions.filter(
    (i) => i.type === type && !isLive(latest.get(i.id))
  );
}

/** Statuses the patient can fix by connecting the same institution again. */
export function canReconnect(connection: InstitutionConnection): boolean {
  return ['no_match', 'expired', 'error'].includes(connection.status);
}

const RESOURCE_LABELS: Record<string, string> = {
  Patient: 'Patient details',
  Observation: 'Measurements and lab results',
  Condition: 'Diagnoses',
  DiagnosticReport: 'Lab reports',
  MedicationRequest: 'Prescriptions',
  MedicationStatement: 'Medications',
  DocumentReference: 'Documents',
  Encounter: 'Visits and hospitalizations',
  Procedure: 'Procedures',
  Immunization: 'Vaccinations',
  ImagingStudy: 'Imaging',
  CarePlan: 'Care plans',
};

/** Human labels for granted SMART scopes, e.g. patient/Condition.read. */
export function scopeLabels(scopes: string[] | null | undefined): string[] {
  const labels = (scopes ?? [])
    .map((scope) => /^patient\/(\w+)\.read$/.exec(scope)?.[1])
    .filter((type): type is string => Boolean(type))
    .map((type) => RESOURCE_LABELS[type] ?? type);
  return [...new Set(labels)];
}

export type StatusTone = 'success' | 'warning' | 'neutral' | 'danger';

export function statusPresentation(connection: InstitutionConnection): {
  label: string;
  tone: StatusTone;
  explanation?: string;
} {
  switch (connection.status) {
    case 'active':
      return { label: 'Connected', tone: 'success' };
    case 'pending_consent':
    case 'authorizing':
      return {
        label: 'Connecting',
        tone: 'warning',
        explanation: 'Waiting for the institution to confirm.',
      };
    case 'no_match':
      return {
        label: 'No records found',
        tone: 'neutral',
        explanation:
          'This institution has no records for that IDNP. Nothing was imported.',
      };
    case 'expired':
      return {
        label: 'Expired',
        tone: 'danger',
        explanation: 'Access ended. Reconnect to see these records again.',
      };
    case 'error':
      return {
        label: 'Failed',
        tone: 'danger',
        explanation:
          connection.failure_reason === 'authorization_abandoned'
            ? 'The connection was not finished.'
            : 'The institution could not be reached.',
      };
    case 'revoked':
      return { label: 'Disconnected', tone: 'neutral' };
  }
}

// One batch is created in a single request, so its consent times sit well
// within this window of each other.
const BATCH_WINDOW_MS = 60_000;

/**
 * The public connections made by the most recent batch: the ones consented
 * to alongside the newest consent. The patient may have unticked some, and
 * older connections must not count towards this batch's outcome.
 */
export function latestBatch(
  institutions: Institution[],
  latest: Map<string, InstitutionConnection>
): InstitutionConnection[] {
  const outcomes = institutions
    .filter((i) => i.type === 'public')
    .map((i) => latest.get(i.id))
    .filter((c): c is InstitutionConnection => Boolean(c?.consented_at));
  const newest = Math.max(...outcomes.map((c) => Date.parse(c.consented_at!)));
  return outcomes.filter(
    (c) => Date.parse(c.consented_at!) >= newest - BATCH_WINDOW_MS
  );
}

export interface ResultMessage {
  variant: 'success' | 'error' | 'info';
  title: string;
  description?: string;
}

/**
 * What to tell the patient on landing back from the OAuth redirect
 * (?connection=…). For a batch the outcome is read off the connections the
 * batch created: the live ones among the public institutions.
 */
export function resultMessage(
  result: string,
  institutions: Institution[],
  latest: Map<string, InstitutionConnection>
): ResultMessage | null {
  switch (result) {
    case 'active':
      return { variant: 'success', title: 'Institution connected' };
    case 'no_match':
      return {
        variant: 'info',
        title: 'No records found',
        description:
          'The institution has no records for that IDNP. Nothing was imported.',
      };
    case 'error':
      return {
        variant: 'error',
        title: "Couldn't finish connecting",
        description: 'Please try again.',
      };
    case 'expired':
      return {
        variant: 'error',
        title: 'The connection timed out',
        description: 'Please start again.',
      };
    case 'done': {
      const batch = latestBatch(institutions, latest);
      const connected = batch.filter((c) => c.status === 'active').length;
      const failed = batch.filter(canReconnect).length;
      return {
        variant: connected ? 'success' : 'info',
        title: `Connected to ${connected} public ${connected === 1 ? 'institution' : 'institutions'}`,
        description: failed
          ? `${failed} could not be connected. See the list below.`
          : undefined,
      };
    }
    default:
      return null;
  }
}
