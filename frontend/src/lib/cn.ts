import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merges conditional class names and resolves conflicting Tailwind
 * utility classes (e.g. cn("px-4", condition && "px-6") -> "px-6").
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
