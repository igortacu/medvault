import { useState } from 'react';
import { cn } from '../lib/cn';

export interface AvatarProps {
  /** Full name — used for the alt text and for the initials fallback. */
  name: string;
  src?: string;
  size?: 'sm' | 'default' | 'lg';
  className?: string;
}

const sizes: Record<NonNullable<AvatarProps['size']>, string> = {
  sm: 'h-8 w-8 text-xs',
  default: 'h-10 w-10 text-sm',
  lg: 'h-14 w-14 text-base',
};

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const initials = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '');
  return initials.join('') || '?';
}

/**
 * Falls back to initials if there's no src, or if the image fails to load —
 * relevant since profile photos (SidebarProfile, ProfileFile) are optional.
 */
export function Avatar({
  name,
  src,
  size = 'default',
  className,
}: AvatarProps) {
  const [imgError, setImgError] = useState(false);
  const showImage = Boolean(src) && !imgError;

  return (
    <span
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full',
        'bg-primary-100 font-sans font-medium text-primary-700',
        sizes[size],
        className
      )}
    >
      {showImage ? (
        <img
          src={src}
          alt={name}
          className="h-full w-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : (
        <>
          <span aria-hidden="true">{getInitials(name)}</span>
          <span className="sr-only">{name}</span>
        </>
      )}
    </span>
  );
}

/*
Usage — SidebarProfile / ProfileFile:
<Avatar name={profile.fullName} src={profile.photoUrl} size="sm" />
*/
