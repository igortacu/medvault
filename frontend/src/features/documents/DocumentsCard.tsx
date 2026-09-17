import type { ReactNode } from 'react';
import { Card } from '../../components/Card.tsx';
import { Badge } from '../../components/Badge.tsx';

interface DocumentsCardProps {
  title: string;
  /** Human-readable resource type, e.g. "Lab result" — shown as a kicker above the title. */
  type?: string;
  subtitle?: string;
  institution?: string;
  badges?: ReactNode;
  onClick?: () => void;
}
function DocumentsCard({
  title,
  type,
  subtitle,
  institution,
  badges,
  onClick,
}: DocumentsCardProps) {
  return (
    <Card interactive={!!onClick} onClick={onClick} className="h-full">
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          {type && (
            <p className="font-sans text-[10px] font-semibold uppercase tracking-widest text-ink-400">
              {type}
            </p>
          )}

          <p className="font-sans text-sm font-medium text-ink-900">{title}</p>

          {subtitle && <p className="text-sm text-ink-400">{subtitle}</p>}
        </div>

        <div className="flex flex-wrap gap-1 sm:flex-col sm:items-end">
          {institution && <Badge variant="neutral">{institution}</Badge>}

          {badges}
        </div>
      </div>
    </Card>
  );
}

export default DocumentsCard;
